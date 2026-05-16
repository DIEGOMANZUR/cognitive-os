from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import structlog

from cognitive_os.memory.weaviate_store import SearchResult

logger = structlog.get_logger(__name__)


class LocalReranker:
    """Optional lazy local reranker with lexical fallback."""

    def __init__(self, *, enabled: bool, model_name: str) -> None:
        self._enabled = enabled
        self._model_name = model_name
        self._model: Any | None = None
        self._model_load_attempted = False

    def rerank(self, query: str, results: Sequence[SearchResult], limit: int) -> list[SearchResult]:
        if not results:
            return []
        if not self._enabled:
            return list(results[:limit])

        model_scores = self._try_model_scores(query, results)
        if model_scores is not None:
            ranked = sorted(
                zip(results, model_scores, strict=True),
                key=lambda item: item[1],
                reverse=True,
            )
            return [result for result, _score in ranked[:limit]]

        return sorted(
            results,
            key=lambda result: self._lexical_score(query, result.text),
            reverse=True,
        )[:limit]

    def _try_model_scores(
        self,
        query: str,
        results: Sequence[SearchResult],
    ) -> list[float] | None:
        model = self._load_model()
        if model is None:
            return None
        pairs = [(query, result.text) for result in results]
        try:
            scores = model.predict(pairs)
        except Exception as exc:  # noqa: BLE001 - degrades silently to lexical
            logger.warning(
                "reranker_inference_failed",
                error_type=type(exc).__name__,
                error=str(exc),
                model_name=self._model_name,
                result_count=len(results),
            )
            return None
        return [float(score) for score in scores]

    def _load_model(self) -> Any | None:
        if self._model_load_attempted:
            return self._model

        self._model_load_attempted = True
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]

            self._model = CrossEncoder(self._model_name, local_files_only=True)
        except Exception as exc:  # noqa: BLE001 - degrades silently to lexical
            logger.warning(
                "reranker_model_load_failed",
                error_type=type(exc).__name__,
                error=str(exc),
                model_name=self._model_name,
            )
            self._model = None
        return self._model

    def _lexical_score(self, query: str, text: str) -> float:
        """Lexical-overlap fallback ranker (Spanish-aware token normalization).

        The previous implementation split on whitespace and lowercased, which is
        near-random for Spanish: `evaluación` and `evaluacion` never matched,
        and stopwords like `de`/`la`/`el` dominated the overlap. This version
        strips diacritics, splits on non-alphanumerics, and ignores a small
        Spanish/English stoplist. Still cheap and deterministic.
        """
        query_terms = _tokenize(query)
        if not query_terms:
            return 0.0
        text_terms = _tokenize(text)
        return len(query_terms & text_terms) / len(query_terms)


_STOPWORDS = frozenset(
    {
        "a",
        "al",
        "an",
        "and",
        "but",
        "con",
        "de",
        "del",
        "el",
        "en",
        "es",
        "for",
        "in",
        "la",
        "las",
        "los",
        "of",
        "or",
        "para",
        "por",
        "que",
        "se",
        "the",
        "to",
        "un",
        "una",
        "unas",
        "unos",
        "with",
        "y",
    }
)


def _tokenize(value: str) -> set[str]:
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    tokens = re.findall(r"[a-z0-9]+", normalized.lower())
    return {token for token in tokens if len(token) >= 3 and token not in _STOPWORDS}
