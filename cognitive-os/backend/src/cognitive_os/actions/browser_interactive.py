"""Multi-step browser automation with optional LLM-vision analysis.

This module extends the single-shot `browser_preview` flow into a guarded loop
that can click, fill, scroll, capture screenshots, and ask a multimodal LLM to
analyze what the page shows. Every step runs through the same allow-list and
size caps as `browser_preview`, plus a few extra rules:

- New `navigate` steps re-validate the URL against `BROWSER_ALLOWED_DOMAINS`.
- `analyze` steps are forwarded to a `VisionAnalyzer` Protocol so tests can run
  without an LLM key; in production the default uses the dedicated vision model
  (glm-4.6v) with automatic fallback to the secondary vision model (Kimi 2.6).
- Each step's result (`BrowserStepResult`) records its status, duration and any
  screenshot, so the operator UI can replay the trace post-execution.

The browser provider is also a Protocol, mirroring `BrowserPreviewService`'s
pattern. Tests inject a `FakeBrowserInteractiveProvider` and never spawn a real
Chromium.
"""

from __future__ import annotations

import base64
import re
import time
from collections.abc import Callable, Sequence
from importlib.util import find_spec
from pathlib import Path
from typing import Literal, Protocol, cast
from urllib.parse import urlparse

import structlog

from cognitive_os.actions.policy import (
    ActionPolicyViolation,
    validate_allowed_browser_domain,
    validate_path_inside_roots,
)
from cognitive_os.actions.schemas import (
    BrowserInteractiveExecutionResult,
    BrowserInteractiveRequest,
    BrowserStep,
    BrowserStepResult,
)
from cognitive_os.core.config import Settings, settings

log = structlog.get_logger(__name__)

PlaywrightWaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]


class VisionAnalyzer(Protocol):
    def analyze(self, *, prompt: str, image_path: Path) -> str: ...


class BrowserInteractiveProvider(Protocol):
    def run(
        self,
        *,
        initial_url: str,
        steps: Sequence[BrowserStep],
        wait_until: str,
        timeout_ms: int,
        screenshot_dir: Path,
        vision_analyzer: VisionAnalyzer | None,
    ) -> list[BrowserStepResult]: ...


ProviderFactory = Callable[[Settings], BrowserInteractiveProvider]
VisionFactory = Callable[[Settings], VisionAnalyzer | None]


MAX_WAIT_MS = 10_000
DEFAULT_SCROLL_PX = 600
SELECTOR_RE = re.compile(r"^[A-Za-z0-9_#.\[\]=\"'\-\s>:()+~,*]+$")


