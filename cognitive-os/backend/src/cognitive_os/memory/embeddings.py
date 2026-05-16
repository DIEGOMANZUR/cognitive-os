from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from typing import Any, Literal, Protocol

import httpx
from pydantic import SecretStr

from cognitive_os.core.config import settings
from cognitive_os.core.resilience import embeddings_circuit_breaker, retry_transient_http

EmbeddingTaskKind = Literal["document", "query"]


class EmbeddingProvider(Protocol):
    def embed_text(self, text: str, *, kind: EmbeddingTaskKind = "document") -> list[float]:
        """Return an embedding vector for one text."""

    def embed_texts(
        self,
        texts: list[str],
        *,
        kind: EmbeddingTaskKind = "document",
    ) -> list[list[float]]:
        """Return embedding vectors for multiple texts."""


class _ApiKeyPool:
    """Round-robin API key pool with on-demand rotation when one is exhausted."""

    def __init__(self, keys: Sequence[SecretStr]) -> None:
        if not keys:
            msg = "No embeddings API keys configured."
            raise ValueError(msg)
        self._keys = list(keys)
        self._index = 0
        self._lock = threading.Lock()

    def current(self) -> SecretStr:
        with self._lock:
            return self._keys[self._index]

    def rotate(self) -> SecretStr:
        with self._lock:
            self._index = (self._index + 1) % len(self._keys)
            return self._keys[self._index]

    def __len__(self) -> int:
        return len(self._keys)


def _is_quota_error(exc: httpx.HTTPStatusError) -> bool:
    if exc.response.status_code in (401, 403, 429):
        return True
    try:
        body = exc.response.json()
    except Exception:
        return False
    status = (body.get("error") or {}).get("status", "")
    return status in {"RESOURCE_EXHAUSTED", "PERMISSION_DENIED", "UNAUTHENTICATED"}


class GeminiEmbeddingProvider:
    """Embedding provider for Google Gemini's native embedContent / batchEmbedContents.

    Uses the v1beta endpoint with `output_dimensionality` (Matryoshka) so we
    can keep `EMBEDDINGS_DIMENSION` independent from the model's native size
    (3072 for `gemini-embedding-001`). Honors `taskType` for retrieval-tuned
    embeddings. Rotates among configured API keys on quota exhaustion.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_keys: Sequence[SecretStr],
        model: str,
        dimension: int,
        task_type_document: str,
        task_type_query: str,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._key_pool = _ApiKeyPool(api_keys)
        self._model = model
        self._dimension = dimension
        self._task_type_document = task_type_document
        self._task_type_query = task_type_query
        self._timeout = timeout

    @property
    def model_path(self) -> str:
        return self._model if self._model.startswith("models/") else f"models/{self._model}"

    def _task_type_for(self, kind: EmbeddingTaskKind) -> str:
        return self._task_type_query if kind == "query" else self._task_type_document

    def embed_text(self, text: str, *, kind: EmbeddingTaskKind = "document") -> list[float]:
        return self.embed_texts([text], kind=kind)[0]

    def embed_texts(
        self,
        texts: list[str],
        *,
        kind: EmbeddingTaskKind = "document",
    ) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "requests": [
                {
                    "model": self.model_path,
                    "content": {"parts": [{"text": text}]},
                    "taskType": self._task_type_for(kind),
                    "outputDimensionality": self._dimension,
                }
                for text in texts
            ]
        }

        def _call() -> httpx.Response:
            return self._post_with_rotation(":batchEmbedContents", payload)

        response = embeddings_circuit_breaker.call(lambda: retry_transient_http(_call))
        response.raise_for_status()
        body = response.json()
        embeddings = body.get("embeddings", [])
        vectors = [item.get("values", []) for item in embeddings]
        if len(vectors) != len(texts):
            msg = (
                f"Gemini returned {len(vectors)} embeddings for {len(texts)} inputs; "
                "refusing to align silently."
            )
            raise RuntimeError(msg)
        for vector in vectors:
            if len(vector) != self._dimension:
                msg = f"Embedding dimension mismatch: expected {self._dimension}, got {len(vector)}"
                raise ValueError(msg)
        return [[float(value) for value in vector] for vector in vectors]

    def _post_with_rotation(self, suffix: str, payload: Mapping[str, Any]) -> httpx.Response:
        last_error: httpx.HTTPStatusError | None = None
        attempts = max(1, len(self._key_pool))
        for _ in range(attempts):
            key = self._key_pool.current().get_secret_value()
            url = f"{self._base_url}/{self.model_path}{suffix}?key={key}"
            response = httpx.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self._timeout,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if _is_quota_error(exc) and len(self._key_pool) > 1:
                    last_error = exc
                    self._key_pool.rotate()
                    continue
                raise
            else:
                return response
        if last_error is not None:
            raise last_error
        msg = "Embedding request failed without a captured error."
        raise RuntimeError(msg)


class OpenAICompatibleEmbeddingProvider:
    """Embedding provider for OpenAI-compatible `/embeddings` APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: SecretStr,
        model: str,
        dimension: int,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._dimension = dimension
        self._timeout = timeout

    def embed_text(self, text: str, *, kind: EmbeddingTaskKind = "document") -> list[float]:
        del kind
        return self.embed_texts([text])[0]

    def embed_texts(
        self,
        texts: list[str],
        *,
        kind: EmbeddingTaskKind = "document",
    ) -> list[list[float]]:
        del kind
        if not texts:
            return []
        self._validate_ready()

        response = embeddings_circuit_breaker.call(
            lambda: retry_transient_http(
                lambda: httpx.post(
                    f"{self._base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                    json={"model": self._model, "input": texts},
                    timeout=self._timeout,
                )
            )
        )
        response.raise_for_status()
        payload = response.json()
        vectors = [item["embedding"] for item in payload["data"]]
        for vector in vectors:
            if len(vector) != self._dimension:
                msg = f"Embedding dimension mismatch: expected {self._dimension}, got {len(vector)}"
                raise ValueError(msg)
        return [[float(value) for value in vector] for vector in vectors]

    def _validate_ready(self) -> None:
        if "CHANGEME" in self._base_url or self._api_key.get_secret_value() == "CHANGEME":
            msg = "Embeddings provider is not configured."
            raise ValueError(msg)
        if self._model == "CHANGEME":
            msg = "Embeddings model is not configured."
            raise ValueError(msg)


def build_embedding_provider_from_settings() -> EmbeddingProvider:
    if settings.embeddings_provider == "gemini":
        keys = settings.embeddings_api_keys
        if not keys:
            msg = "EMBEDDINGS_API_KEY (Gemini) is not configured."
            raise ValueError(msg)
        return GeminiEmbeddingProvider(
            base_url=settings.embeddings_base_url,
            api_keys=keys,
            model=settings.embeddings_model,
            dimension=settings.embeddings_dimension,
            task_type_document=settings.embeddings_task_type_document,
            task_type_query=settings.embeddings_task_type_query,
            timeout=settings.http_timeout_seconds,
        )
    return OpenAICompatibleEmbeddingProvider(
        base_url=settings.embeddings_base_url,
        api_key=settings.embeddings_api_key,
        model=settings.embeddings_model,
        dimension=settings.embeddings_dimension,
        timeout=settings.http_timeout_seconds,
    )
