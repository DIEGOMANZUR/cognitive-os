"""Shared test fixtures.

Hermetic-by-default LLM guard
-----------------------------
Unit tests must never make real network calls to an LLM. Several tests
exercise the full LangGraph graph (`build_graph(...).invoke(...)` or the
`/chat` endpoints). The graph's router (`route_request`) calls the model
factories and, if they fail, falls back to the deterministic router; the
DeepAgent path uses an injected runner that tests stub.

Historically these tests "passed" only because the configured model
fast-failed (e.g. a 4xx in milliseconds) which dropped the router into the
deterministic path. Once a working tool-capable model was configured the
same tests started making real, slow, non-deterministic network calls and
flaked/timed out.

This autouse fixture makes every model factory raise by default, so the
router deterministically uses `deterministic_route` and the DeepAgent
factory never opens a socket. Tests that *want* an LLM:

* inject `router_llm=FakeRouterLLM(...)` into `build_graph` (the router
  then never touches the factories), or
* `monkeypatch.setattr(...create_*_chat_model, fake)` inside the test
  body (runs after this fixture, so the test's stub wins).

Integration tests (`-m integration`) are excluded from the default suite
and may opt back into real calls.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

_ROUTER_FACTORIES = (
    "create_agent_chat_model",
    "create_secondary_chat_model",
    "create_primary_chat_model",
    "create_fallback_chat_model",
)


@pytest.fixture(autouse=True)
def _disable_real_llm_factories(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Force every LLM model factory to raise so unit tests stay hermetic."""
    if request.node.get_closest_marker("integration") or request.node.get_closest_marker("slow"):
        yield
        return

    def _blocked(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError(
            "Real LLM factory disabled in unit tests (hermetic). Inject "
            "router_llm / deepagent_runner or monkeypatch the factory in the test."
        )

    for _name in _ROUTER_FACTORIES:
        monkeypatch.setattr(f"cognitive_os.agents.graph.{_name}", _blocked, raising=False)
    monkeypatch.setattr(
        "cognitive_os.deepagents.factory.create_agent_chat_model", _blocked, raising=False
    )
    yield
