from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

import cognitive_os.api.app as api_app
from cognitive_os.agents.graph import build_graph
from cognitive_os.agents.research import ReadOnlyResearchTools, ResearchAgent
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token, decode_jwt
from cognitive_os.core.health import ComponentHealth, HealthDashboard
from cognitive_os.deepagents.schemas import DeepAgentResult, DeepAgentTask


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


class EmptyWebClient:
    def search(self, query: str) -> list[object]:
        del query
        return []


def _failed_deepagent_runner(task: DeepAgentTask) -> DeepAgentResult:
    return DeepAgentResult(
        task_id=task.task_id,
        thread_id=task.thread_id,
        status="failed",
        answer="mocked failure",
        findings=[],
        citations=[],
        uncertainty_notes=["mocked"],
        generated_files=[],
        requested_external_actions=[],
        raw_summary=None,
    )


@pytest.mark.asyncio
async def test_health_is_public() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "cognitive-os"}


@pytest.mark.asyncio
async def test_local_token_bootstrap_requires_dedicated_local_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_app.settings, "operator_profile", "strict")
    monkeypatch.setattr(api_app.settings, "local_autonomy_mode", "full")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/local-token")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_local_token_bootstrap_mints_admin_operator_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_app.settings, "operator_profile", "dedicated_local")
    monkeypatch.setattr(api_app.settings, "local_autonomy_mode", "full")
    monkeypatch.setattr(api_app.settings, "auth_default_roles", ["operator"])
    monkeypatch.setattr(api_app.settings, "auth_admin_roles", ["admin"])
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/local-token")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    payload = decode_jwt(body["access_token"])
    assert body["token_type"] == "bearer"
    assert body["user_id"] == "local-operator"
    assert set(body["roles"]) == {"admin", "operator"}
    assert payload["sub"] == "local-operator"
    assert set(payload["roles"]) == {"admin", "operator"}


@pytest.mark.asyncio
async def test_chat_requires_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/chat", json={"message": "hola"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_and_thread_roundtrip_with_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    # Router stays deterministic via the autouse hermetic guard in
    # tests/conftest.py (no real LLM network call); `deepagent_runner` is
    # stubbed below so the research path falls to the deterministic RAG reply.
    test_graph = build_graph(
        checkpointer=api_app.MemorySaver(),
        retriever=api_app._empty_retriever,
        research_agent=ResearchAgent(
            tools=ReadOnlyResearchTools(
                local_search=api_app._empty_retriever,
                web_client=EmptyWebClient(),
            )
        ),
        deepagent_runner=_failed_deepagent_runner,
    )
    monkeypatch.setattr(api_app, "_api_graph", test_graph)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        chat_response = await client.post(
            "/chat",
            json={"message": "investiga sin documentos"},
            headers=_headers(),
        )
        thread_id = chat_response.json()["thread_id"]
        thread_response = await client.get(f"/threads/{thread_id}", headers=_headers())

    assert chat_response.status_code == 200
    assert chat_response.json()["route"] == "research"
    assert "No hay evidencia suficiente" in chat_response.json()["message"]
    assert thread_response.status_code == 200
    assert thread_response.json()["thread_id"] == thread_id


@pytest.mark.asyncio
async def test_protected_job_endpoint_rejects_missing_auth_before_db_access() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/jobs/11111111-1111-1111-1111-111111111111")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_dashboard_requires_auth_and_returns_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_dashboard() -> HealthDashboard:
        return HealthDashboard(
            status="ok",
            checked_at=datetime.now(UTC),
            components=[ComponentHealth(name="postgres", status="ok")],
        )

    monkeypatch.setattr(api_app, "check_health_dashboard", fake_dashboard)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.get("/health/dashboard")
        authorized = await client.get("/health/dashboard", headers=_headers())

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["components"][0]["name"] == "postgres"


@pytest.mark.asyncio
async def test_public_config_requires_auth_and_exposes_operator_flags() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unauthorized = await client.get("/config/public")
        authorized = await client.get("/config/public", headers=_headers())

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    payload = authorized.json()
    assert payload["primary_llm_model"] == api_app.settings.primary_llm_model
    assert "mail_enabled" in payload
    assert "mail_imap_timeout_seconds" in payload
    assert "enable_openharness_research" in payload
    assert "godaddy_dns_dry_run_only" in payload
    assert "langsmith_endpoints_require_admin" in payload
    assert "enable_maps_routing" in payload
    assert "enable_google_calendar" in payload
    assert "enable_google_drive" in payload
    assert "google_drive_deliverables_folder_name" in payload


@pytest.mark.asyncio
async def test_public_config_does_not_expose_secret_shaped_keys() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/config/public", headers=_headers())

    assert response.status_code == 200
    forbidden = ("secret", "token", "password", "api_key", "database_url", "client_secret")
    for key in response.json():
        assert not any(fragment in key.lower() for fragment in forbidden), key


@pytest.mark.asyncio
async def test_episodic_memory_requires_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/deepagents/memory/episodic",
            json={"summary": "1234567890abcdefghijklmnop"},  # pragma: allowlist secret
        )

    assert resp.status_code == 401
