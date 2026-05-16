from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from cognitive_os.actions.captcha import (
    CapSolverHttpProvider,
    CaptchaSolverError,
    CaptchaSolverService,
    FakeCaptchaProvider,
    _extract_token,
    _redact,
)
from cognitive_os.api.app import app
from cognitive_os.core.config import Settings


def _settings(*, enabled: bool = True, key: str = "CAP-REALKEY1234567890") -> Settings:
    return Settings.model_construct(
        enable_captcha_solving=enabled,
        capsolver_api_key=SecretStr(key),
        capsolver_base_url="https://api.capsolver.com",
        capsolver_poll_interval_seconds=0.0,
        capsolver_max_poll_seconds=10,
        http_timeout_seconds=5.0,
    )


def test_status_disabled_blocked_ready() -> None:
    assert CaptchaSolverService(app_settings=_settings(enabled=False)).status().status == (
        "disabled"
    )
    assert CaptchaSolverService(app_settings=_settings(key="CHANGEME")).status().status == (
        "blocked"
    )
    ready = CaptchaSolverService(app_settings=_settings()).status()
    assert ready.status == "ready"
    assert ready.base_url == "https://api.capsolver.com"


def test_solve_image_blocked_when_disabled() -> None:
    svc = CaptchaSolverService(
        provider=FakeCaptchaProvider(),
        app_settings=_settings(enabled=False),
    )
    with pytest.raises(CaptchaSolverError, match="ENABLE_CAPTCHA_SOLVING"):
        svc.solve_image("aGVsbG8=")


def test_solve_image_returns_text_inline() -> None:
    provider = FakeCaptchaProvider(create_response={"errorId": 0, "solution": {"text": "AB12CD"}})
    svc = CaptchaSolverService(provider=provider, app_settings=_settings())
    solution = svc.solve_image("aGVsbG8=")
    assert solution.kind == "image_to_text"
    assert solution.token == "AB12CD"
    # ImageToText must NOT poll getTaskResult.
    assert provider.result_calls == []
    assert provider.create_calls[0]["type"] == "ImageToTextTask"
    assert provider.create_calls[0]["body"] == "aGVsbG8="


def test_solve_image_strips_data_uri_prefix() -> None:
    provider = FakeCaptchaProvider(create_response={"errorId": 0, "solution": {"text": "X"}})
    svc = CaptchaSolverService(provider=provider, app_settings=_settings())
    svc.solve_image("data:image/png;base64,RAWBYTES==")
    assert provider.create_calls[0]["body"] == "RAWBYTES=="


def test_solve_image_rejects_empty() -> None:
    svc = CaptchaSolverService(provider=FakeCaptchaProvider(), app_settings=_settings())
    with pytest.raises(CaptchaSolverError, match="must not be empty"):
        svc.solve_image("   ")


def test_solve_image_surfaces_capsolver_error() -> None:
    provider = FakeCaptchaProvider(
        create_response={
            "errorId": 1,
            "errorCode": "ERROR_KEY_DENIED_ACCESS",
            "errorDescription": "bad key",
        }
    )
    svc = CaptchaSolverService(provider=provider, app_settings=_settings())
    with pytest.raises(CaptchaSolverError, match="ERROR_KEY_DENIED_ACCESS"):
        svc.solve_image("aGk=")


def test_solve_token_polls_until_ready() -> None:
    provider = FakeCaptchaProvider(
        create_response={"errorId": 0, "taskId": "task-9"},
        result_responses=[
            {"errorId": 0, "status": "processing"},
            {"errorId": 0, "status": "processing"},
            {"errorId": 0, "status": "ready", "solution": {"gRecaptchaResponse": "TOK99"}},
        ],
    )
    svc = CaptchaSolverService(provider=provider, app_settings=_settings())
    solution = svc.solve_token(
        "recaptcha_v2",
        website_url="https://example.com",
        website_key="6Lc-sitekey",
    )
    assert solution.token == "TOK99"
    assert solution.task_id == "task-9"
    assert provider.result_calls == ["task-9", "task-9", "task-9"]
    assert provider.create_calls[0]["type"] == "ReCaptchaV2TaskProxyLess"


