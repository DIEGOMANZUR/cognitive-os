from __future__ import annotations

from cognitive_os.agents.web_search import (
    MultiProviderWebSearchClient,
    WebSearchClient,
    WebSearchResult,
    canonical_url,
)


class _FixedClient:
    def __init__(self, results: list[WebSearchResult]) -> None:
        self._results = results

    def search(self, query: str) -> list[WebSearchResult]:  # noqa: ARG002
        return list(self._results)


class _FailingClient:
    def search(self, query: str) -> list[WebSearchResult]:  # noqa: ARG002
        msg = "boom"
        raise RuntimeError(msg)


def test_canonical_url_strips_tracking_and_normalizes() -> None:
    a = canonical_url("https://www.Example.COM/path/?utm_source=x&id=42#frag")
    b = canonical_url("HTTPS://example.com/path?id=42&fbclid=zzz")
    assert a == b
    assert "utm_" not in a
    assert "fbclid" not in a


def test_multi_provider_dedupes_and_ranks_by_consensus() -> None:
    tavily = _FixedClient(
        [
            WebSearchResult(
                title="Tav A", url="https://example.com/foo", snippet="x", provider="tavily"
            ),
            WebSearchResult(
                title="Tav B",
                url="https://second.com/bar?utm_campaign=ads",
                snippet="y",
                score=0.7,
                provider="tavily",
            ),
        ]
    )
    brave = _FixedClient(
        [
            WebSearchResult(
                title="Brave A",
                url="https://www.example.com/foo/?utm_source=z",
                snippet="x dup",
                score=0.9,
                provider="brave",
            ),
            WebSearchResult(
                title="Brave C",
                url="https://third.com/baz",
                snippet="z",
                provider="brave",
            ),
        ]
    )
    multi: WebSearchClient = MultiProviderWebSearchClient([tavily, brave], max_results=10)
    results = multi.search("anything")

    assert len(results) == 3
    by_url = {canonical_url(r.url): r for r in results}
    consensus = by_url["https://example.com/foo"]
    # Result returned by 2 providers should keep both tags.
    assert sorted(consensus.all_providers) == ["brave", "tavily"]
    # Best score wins on merge.
    assert consensus.score == 0.9
    # Ranking favors consensus first.
    assert results[0].url.endswith("/foo")


def test_multi_provider_swallows_provider_errors() -> None:
    good = _FixedClient(
        [WebSearchResult(title="t", url="https://ok.com/x", snippet="s", provider="tavily")]
    )
    multi = MultiProviderWebSearchClient([good, _FailingClient()])
    out = multi.search("q")

    assert len(out) == 1
    assert out[0].url == "https://ok.com/x"


def test_multi_provider_no_clients_returns_empty() -> None:
    assert MultiProviderWebSearchClient([]).search("q") == []
