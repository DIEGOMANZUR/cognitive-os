from __future__ import annotations

from typing import Any

import pytest
from pydantic import SecretStr

from cognitive_os.memory.embeddings import OpenAICompatibleEmbeddingProvider


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_openai_compatible_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> FakeResponse:
        assert url == "https://embedding.local/embeddings"
        assert headers["Authorization"] == "Bearer test-key"
        assert json == {"model": "embed-test", "input": ["hello", "world"]}
        assert timeout == 30.0
        return FakeResponse(
            {
                "data": [
                    {"embedding": [1, 0, 0]},
                    {"embedding": [0, 1, 0]},
                ]
            }
        )

    monkeypatch.setattr("httpx.post", fake_post)
    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://embedding.local",
        api_key=SecretStr("test-key"),
        model="embed-test",
        dimension=3,
    )

    assert provider.embed_texts(["hello", "world"]) == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


def test_embedding_provider_rejects_placeholder() -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        base_url="CHANGEME",
        api_key=SecretStr("CHANGEME"),
        model="CHANGEME",
        dimension=3,
    )

    with pytest.raises(ValueError, match="not configured"):
        provider.embed_text("hello")