def test_solve_token_recaptcha_v3_sets_page_action() -> None:
    provider = FakeCaptchaProvider(
        create_response={"errorId": 0, "taskId": "t"},
        result_responses=[{"errorId": 0, "status": "ready", "solution": {"token": "v3tok"}}],
    )
    svc = CaptchaSolverService(provider=provider, app_settings=_settings())
    sol = svc.solve_token(
        "recaptcha_v3",
        website_url="https://x.com",
        website_key="k",
        page_action="login",
    )
    assert sol.token == "v3tok"
    assert provider.create_calls[0]["type"] == "ReCaptchaV3TaskProxyLess"
    assert provider.create_calls[0]["pageAction"] == "login"


def test_solve_token_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    # Provider that NEVER reaches "ready" (custom fake so exhaustion can't
    # accidentally fall back to a ready default).
    class _AlwaysProcessing:
        def create_task(self, task: dict[str, Any]) -> dict[str, Any]:
            return {"errorId": 0, "taskId": "slow"}

        def get_task_result(self, task_id: str) -> dict[str, Any]:
            return {"errorId": 0, "status": "processing"}

    # Deterministic clock: each monotonic() read jumps 60s so the 10s deadline
    # is exceeded on the second poll regardless of real wall-clock.
    import cognitive_os.actions.captcha as captcha_mod

    ticks = iter([0.0, 60.0, 120.0, 180.0, 240.0])
    monkeypatch.setattr(captcha_mod.time, "monotonic", lambda: next(ticks))
    svc = CaptchaSolverService(
        provider=_AlwaysProcessing(),
        app_settings=_settings(),
        sleep=lambda _s: None,
    )
    with pytest.raises(CaptchaSolverError, match="did not solve"):
        svc.solve_token(
            "turnstile",
            website_url="https://cf.com",
            website_key="0x4",
        )


def test_solve_token_rejects_non_token_kind() -> None:
    svc = CaptchaSolverService(provider=FakeCaptchaProvider(), app_settings=_settings())
    with pytest.raises(CaptchaSolverError, match="not a token captcha"):
        svc.solve_token(
            "image_to_text",  # type: ignore[arg-type]
            website_url="https://x.com",
            website_key="k",
        )


def test_redact_strips_capsolver_key() -> None:
    # pragma: allowlist nextline secret
    capsolver_like = "CAP-" + "FD160D382D9BC71A86225E11A269D71229AE972EA6"
    leaked = f"fail clientKey={capsolver_like}"
    assert capsolver_like not in _redact(leaked)
    assert "[REDACTED]" in _redact(leaked)


def test_extract_token_prefers_known_keys() -> None:
    assert _extract_token({"gRecaptchaResponse": "a"}) == "a"
    assert _extract_token({"token": "b"}) == "b"
    assert _extract_token({"text": "c"}) == "c"
    with pytest.raises(CaptchaSolverError, match="usable token"):
        _extract_token({"nothing": "x"})


def test_http_provider_sends_client_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return httpx.Response(
            200, json={"errorId": 0, "taskId": "z"}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = CapSolverHttpProvider(_settings())
    provider.create_task({"type": "ImageToTextTask", "body": "x"})
    assert captured["url"] == "https://api.capsolver.com/createTask"
    assert captured["json"]["clientKey"] == "CAP-REALKEY1234567890"  # pragma: allowlist secret
    assert captured["json"]["task"] == {"type": "ImageToTextTask", "body": "x"}


def test_http_provider_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(CaptchaSolverError, match="invalid JSON"):
        CapSolverHttpProvider(_settings()).get_task_result("t")


@pytest.mark.asyncio
async def test_captcha_endpoints_require_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        s = await client.get("/actions/captcha/status")
        i = await client.post("/actions/captcha/image", json={"image_base64": "aGk="})
        t = await client.post(
            "/actions/captcha/token",
            json={
                "kind": "recaptcha_v2",
                "website_url": "https://x.com",
                "website_key": "k",
            },
        )
    assert s.status_code == 401
    assert i.status_code == 401
    assert t.status_code == 401
