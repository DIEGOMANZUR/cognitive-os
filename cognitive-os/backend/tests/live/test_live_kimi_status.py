"""Live smoke: the Kimi WebBridge / Edge DevTools daemon answers a probe.

Read-only: `KimiWebBridgeService().status()` pings the local daemon and (if
enabled) the Edge DevTools endpoint. It opens no tab and navigates nowhere.
"""

from __future__ import annotations

import pytest

from cognitive_os.core.config import settings

pytestmark = pytest.mark.live_readonly


def test_live_kimi_webbridge_status() -> None:
    edge_enabled = bool(getattr(settings, "enable_edge_devtools_webbridge", False))
    if not settings.enable_kimi_webbridge and not edge_enabled:
        pytest.skip("Neither Kimi WebBridge nor Edge DevTools bridge is enabled")

    from cognitive_os.actions.kimi_webbridge import KimiWebBridgeService

    status = KimiWebBridgeService().status()

    # `ready` proves a live daemon answered. `blocked` is honest (daemon up but
    # misconfigured) and worth surfacing; `disabled` with nothing running means
    # the operator must start the daemon — skip rather than fail.
    assert status.status in {"ready", "blocked", "disabled"}
    if status.status == "disabled" and not status.daemon_running:
        pytest.skip(f"WebBridge daemon not running: {status.reason}")
    assert status.daemon_url
