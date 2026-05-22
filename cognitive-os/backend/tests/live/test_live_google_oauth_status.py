"""Live smoke: Google OAuth is healthy enough for a read-only Calendar call.

Read-only: only `CalendarService().status()` plus, if ready, a free/busy query
for a 1-hour window. Never creates or mutates an event. Catches an expired or
missing OAuth token before the operator hits it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from cognitive_os.core.config import settings

pytestmark = pytest.mark.live_readonly


def test_live_google_calendar_oauth_status() -> None:
    if not settings.enable_google_calendar:
        pytest.skip("ENABLE_GOOGLE_CALENDAR is false")

    from cognitive_os.actions.calendar import (
        CalendarError,
        CalendarService,
        FreeBusyRequest,
    )

    service = CalendarService()
    status = service.status()

    # `blocked`/`disabled` are honest "not set up" states — skip, don't fail:
    # the operator must run scripts/auth_google.py or flip the flag.
    if status.status in {"blocked", "disabled"}:
        pytest.skip(f"Google Calendar not ready ({status.status}): {status.reason}")
    assert status.status == "ready"

    # `status==ready` only inspects the token's recorded scopes — it can be a
    # false positive (API disabled in the Cloud project, scope not really
    # granted). The freebusy call is the real verification; a CalendarError
    # here is a genuine finding, surfaced with a clean redacted message.
    now = datetime.now(UTC)
    try:
        result = service.freebusy(FreeBusyRequest(time_min=now, time_max=now + timedelta(hours=1)))
    except CalendarError as exc:
        pytest.fail(f"Google Calendar OAuth is not usable for free/busy: {exc}")
    assert result is not None
