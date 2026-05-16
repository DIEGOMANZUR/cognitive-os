"""Web search providers for Cognitive OS.

We support Tavily, Brave Search, Perplexity and Exa (`EXA_API_KEY`). Each
provider runs in parallel through `MultiProviderWebSearchClient`, which
deduplicates results by canonical URL so DeepAgents and the research subagent
never see the same source twice even when several providers return it.

Design rules:
* Every client returns `WebSearchResult` with a `provider` tag.
* A missing API key is a no-op (`return []`), never an exception, so the
  multi-provider client degrades gracefully when only some keys are set.
* The multi-provider client merges duplicates: if Tavily and Brave both return
  `cnn.com/article-123`, the merged result keeps the best score, the union of
  provider tags, and the first non-empty snippet/date.
* Ranking favors consensus: results returned by more providers float to the
  top, ties broken by score.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from pydantic import BaseModel, Field, SecretStr

from cognitive_os.agents.state import RetrievalCitation
from cognitive_os.core.config import Settings, settings

logger = logging.getLogger(__name__)

_TRACKING_PARAM_PREFIXES: tuple[str, ...] = (
    "utm_",
    "fbclid",
    "gclid",
    "msclkid",
    "yclid",
    "_hsenc",
    "_hsmi",
    "ref",
    "ref_src",
    "mc_cid",
    "mc_eid",
)


class WebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    date: str | None = None
    score: float | None = None
    provider: str = "unknown"
    additional_providers: list[str] = Field(default_factory=list)

    def to_citation(self) -> RetrievalCitation:
        return RetrievalCitation(
            url=self.url,
            title=self.title,
            date=self.date,
            quote=self.snippet,
        )

    @property
    def all_providers(self) -> list[str]:
        return [self.provider, *self.additional_providers]


class WebSearchClient(Protocol):
    def search(self, query: str) -> list[WebSearchResult]:
        """Run a read-only web search."""


def canonical_url(url: str) -> str:
    """Return a comparable canonical form of a URL.

    Lowercases scheme/host, drops `www.`, removes the fragment, strips tracking
    query parameters (utm_*, fbclid, gclid, …), and sorts the remaining query
    so the order doesn't break dedup. Empty/invalid URLs are returned as-is.
    """
    if not url:
        return url
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return url.strip().lower()
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    cleaned_query = sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not any(key.lower().startswith(prefix) for prefix in _TRACKING_PARAM_PREFIXES)
    )
    query = urlencode(cleaned_query)
    return urlunparse((scheme, netloc, path, "", query, ""))


class TavilyWebSearchClient:
    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str = "https://api.tavily.com/search",
        timeout_seconds: float = 15.0,
        max_results: int = 8,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._max_results = max_results

    def search(self, query: str) -> list[WebSearchResult]:
        credential = self._api_key.get_secret_value()
        if not credential or credential == "CHANGEME":
            return []
        response = httpx.post(
            self._base_url,
            json={
                "api_key": credential,
                "query": query,
                "search_depth": "basic",
                "include_answer": False,
                "max_results": self._max_results,
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", [])
        if not isinstance(results, list):
            return []
        return [self._parse_result(item) for item in results if isinstance(item, dict)]

    @staticmethod
    def _parse_result(item: dict[str, object]) -> WebSearchResult:
        title = str(item.get("title") or item.get("url") or "Fuente web")
        url = str(item.get("url") or "")
        snippet = str(item.get("content") or item.get("snippet") or "")
        raw_score = item.get("score")
        score = float(raw_score) if isinstance(raw_score, int | float) else None
        raw_date = item.get("published_date") or item.get("date")
        date = str(raw_date) if raw_date is not None else None
        return WebSearchResult(
            title=title, url=url, snippet=snippet, date=date, score=score, provider="tavily"
        )


class BraveWebSearchClient:
    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str = "https://api.search.brave.com/res/v1/web/search",
        timeout_seconds: float = 15.0,
        max_results: int = 8,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._max_results = max_results

    def search(self, query: str) -> list[WebSearchResult]:
        credential = self._api_key.get_secret_value()
        if not credential or credential == "CHANGEME":
            return []
        response = httpx.get(
            self._base_url,
            params={
                "q": query,
                "count": self._max_results,
                "safesearch": "moderate",
                "result_filter": "web",
            },
            headers={
                "X-Subscription-Token": credential,
                "Accept": "application/json",
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        results: list[WebSearchResult] = []
        web_block = body.get("web") or {}
        for item in (web_block.get("results") or [])[: self._max_results]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            if not url:
                continue
            results.append(
                WebSearchResult(
                    title=str(item.get("title") or url),
                    url=url,
                    snippet=str(item.get("description") or ""),
                    date=str(item.get("age")) if item.get("age") else None,
                    score=None,
                    provider="brave",
                )
            )
        return results


class PerplexityWebSearchClient:
    """Perplexity Sonar wrapper.

    Perplexity does not expose a "search" endpoint; instead it exposes
    `chat/completions` with online models that include citations. We use the
    answer body as the snippet for every cited URL — the provider's own
    grounding is the source of truth. Citations are extracted both from the
    legacy `citations` (list[str]) and the newer `search_results` shapes.
    """

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str = "https://api.perplexity.ai",
        model: str = "sonar",
        timeout_seconds: float = 20.0,
        max_results: int = 8,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_results = max_results

    def search(self, query: str) -> list[WebSearchResult]:
        credential = self._api_key.get_secret_value()
        if not credential or credential == "CHANGEME":
            return []
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {credential}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a search assistant. Answer concisely and always cite "
                            "the sources you used. Do not invent."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                "return_citations": True,
                "max_tokens": 600,
                "temperature": 0.2,
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        choices = body.get("choices") or []
        answer_snippet = ""
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            answer_snippet = str(message.get("content") or "")[:500]

        citations = body.get("citations") or body.get("search_results") or []
        results: list[WebSearchResult] = []
        for citation in list(citations)[: self._max_results]:
            if isinstance(citation, str):
                results.append(
                    WebSearchResult(
                        title=citation,
                        url=citation,
                        snippet=answer_snippet,
                        date=None,
                        score=None,
                        provider="perplexity",
                    )
                )
            elif isinstance(citation, dict):
                url = str(citation.get("url") or "")
                if not url:
                    continue
                results.append(
                    WebSearchResult(
                        title=str(citation.get("title") or url),
                        url=url,
                        snippet=str(citation.get("snippet") or answer_snippet),
                        date=(
                            str(citation.get("date") or citation.get("published_date") or "")
                            or None
                        ),
                        score=None,
                        provider="perplexity",
                    )
                )
        return results


class ExaWebSearchClient:
    """Exa semantic search (https://api.exa.ai/search)."""

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str = "https://api.exa.ai/search",
        timeout_seconds: float = 18.0,
        max_results: int = 8,
        search_type: str = "auto",
        text_max_chars: int = 480,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_results = max_results
        self._search_type = search_type
        self._text_max_chars = max(64, text_max_chars)

    def search(self, query: str) -> list[WebSearchResult]:
        credential = self._api_key.get_secret_value()
        if not credential or credential == "CHANGEME":
            return []
        response = httpx.post(
            f"{self._base_url}",
            headers={"x-api-key": credential, "Content-Type": "application/json"},
            json={
                "query": query,
                "type": self._search_type,
                "numResults": self._max_results,
                # Short text excerpts keep latency and token cost predictable.
                "contents": {"text": {"maxCharacters": self._text_max_chars}},
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        rows = body.get("results") or []
        if not isinstance(rows, list):
            return []
        out: list[WebSearchResult] = []
        for item in rows[: self._max_results]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            if not url:
                continue
            title = str(item.get("title") or url)
            text = str(item.get("text") or "")
            snippet = ""
            hl = item.get("highlights")
            if isinstance(hl, list) and hl:
                snippet = str(hl[0] or "").strip()
            if not snippet and text.strip():
                snippet = text.strip()[:800]
            if not snippet and isinstance(item.get("summary"), str):
                snippet = str(item["summary"]).strip()
            pub = item.get("publishedDate")
            date_str = str(pub).strip() if pub is not None else None
            score_raw = item.get("score")
            score = float(score_raw) if isinstance(score_raw, int | float) else None
            out.append(
                WebSearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    date=date_str,
                    score=score,
                    provider="exa",
                )
            )
        return out


class MultiProviderWebSearchClient:
    """Run several `WebSearchClient`s in parallel and dedup by canonical URL.

    Failures from any single provider are logged and dropped — the rest of
    the providers still contribute. Empty providers (missing key) silently
    return `[]`.
    """

    def __init__(
        self,
        clients: Sequence[WebSearchClient],
        *,
        per_provider_timeout_seconds: float = 20.0,
        max_results: int = 10,
    ) -> None:
        self._clients = list(clients)
        self._per_provider_timeout = per_provider_timeout_seconds
        self._max_results = max_results

    def search(self, query: str) -> list[WebSearchResult]:
        if not self._clients:
            return []
        per_provider: list[list[WebSearchResult]] = []
        with ThreadPoolExecutor(max_workers=max(1, len(self._clients))) as executor:
            future_to_name = {
                executor.submit(client.search, query): client.__class__.__name__
                for client in self._clients
            }
            try:
                completed_iter = list(
                    as_completed(future_to_name, timeout=self._per_provider_timeout)
                )
            except TimeoutError:
                completed_iter = list(future_to_name.keys())
            for future in completed_iter:
                name = future_to_name[future]
                try:
                    per_provider.append(list(future.result(timeout=0)))
                except Exception as exc:
                    logger.warning(
                        "web_search_provider_failed", extra={"provider": name, "error": str(exc)}
                    )
        return _merge_and_rank(per_provider, max_results=self._max_results)


def _merge_and_rank(
    per_provider: Sequence[Sequence[WebSearchResult]],
    *,
    max_results: int,
) -> list[WebSearchResult]:
    merged: dict[str, WebSearchResult] = {}
    for batch in per_provider:
        for result in batch:
            if not result.url:
                continue
            canonical = canonical_url(result.url)
            existing = merged.get(canonical)
            if existing is None:
                merged[canonical] = result
                continue
            existing_providers = existing.all_providers
            new_providers = [p for p in result.all_providers if p not in existing_providers]
            if not new_providers:
                continue
            scores = [s for s in (existing.score, result.score) if s is not None]
            best_score = max(scores) if scores else None
            merged[canonical] = existing.model_copy(
                update={
                    "additional_providers": [
                        *existing.additional_providers,
                        *new_providers,
                    ],
                    "snippet": existing.snippet or result.snippet,
                    "date": existing.date or result.date,
                    "score": best_score,
                }
            )
    ranked = sorted(
        merged.values(),
        key=lambda item: (
            len(item.all_providers),
            item.score if item.score is not None else 0.0,
        ),
        reverse=True,
    )
    return ranked[:max_results]


def build_default_web_search_client(
    app_settings: Settings = settings,
) -> MultiProviderWebSearchClient:
    """Wire the providers configured in `Settings` into a multi-provider client.

    Tavily, Brave (`BRAVE_API_KEY`), Perplexity and Exa (`EXA_API_KEY`) are
    included when their key is present and not `CHANGEME`. Returns a client with
    the available subset; if every key is missing the result is a client with no
    providers (`search()` returns `[]`).
    """
    clients: list[WebSearchClient] = []
    if _is_real_key(app_settings.tavily_api_key):
        clients.append(TavilyWebSearchClient(api_key=app_settings.tavily_api_key))
    if _is_real_key(app_settings.brave_api_key):
        clients.append(BraveWebSearchClient(api_key=app_settings.brave_api_key))
    if _is_real_key(app_settings.perplexity_api_key):
        clients.append(
            PerplexityWebSearchClient(
                api_key=app_settings.perplexity_api_key,
                base_url=app_settings.perplexity_base_url,
            )
        )
    if _is_real_key(app_settings.exa_api_key):
        clients.append(ExaWebSearchClient(api_key=app_settings.exa_api_key))
    return MultiProviderWebSearchClient(clients)


def configured_web_search_provider_names(app_settings: Settings = settings) -> list[str]:
    """Names of configured providers (keys set), irrespective of WEB_SEARCH_ENABLED."""
    names: list[str] = []
    if _is_real_key(app_settings.tavily_api_key):
        names.append("tavily")
    if _is_real_key(app_settings.brave_api_key):
        names.append("brave")
    if _is_real_key(app_settings.perplexity_api_key):
        names.append("perplexity")
    if _is_real_key(app_settings.exa_api_key):
        names.append("exa")
    return names


def _is_real_key(secret: SecretStr) -> bool:
    value = secret.get_secret_value().strip()
    return bool(value) and value != "CHANGEME"
