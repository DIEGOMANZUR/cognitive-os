from __future__ import annotations

import re
import time
from collections.abc import Callable
from importlib.util import find_spec
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from cognitive_os.actions.policy import (
    ActionPolicyViolation,
    validate_allowed_browser_domain,
    validate_path_inside_roots,
)
from cognitive_os.actions.schemas import (
    BrowserPreviewExecutionResult,
    BrowserPreviewRequest,
)
from cognitive_os.core.config import Settings, settings


class BrowserPreviewProvider(Protocol):
    def run(
        self,
        *,
        url: str,
        wait_until: str,
        timeout_ms: int,
        capture_screenshot: bool,
        screenshot_path: Path,
    ) -> BrowserPreviewProviderResult: ...


class BrowserPreviewProviderResult:
    __slots__ = ("final_url", "title", "screenshot_bytes")

    def __init__(
        self,
        *,
        final_url: str,
        title: str,
        screenshot_bytes: int,
    ) -> None:
        self.final_url = final_url
        self.title = title
        self.screenshot_bytes = screenshot_bytes


ProviderFactory = Callable[[Settings], BrowserPreviewProvider]


class BrowserPreviewService:
    def __init__(
        self,
        app_settings: Settings = settings,
        *,
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        self._settings = app_settings
        self._provider_factory = provider_factory

    def validate(self, request: BrowserPreviewRequest) -> tuple[str, str] | None:
        if not self._settings.enable_browser_automation:
            raise ActionPolicyViolation("Browser automation is disabled.")
        if not self._settings.browser_headless_default:
            raise ActionPolicyViolation("Browser preview requires BROWSER_HEADLESS_DEFAULT=true.")
        url, origin = validate_allowed_browser_domain(
            request.url,
            self._settings,
            resolve_ip=self._settings.enable_browser_ssrf_check,
        )
        return url, origin

    def execute(self, request: BrowserPreviewRequest) -> BrowserPreviewExecutionResult:
        try:
            normalized = self.validate(request)
            assert normalized is not None  # noqa: S101 - guarded by validate
            url, _origin = normalized
        except ActionPolicyViolation as exc:
            return BrowserPreviewExecutionResult(
                status="blocked",
                url=request.url,
                reason=str(exc),
            )

        provider = self._resolve_provider()
        if provider is None:
            return BrowserPreviewExecutionResult(
                status="blocked",
                url=url,
                reason=(
                    "Playwright is not installed. Run `uv sync` and "
                    "`playwright install chromium` to enable real previews."
                ),
            )

        try:
            screenshot_path = self._resolve_screenshot_path(url)
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        except ActionPolicyViolation as exc:
            return BrowserPreviewExecutionResult(
                status="blocked",
                url=url,
                reason=str(exc),
            )

        started = time.monotonic()
        try:
            outcome = provider.run(
                url=url,
                wait_until=request.wait_until,
                timeout_ms=self._settings.browser_navigation_timeout_ms,
                capture_screenshot=request.capture_screenshot,
                screenshot_path=screenshot_path,
            )
        except Exception as exc:  # noqa: BLE001 - report provider failures as failed
            return BrowserPreviewExecutionResult(
                status="failed",
                url=url,
                reason=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        duration_ms = int((time.monotonic() - started) * 1000)
        bytes_written = 0
        screenshot_out: str | None = None
        if request.capture_screenshot and screenshot_path.exists():
            bytes_written = screenshot_path.stat().st_size
            if bytes_written > self._settings.browser_screenshot_max_bytes:
                screenshot_path.unlink(missing_ok=True)
                return BrowserPreviewExecutionResult(
                    status="blocked",
                    url=url,
                    final_url=outcome.final_url,
                    title=outcome.title,
                    duration_ms=duration_ms,
                    reason=(
                        f"Screenshot exceeds BROWSER_SCREENSHOT_MAX_BYTES "
                        f"({bytes_written} > {self._settings.browser_screenshot_max_bytes})."
                    ),
                )
            screenshot_out = str(screenshot_path)

        return BrowserPreviewExecutionResult(
            status="completed",
            url=url,
            final_url=outcome.final_url,
            title=outcome.title,
            screenshot_path=screenshot_out,
            bytes_written=bytes_written,
            duration_ms=duration_ms,
        )

    def _resolve_provider(self) -> BrowserPreviewProvider | None:
        if self._provider_factory is not None:
            return self._provider_factory(self._settings)
        if find_spec("playwright") is None:
            return None
        return PlaywrightBrowserPreviewProvider()

    def _resolve_screenshot_path(self, url: str) -> Path:
        root = self._settings.browser_screenshot_dir.expanduser().resolve()
        host = urlparse(url).netloc.replace(":", "_") or "unknown"
        slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", host).strip("_") or "page"
        stamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{slug}-{stamp}.png"
        candidate = (root / filename).resolve()
        validate_path_inside_roots(candidate, [root], label="browser screenshot")
        return candidate


class PlaywrightBrowserPreviewProvider:
    def run(
        self,
        *,
        url: str,
        wait_until: str,
        timeout_ms: int,
        capture_screenshot: bool,
        screenshot_path: Path,
    ) -> BrowserPreviewProviderResult:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]

        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                page = context.new_page()
                response = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                final_url = response.url if response is not None else page.url
                title = page.title()
                screenshot_bytes = 0
                if capture_screenshot:
                    page.screenshot(path=str(screenshot_path), full_page=False)
                    screenshot_bytes = screenshot_path.stat().st_size
                return BrowserPreviewProviderResult(
                    final_url=final_url,
                    title=title,
                    screenshot_bytes=screenshot_bytes,
                )
            finally:
                browser.close()
