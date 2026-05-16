from __future__ import annotations

import pytest
from pydantic import SecretStr

from cognitive_os.agents.web_search import (
    ExaWebSearchClient,
    build_default_web_search_client,
    configured_web_search_provider_names,
)
from cognitive_os.core.config import Settings


def test_exa_returns_empty_when_key_is_placeholder() -> None:
    client = ExaWebSearchClient(api_key=SecretStr("CHANGEME"))
    assert client.search("foo") == []


def test_configured_provider_names_stable_order_and_subset() -> None:
    settings = Settings(
        tavily_api_key=SecretStr("a"),
        brave_api_key=SecretStr("b"),
        perplexity_api_key=SecretStr("CHANGEME"),
        exa_api_key=SecretStr("ex"),
    )
    assert configured_web_search_provider_names(settings) == [
        "tavily",
        "brave",
        "exa",
    ]


def test_build_default_does_not_scan_web_when_placeholders_explicit() -> None:
    scoped = Settings(
        tavily_api_key=SecretStr("CHANGEME"),
        brave_api_key=SecretStr("CHANGEME"),
        perplexity_api_key=SecretStr("CHANGEME"),
        exa_api_key=SecretStr("CHANGEME"),
    )
    bundled = build_default_web_search_client(scoped)
    assert bundled.search("anything") == []


def test_exa_parses_standard_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(
        *_args,
        **_kwargs,
    ):
        class _Resp:
            def raise_for_status(self) -> None:  # noqa: D401
                return None

            def json(self) -> dict:
                return {
                    "results": [
                        {
                            "title": "T",
                            "url": "https://example.test/a",
                            "text": "main body",
                            "publishedDate": "2024-05-05",
                            "score": 0.94,
                            "highlights": ["short highlight"],
                        }
                    ]
                }

        return _Resp()

    monkeypatch.setattr(
        "cognitive_os.agents.web_search.httpx.post",
        fake_post,
    )
    cli = ExaWebSearchClient(api_key=SecretStr("k"))
    out = cli.search("q")

    assert len(out) == 1
    assert out[0].provider == "exa"
    assert out[0].url.endswith("/a")
    assert "highlight" in out[0].snippet
    assert out[0].score == pytest.approx(0.94)