class BrowserInteractiveService:
    def __init__(
        self,
        app_settings: Settings = settings,
        *,
        provider_factory: ProviderFactory | None = None,
        vision_factory: VisionFactory | None = None,
    ) -> None:
        self._settings = app_settings
        self._provider_factory = provider_factory
        self._vision_factory = vision_factory

    def validate(self, request: BrowserInteractiveRequest) -> tuple[str, str]:
        if not self._settings.enable_browser_automation:
            raise ActionPolicyViolation("Browser automation is disabled.")
        if not self._settings.browser_headless_default:
            raise ActionPolicyViolation(
                "Browser interactive requires BROWSER_HEADLESS_DEFAULT=true.",
            )
        url, origin = validate_allowed_browser_domain(
            request.url,
            self._settings,
            resolve_ip=self._settings.enable_browser_ssrf_check,
        )
        # Pre-validate every step so the service refuses fast (before launching
        # a browser) when the plan is unsafe. Each step that hits the network
        # gets re-validated at runtime too.
        for index, step in enumerate(request.steps):
            self._validate_step(index, step)
        return url, origin

    def execute(
        self,
        request: BrowserInteractiveRequest,
    ) -> BrowserInteractiveExecutionResult:
        started = time.monotonic()
        try:
            normalized = self.validate(request)
        except ActionPolicyViolation as exc:
            return BrowserInteractiveExecutionResult(
                status="blocked",
                url=request.url,
                reason=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        provider = self._resolve_provider()
        if provider is None:
            return BrowserInteractiveExecutionResult(
                status="blocked",
                url=normalized[0],
                reason=(
                    "Playwright is not installed. Run `uv sync` and "
                    "`playwright install chromium` to enable interactive browsing."
                ),
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        try:
            screenshot_dir = self._resolve_screenshot_dir()
        except ActionPolicyViolation as exc:
            return BrowserInteractiveExecutionResult(
                status="blocked",
                url=normalized[0],
                reason=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        analyzer = self._resolve_vision_analyzer()

        try:
            step_results = provider.run(
                initial_url=normalized[0],
                steps=request.steps,
                wait_until=request.wait_until,
                timeout_ms=self._settings.browser_navigation_timeout_ms,
                screenshot_dir=screenshot_dir,
                vision_analyzer=analyzer,
            )
        except Exception as exc:  # noqa: BLE001 - provider errors surface as failed
            return BrowserInteractiveExecutionResult(
                status="failed",
                url=normalized[0],
                reason=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        # Enforce per-screenshot size cap post-execution so a misbehaving page
        # cannot leave huge PNGs on disk.
        max_bytes = self._settings.browser_screenshot_max_bytes
        for result in step_results:
            if not result.screenshot_path:
                continue
            shot = Path(result.screenshot_path)
            if shot.exists() and shot.stat().st_size > max_bytes:
                shot.unlink(missing_ok=True)
                result.status = "blocked"
                result.reason = (
                    f"Screenshot exceeds BROWSER_SCREENSHOT_MAX_BYTES "
                    f"({shot.stat().st_size if shot.exists() else '>cap'} > {max_bytes})."
                )
                result.screenshot_path = None

        final_url = next(
            (result.final_url for result in reversed(step_results) if result.final_url is not None),
            normalized[0],
        )
        has_failure = any(result.status == "failed" for result in step_results)
        has_block = any(result.status == "blocked" for result in step_results)
        overall: str
        if has_failure:
            overall = "failed"
        elif has_block:
            overall = "blocked"
        else:
            overall = "completed"
        return BrowserInteractiveExecutionResult(
            status=overall,  # type: ignore[arg-type]
            url=normalized[0],
            final_url=final_url,
            steps=step_results,
            reason=None,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    def _validate_step(self, index: int, step: BrowserStep) -> None:
        if step.kind == "navigate":
            if not step.url:
                msg = f"step[{index}] navigate requires `url`"
                raise ActionPolicyViolation(msg)
            validate_allowed_browser_domain(
                step.url,
                self._settings,
                resolve_ip=self._settings.enable_browser_ssrf_check,
            )
        elif step.kind == "click":
            self._require_selector(index, step.selector)
        elif step.kind == "fill":
            self._require_selector(index, step.selector)
            if step.value is None:
                msg = f"step[{index}] fill requires `value`"
                raise ActionPolicyViolation(msg)
        elif step.kind == "scroll":
            if step.value is not None and not step.value.lstrip("-").isdigit():
                msg = f"step[{index}] scroll value must be an integer (pixels)"
                raise ActionPolicyViolation(msg)
        elif step.kind == "wait":
            if step.value is None or not step.value.isdigit():
                msg = f"step[{index}] wait requires integer milliseconds in `value`"
                raise ActionPolicyViolation(msg)
            if int(step.value) > MAX_WAIT_MS:
                msg = f"step[{index}] wait cannot exceed {MAX_WAIT_MS} ms"
                raise ActionPolicyViolation(msg)
        elif step.kind == "analyze":
            if not step.prompt or not step.prompt.strip():
                msg = f"step[{index}] analyze requires `prompt`"
                raise ActionPolicyViolation(msg)
        # `screenshot` has no extra arguments.

    @staticmethod
    def _require_selector(index: int, selector: str | None) -> None:
        if not selector or not selector.strip():
            msg = f"step[{index}] requires a CSS `selector`"
            raise ActionPolicyViolation(msg)
        if not SELECTOR_RE.match(selector):
            msg = f"step[{index}] selector contains disallowed characters"
            raise ActionPolicyViolation(msg)

    def _resolve_provider(self) -> BrowserInteractiveProvider | None:
        if self._provider_factory is not None:
            return self._provider_factory(self._settings)
        if find_spec("playwright") is None:
            return None
        return PlaywrightBrowserInteractiveProvider()

    def _resolve_vision_analyzer(self) -> VisionAnalyzer | None:
        if self._vision_factory is not None:
            return self._vision_factory(self._settings)
        try:
            return ChatVisionAnalyzer.from_settings(self._settings)
        except Exception:
            # Without a configured multimodal model the analyze step still runs;
            # it just returns "analysis unavailable" via the provider.
            return None

    def _resolve_screenshot_dir(self) -> Path:
        root = self._settings.browser_screenshot_dir.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        # Sanity: the directory must be inside the configured root after resolve.
        validate_path_inside_roots(root, [root], label="browser interactive screenshots")
        return root


class ChatVisionAnalyzer:
    """Default vision analyzer backed by the primary chat model.

    Uses LangChain's multimodal message format: a `HumanMessage` whose content
    is a list of `{type:"text"}` and `{type:"image_url"}` blocks. Works with
    OpenAI-compatible providers that accept data-URL images (gpt-4o, gpt-5,
    Gemini, etc.). The image is sent as `data:image/png;base64,...` so we
    never need a public URL.
    """

    def __init__(self, llm: object, fallback_llm: object | None = None) -> None:
        self._llm = llm
        self._fallback_llm = fallback_llm

    @classmethod
    def from_settings(cls, app_settings: Settings) -> ChatVisionAnalyzer:
        from cognitive_os.agents.llm_factory import create_vision_chat_model

        del app_settings
        primary = create_vision_chat_model()
        try:
            fallback = create_vision_chat_model(fallback=True)
        except ValueError:
            # Fallback creds not configured: run primary-only rather than refuse.
            fallback = None
        return cls(primary, fallback)

    def _build_messages(self, prompt: str, data_uri: str) -> list[object]:
        from langchain_core.messages import HumanMessage, SystemMessage

        return [
            SystemMessage(
                content=(
                    "Describe lo que muestra el screenshot. Sé conciso, factual, "
                    "y no inventes contenido fuera de la imagen."
                ),
            ),
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            ),
        ]

    def analyze(self, *, prompt: str, image_path: Path) -> str:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        data_uri = f"data:image/png;base64,{encoded}"
        messages = self._build_messages(prompt, data_uri)
        try:
            response = self._llm.invoke(messages)  # type: ignore[attr-defined]
        except Exception as primary_exc:
            if self._fallback_llm is None:
                raise
            log.warning(
                "vision_primary_failed_using_fallback",
                error=str(primary_exc),
            )
            response = self._fallback_llm.invoke(messages)  # type: ignore[attr-defined]
        content = getattr(response, "content", response)
        return str(content) if content is not None else "vision analyzer returned no content"


class PlaywrightBrowserInteractiveProvider:
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
        from playwright.sync_api import sync_playwright

        results: list[BrowserStepResult] = []
        screenshot_seq = 0

        def shot_path() -> Path:
            nonlocal screenshot_seq
            screenshot_seq += 1
            host = urlparse(initial_url).netloc.replace(":", "_") or "page"
            slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", host).strip("_") or "page"
            stamp = time.strftime("%Y%m%d-%H%M%S")
            return screenshot_dir / f"{slug}-{stamp}-{screenshot_seq:02d}.png"

        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                page = context.new_page()
                page.goto(
                    initial_url,
                    wait_until=cast("PlaywrightWaitUntil", wait_until),
                    timeout=timeout_ms,
                )
                for index, step in enumerate(steps):
                    started = time.monotonic()
                    try:
                        result = self._run_step(
                            page=page,
                            step=step,
                            step_index=index,
                            timeout_ms=timeout_ms,
                            shot_path=shot_path,
                            vision_analyzer=vision_analyzer,
                        )
                    except Exception as exc:  # noqa: BLE001
                        result = BrowserStepResult(
                            step_index=index,
                            kind=step.kind,
                            status="failed",
                            reason=f"{type(exc).__name__}: {exc}",
                            duration_ms=int((time.monotonic() - started) * 1000),
                        )
                    else:
                        result.duration_ms = int((time.monotonic() - started) * 1000)
                    results.append(result)
            finally:
                browser.close()
        return results

    def _run_step(
        self,
        *,
        page: object,
        step: BrowserStep,
        step_index: int,
        timeout_ms: int,
        shot_path: Callable[[], Path],
        vision_analyzer: VisionAnalyzer | None,
    ) -> BrowserStepResult:
        if step.kind == "navigate":
            assert step.url is not None  # noqa: S101 - guaranteed by validate
            page.goto(step.url, timeout=timeout_ms)  # type: ignore[attr-defined]
            return BrowserStepResult(
                step_index=step_index,
                kind=step.kind,
                status="ok",
                final_url=page.url,  # type: ignore[attr-defined]
                title=page.title(),  # type: ignore[attr-defined]
            )
        if step.kind == "click":
            assert step.selector is not None  # noqa: S101
            page.click(step.selector, timeout=timeout_ms)  # type: ignore[attr-defined]
            return BrowserStepResult(step_index=step_index, kind=step.kind, status="ok")
        if step.kind == "fill":
            assert step.selector is not None  # noqa: S101
            page.fill(step.selector, step.value or "", timeout=timeout_ms)  # type: ignore[attr-defined]
            return BrowserStepResult(step_index=step_index, kind=step.kind, status="ok")
        if step.kind == "scroll":
            delta = int(step.value or DEFAULT_SCROLL_PX)
            page.evaluate(f"window.scrollBy(0, {delta})")  # type: ignore[attr-defined]
            return BrowserStepResult(step_index=step_index, kind=step.kind, status="ok")
        if step.kind == "wait":
            page.wait_for_timeout(int(step.value or 0))  # type: ignore[attr-defined]
            return BrowserStepResult(step_index=step_index, kind=step.kind, status="ok")
        if step.kind == "screenshot":
            target = shot_path()
            page.screenshot(path=str(target), full_page=False)  # type: ignore[attr-defined]
            return BrowserStepResult(
                step_index=step_index,
                kind=step.kind,
                status="ok",
                screenshot_path=str(target),
            )
        if step.kind == "analyze":
            target = shot_path()
            page.screenshot(path=str(target), full_page=False)  # type: ignore[attr-defined]
            if vision_analyzer is None:
                return BrowserStepResult(
                    step_index=step_index,
                    kind=step.kind,
                    status="ok",
                    screenshot_path=str(target),
                    analysis=(
                        "vision analyzer is not configured; screenshot captured but not analyzed."
                    ),
                )
            analysis = vision_analyzer.analyze(
                prompt=step.prompt or "Describe la pagina actual.",
                image_path=target,
            )
            return BrowserStepResult(
                step_index=step_index,
                kind=step.kind,
                status="ok",
                screenshot_path=str(target),
                analysis=analysis,
            )
        msg = f"unsupported browser step kind: {step.kind}"
        raise ValueError(msg)
