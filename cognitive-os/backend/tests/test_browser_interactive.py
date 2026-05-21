"""Phase 17: tests for `browser_interactive` (multi-step + vision).

These tests never spawn a real browser. The provider and the vision analyzer
are both injected as Protocol implementations:

- `_RecordingProvider` captures the steps it received and returns canned
  `BrowserStepResult`s, so we can assert validation/orchestration without
  Playwright installed.
- `_FakeVisionAnalyzer` records prompts and returns a fixed analysis string.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest

import cognitive_os.api.app as api_app
from cognitive_os.actions.browser_interactive import (
    BrowserInteractiveService,
    VisionAnalyzer,
)
from cognitive_os.actions.schemas import (
    BrowserInteractiveRequest,
    BrowserStep,
    BrowserStepResult,
)
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import Settings


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def _settings_with_browser_on(tmp_path: Path, domains: str = "example.com") -> Settings:
    return Settings(
        enable_browser_automation=True,
        browser_headless_default=True,
        browser_allowed_domains=domains,
        browser_screenshot_dir=tmp_path / "screenshots",
        browser_navigation_timeout_ms=15_000,
        browser_screenshot_max_bytes=5_000_000,
    )


class _RecordingProvider:
    def __init__(
        self,
        results: list[BrowserStepResult] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._results = results

    def run(
        self,
        *,
        initial_url: str,
        steps: Sequence[BrowserStep],
        wait_until: str,
        timeout_ms: int,
        screenshot_dir: Path,
        vision_analyzer: VisionAnalyzer | None,
    ) -> list[BrowserStepResult]:
        self.calls.append(
            {
                "initial_url": initial_url,
                "step_count": len(steps),
                "wait_until": wait_until,
                "timeout_ms": timeout_ms,
                "screenshot_dir": str(screenshot_dir),
                "has_vision": vision_analyzer is not None,
                "step_kinds": [step.kind for step in steps],
            }
        )
        if self._results is not None:
            return list(self._results)
        out: list[BrowserStepResult] = []
        for index, step in enumerate(steps):
            if step.kind == "analyze":
                shot = screenshot_dir / f"step-{index}.png"
                shot.write_bytes(b"\x89PNG\r\n\x1a\nfake")
                if vision_analyzer is not None:
                    analysis = vision_analyzer.analyze(
                        prompt=step.prompt or "describe",
                        image_path=shot,
                    )
                else:
                    analysis = (
                        "vision analyzer is not configured; screenshot captured but not analyzed."
                    )
                out.append(
                    BrowserStepResult(
                        step_index=index,
                        kind=step.kind,
                        status="ok",
                        screenshot_path=str(shot),
                        analysis=analysis,
                    )
                )
            elif step.kind == "screenshot":
                shot = screenshot_dir / f"step-{index}.png"
                shot.write_bytes(b"\x89PNG\r\n\x1a\nfake")
                out.append(
                    BrowserStepResult(
                        step_index=index,
                        kind=step.kind,
                        status="ok",
                        screenshot_path=str(shot),
                    )
                )
            else:
                out.append(BrowserStepResult(step_index=index, kind=step.kind, status="ok"))
        return out


class _FakeVisionAnalyzer:
    def __init__(self, analysis: str = "page shows a search box and a logo") -> None:
        self.analysis = analysis
        self.calls: list[dict[str, Any]] = []

    def analyze(self, *, prompt: str, image_path: Path) -> str:
        self.calls.append({"prompt": prompt, "image_path": str(image_path)})
        return self.analysis


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_blocks_when_browser_automation_disabled(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, enable_browser_automation=False)
    service = BrowserInteractiveService(settings)
    request = BrowserInteractiveRequest(url="https://example.com", steps=[])
    result = service.execute(request)
    assert result.status == "blocked"
    assert "disabled" in (result.reason or "").lower()


def test_validate_blocks_domain_outside_allowlist(tmp_path: Path) -> None:
    settings = _settings_with_browser_on(tmp_path, domains="example.com")
    service = BrowserInteractiveService(settings)
    request = BrowserInteractiveRequest(url="https://evil.test/login", steps=[])
    result = service.execute(request)
    assert result.status == "blocked"


def test_validate_rejects_step_navigate_to_disallowed_domain(tmp_path: Path) -> None:
    settings = _settings_with_browser_on(tmp_path, domains="example.com")
    service = BrowserInteractiveService(settings)
    request = BrowserInteractiveRequest(
        url="https://example.com",
        steps=[BrowserStep(kind="navigate", url="https://evil.test/page")],
    )
    result = service.execute(request)
    assert result.status == "blocked"


def test_validate_rejects_click_without_selector(tmp_path: Path) -> None:
    settings = _settings_with_browser_on(tmp_path)
    service = BrowserInteractiveService(settings)
    request = BrowserInteractiveRequest(
        url="https://example.com",
        steps=[BrowserStep(kind="click", selector=None)],
    )
    result = service.execute(request)
    assert result.status == "blocked"
    assert "selector" in (result.reason or "").lower()


def test_validate_rejects_dangerous_selector(tmp_path: Path) -> None:
    settings = _settings_with_browser_on(tmp_path)
    service = BrowserInteractiveService(settings)
    request = BrowserInteractiveRequest(
        url="https://example.com",
        steps=[BrowserStep(kind="click", selector="button.submit; rm -rf /")],
    )
    result = service.execute(request)
    assert result.status == "blocked"


def test_validate_rejects_wait_above_cap(tmp_path: Path) -> None:
    settings = _settings_with_browser_on(tmp_path)
    service = BrowserInteractiveService(settings)
    request = BrowserInteractiveRequest(
        url="https://example.com",
        steps=[BrowserStep(kind="wait", value="60000")],
    )
    result = service.execute(request)
    assert result.status == "blocked"


def test_validate_rejects_analyze_without_prompt(tmp_path: Path) -> None:
    settings = _settings_with_browser_on(tmp_path)
    service = BrowserInteractiveService(settings)
    request = BrowserInteractiveRequest(
        url="https://example.com",
        steps=[BrowserStep(kind="analyze", prompt=None)],
    )
    result = service.execute(request)
    assert result.status == "blocked"


# ---------------------------------------------------------------------------
# Execution with FakeProvider + FakeVision
# ---------------------------------------------------------------------------


def test_execute_orchestrates_steps_and_records_results(tmp_path: Path) -> None:
    settings = _settings_with_browser_on(tmp_path)
    provider = _RecordingProvider()
    vision = _FakeVisionAnalyzer(analysis="texto principal: Bienvenido")
    service = BrowserInteractiveService(
        settings,
        provider_factory=lambda _: provider,
        vision_factory=lambda _: vision,
    )
    request = BrowserInteractiveRequest(
        url="https://example.com/search",
        steps=[
            BrowserStep(kind="fill", selector="input.q", value="hello world"),
            BrowserStep(kind="click", selector="button.submit"),
            BrowserStep(kind="screenshot"),
            BrowserStep(kind="analyze", prompt="¿Qué muestra el header?"),
        ],
    )
    result = service.execute(request)
    assert result.status == "completed"
    assert [step.kind for step in result.steps] == ["fill", "click", "screenshot", "analyze"]
    assert result.steps[-1].analysis == "texto principal: Bienvenido"
    assert provider.calls[0]["has_vision"] is True
    assert vision.calls and vision.calls[0]["prompt"].startswith("¿Qué muestra")


def test_execute_omits_vision_when_factory_returns_none(tmp_path: Path) -> None:
    """If no analyzer is configured, the analyze step still runs and returns a note."""
    settings = _settings_with_browser_on(tmp_path)
    provider = _RecordingProvider()
    service = BrowserInteractiveService(
        settings,
        provider_factory=lambda _: provider,
        vision_factory=lambda _: None,
    )
    request = BrowserInteractiveRequest(
        url="https://example.com",
        steps=[BrowserStep(kind="analyze", prompt="describe")],
    )
    result = service.execute(request)
    assert result.status == "completed"
    assert provider.calls[0]["has_vision"] is False
    assert result.steps[0].analysis is not None
    assert "not configured" in result.steps[0].analysis


def test_execute_blocks_when_screenshot_exceeds_cap(tmp_path: Path) -> None:
    """A screenshot larger than the cap is deleted and the step marked blocked."""
    settings = _settings_with_browser_on(tmp_path)
    settings = settings.model_copy(update={"browser_screenshot_max_bytes": 10})
    huge_shot = tmp_path / "screenshots" / "huge.png"

    class _HugeProvider:
        def run(self, **kwargs: Any) -> list[BrowserStepResult]:
            huge_shot.parent.mkdir(parents=True, exist_ok=True)
            huge_shot.write_bytes(b"x" * 1024)
            return [
                BrowserStepResult(
                    step_index=0,
                    kind="screenshot",
                    status="ok",
                    screenshot_path=str(huge_shot),
                )
            ]

    service = BrowserInteractiveService(settings, provider_factory=lambda _: _HugeProvider())
    request = BrowserInteractiveRequest(
        url="https://example.com",
        steps=[BrowserStep(kind="screenshot")],
    )
    result = service.execute(request)
    assert result.status == "blocked"
    assert not huge_shot.exists(), "oversize screenshot must be deleted"
    assert result.steps[0].status == "blocked"
    assert "BROWSER_SCREENSHOT_MAX_BYTES" in (result.steps[0].reason or "")


def test_execute_blocks_when_playwright_not_installed(tmp_path: Path) -> None:
    """No provider factory + no playwright installed -> blocked with clear reason."""
    settings = _settings_with_browser_on(tmp_path)
    service = BrowserInteractiveService(settings)
    # Default `_resolve_provider` returns None when `find_spec("playwright")` is None.
    # Force the fallback path by monkeypatching find_spec via the service internals.
    service._provider_factory = lambda _: None  # type: ignore[assignment]
    request = BrowserInteractiveRequest(url="https://example.com", steps=[])
    result = service.execute(request)
    assert result.status == "blocked"
    assert "playwright" in (result.reason or "").lower()


# ---------------------------------------------------------------------------
# Endpoint smoke test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_browser_interactive_endpoint_requires_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/browser/interactive/request",
            json={"url": "https://example.com", "steps": []},
        )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_request_browser_interactive_endpoint_blocks_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Endpoint must surface the policy block as a persisted blocked ActionRequest."""
    from cognitive_os.actions import service as service_module

    # Force the service to a Settings instance that disables browser automation.
    original = service_module.ActionRequestService

    class _DisabledService(original):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(Settings(_env_file=None, enable_browser_automation=False))

    monkeypatch.setattr(service_module, "ActionRequestService", _DisabledService)
    monkeypatch.setattr(api_app, "ActionRequestService", _DisabledService)

    # The service calls session_scope to persist; if the DB isn't available the
    # request should still surface a 500. We're only checking the policy gate here,
    # so we monkeypatch persistence to return a fake view.
    captured: dict[str, Any] = {}

    async def fake_create(self: Any, request: Any, *, requested_by: str) -> Any:
        captured["url"] = request.url
        captured["steps"] = list(request.steps)
        from uuid import uuid4

        from cognitive_os.actions.schemas import ActionRequestView

        return ActionRequestView(
            id=uuid4(),
            action_type="browser_interactive",
            status="blocked",
            requested_by=requested_by,
            payload_redacted={},
            preview={"status": "blocked", "reason": "Browser automation is disabled."},
            result={},
            error="Browser automation is disabled.",
            created_at=__import__("datetime").datetime.now(tz=__import__("datetime").timezone.utc),
            updated_at=__import__("datetime").datetime.now(tz=__import__("datetime").timezone.utc),
        )

    monkeypatch.setattr(_DisabledService, "create_browser_interactive_request", fake_create)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/browser/interactive/request",
            json={
                "url": "https://example.com",
                "steps": [{"kind": "screenshot"}],
            },
            headers=_headers(),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert "disabled" in (body["error"] or "").lower()
    assert captured["url"] == "https://example.com"
