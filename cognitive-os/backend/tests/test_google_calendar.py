from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from cognitive_os.actions.calendar import (
    CalendarError,
    CalendarEvent,
    CalendarService,
    EventCreateRequest,
    FakeCalendarProvider,
    FreeBusyRequest,
    GoogleCalendarProvider,
    ListEventsRequest,
    _parse_event,
)
from cognitive_os.api.app import app
from cognitive_os.core.auth import create_access_token
from cognitive_os.core.config import Settings
from cognitive_os.core.google_oauth import GoogleCredentialsLoader


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id='1')}"}


def _settings(tmp_path: Path, *, enabled: bool = True, client_id: str = "id.apps") -> Settings:
    return Settings.model_construct(
        enable_google_calendar=enabled,
        google_client_id=client_id,
        google_token_dir=tmp_path,
        google_calendar_scopes=[
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.freebusy",
        ],
        http_timeout_seconds=5.0,
    )


def _loader(tmp_path: Path, *, token: str = "tok") -> GoogleCredentialsLoader:
    token_path = tmp_path / "token.json"
    token_path.write_text("{}", encoding="utf-8")
    creds = SimpleNamespace(valid=True, expired=False, refresh_token=None, token=token)
    return GoogleCredentialsLoader(token_path=token_path, credentials_loader=lambda _p: creds)


def test_status_disabled_blocked_ready(tmp_path: Path) -> None:
    assert CalendarService(app_settings=_settings(tmp_path, enabled=False)).status().status == (
        "disabled"
    )
    blocked = CalendarService(app_settings=_settings(tmp_path, client_id="CHANGEME"))
    assert blocked.status().status == "blocked"
    # No token.json on disk and no injected provider -> blocked.
    assert CalendarService(app_settings=_settings(tmp_path)).status().status == "blocked"
    # Injected provider bypasses the token check -> ready.
    ready = CalendarService(provider=FakeCalendarProvider(), app_settings=_settings(tmp_path))
    assert ready.status().status == "ready"


def test_list_events_blocked_when_not_ready(tmp_path: Path) -> None:
    service = CalendarService(app_settings=_settings(tmp_path, enabled=False))
    with pytest.raises(CalendarError, match="ENABLE_GOOGLE_CALENDAR"):
        service.list_events(ListEventsRequest())


def test_list_events_uses_provider_and_default_window(tmp_path: Path) -> None:
    event = CalendarEvent(event_id="e1", summary="Reunión", start="2026-06-01T10:00:00Z", end="x")
    provider = FakeCalendarProvider(events=[event])
    service = CalendarService(provider=provider, app_settings=_settings(tmp_path))
    result = service.list_events(ListEventsRequest(max_results=5))
    assert result == [event]
    call = provider.calls[0]
    assert call["max_results"] == 5
    assert call["time_max"] > call["time_min"]


def test_list_events_rejects_inverted_window(tmp_path: Path) -> None:
    service = CalendarService(provider=FakeCalendarProvider(), app_settings=_settings(tmp_path))
    now = datetime.now(tz=UTC)
    with pytest.raises(CalendarError, match="time_max must be after"):
        service.list_events(
            ListEventsRequest(time_min=now, time_max=now - timedelta(hours=1)),
        )


def test_freebusy_uses_provider_and_defaults_to_primary(tmp_path: Path) -> None:
    event = CalendarEvent(
        event_id="e1",
        summary="Call",
        start="2026-06-01T10:00:00Z",
        end="2026-06-01T11:00:00Z",
    )
    provider = FakeCalendarProvider(events=[event])
    service = CalendarService(provider=provider, app_settings=_settings(tmp_path))
    result = service.freebusy(FreeBusyRequest())
    assert result.busy_count == 1
    assert result.calendars[0].calendar_id == "primary"
    assert result.calendars[0].busy[0].start == "2026-06-01T10:00:00Z"
    assert provider.freebusy_calls[0]["calendars"] == ["primary"]


def test_freebusy_rejects_inverted_window(tmp_path: Path) -> None:
    service = CalendarService(provider=FakeCalendarProvider(), app_settings=_settings(tmp_path))
    now = datetime.now(tz=UTC)
    with pytest.raises(CalendarError, match="time_max must be after"):
        service.freebusy(FreeBusyRequest(time_min=now, time_max=now - timedelta(hours=1)))


def test_parse_event_detects_all_day() -> None:
    timed = _parse_event(
        {"id": "a", "summary": "Call", "start": {"dateTime": "2026-06-01T09:00:00Z"}, "end": {}}
    )
    assert timed is not None and timed.all_day is False
    all_day = _parse_event(
        {"id": "b", "summary": "Trip", "start": {"date": "2026-06-01"}, "end": {}}
    )
    assert all_day is not None and all_day.all_day is True
    assert _parse_event({"summary": "no id"}) is None


def test_google_provider_parses_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "items": [
            {
                "id": "evt-1",
                "summary": "Demo",
                "start": {"dateTime": "2026-06-01T10:00:00Z"},
                "end": {"dateTime": "2026-06-01T11:00:00Z"},
                "location": "Madrid",
                "htmlLink": "https://calendar.google.com/evt-1",
            },
            {"summary": "skipped, no id"},
        ]
    }

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    provider = GoogleCalendarProvider(_settings(tmp_path), credentials_loader=_loader(tmp_path))
    events = provider.list_events(
        time_min=datetime(2026, 6, 1, tzinfo=UTC),
        time_max=datetime(2026, 6, 8, tzinfo=UTC),
        max_results=10,
    )
    assert len(events) == 1
    assert events[0].event_id == "evt-1"
    assert events[0].location == "Madrid"


def test_google_provider_parses_freebusy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "calendars": {
            "primary": {
                "busy": [
                    {
                        "start": "2026-06-01T10:00:00Z",
                        "end": "2026-06-01T11:00:00Z",
                    }
                ]
            },
            "team@example.com": {"busy": []},
        }
    }

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        body = kwargs["json"]
        assert url.endswith("/freeBusy")
        assert body["items"] == [{"id": "primary"}, {"id": "team@example.com"}]
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = GoogleCalendarProvider(_settings(tmp_path), credentials_loader=_loader(tmp_path))
    result = provider.freebusy(
        time_min=datetime(2026, 6, 1, tzinfo=UTC),
        time_max=datetime(2026, 6, 2, tzinfo=UTC),
        calendars=["primary", "team@example.com"],
    )
    assert result.busy_count == 1
    assert result.calendars[0].busy[0].end == "2026-06-01T11:00:00Z"


@pytest.mark.asyncio
async def test_calendar_endpoints_require_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status_resp = await client.get("/actions/calendar/status")
        events_resp = await client.post("/actions/calendar/events", json={})
        freebusy_resp = await client.post("/actions/calendar/freebusy", json={})
        create_resp = await client.post("/actions/calendar/events/create", json={})
        request_resp = await client.post("/actions/calendar/events/request", json={})
    assert status_resp.status_code == 401
    assert events_resp.status_code == 401
    assert freebusy_resp.status_code == 401
    assert create_resp.status_code == 401
    assert request_resp.status_code == 401


@pytest.mark.asyncio
async def test_calendar_direct_create_rejects_real_write() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/actions/calendar/events/create",
            json={
                "summary": "Direct write",
                "start": "2026-06-01T10:00:00Z",
                "end": "2026-06-01T11:00:00Z",
                "dry_run": False,
            },
            headers=_headers(),
        )

    assert response.status_code == 409
    assert "/actions/calendar/events/request" in response.json()["detail"]


def _create_settings(
    tmp_path: Path,
    *,
    enabled: bool = True,
    write_enabled: bool = False,
) -> Settings:
    return Settings.model_construct(
        enable_google_calendar=enabled,
        enable_google_calendar_write=write_enabled,
        google_client_id="id.apps",
        google_token_dir=tmp_path,
        google_calendar_scopes=[
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.freebusy",
        ],
        http_timeout_seconds=5.0,
    )


def _create_request() -> EventCreateRequest:
    return EventCreateRequest(
        summary="Meet",
        start=datetime(2026, 6, 1, 10, tzinfo=UTC),
        end=datetime(2026, 6, 1, 11, tzinfo=UTC),
        location="Office",
        description=None,
        attendees=["a@example.com"],
        dry_run=True,
    )


def test_create_event_dry_run_returns_preview_and_does_not_touch_provider(tmp_path: Path) -> None:
    provider = FakeCalendarProvider()
    service = CalendarService(provider=provider, app_settings=_create_settings(tmp_path))
    result = service.create_event(_create_request())
    assert result.status == "preview"
    assert result.payload["summary"] == "Meet"
    assert result.event is None
    assert provider.create_calls == []


def test_create_event_real_blocked_when_write_disabled(tmp_path: Path) -> None:
    provider = FakeCalendarProvider()
    service = CalendarService(
        provider=provider,
        app_settings=_create_settings(tmp_path, write_enabled=False),
    )
    request = _create_request().model_copy(update={"dry_run": False})
    result = service.create_event(request)
    assert result.status == "blocked"
    assert "ENABLE_GOOGLE_CALENDAR_WRITE" in (result.reason or "")
    assert provider.create_calls == []


def test_create_event_executes_when_write_enabled(tmp_path: Path) -> None:
    provider = FakeCalendarProvider(
        created_event=CalendarEvent(
            event_id="real-evt",
            summary="Meet",
            start="2026-06-01T10:00:00Z",
            end="2026-06-01T11:00:00Z",
        )
    )
    service = CalendarService(
        provider=provider,
        app_settings=_create_settings(tmp_path, write_enabled=True),
    )
    request = _create_request().model_copy(update={"dry_run": False})
    result = service.create_event(request)
    assert result.status == "created"
    assert result.event is not None
    assert result.event.event_id == "real-evt"
    assert len(provider.create_calls) == 1
    sent = provider.create_calls[0]
    assert sent["summary"] == "Meet"
    assert sent["attendees"] == [{"email": "a@example.com"}]


def test_create_event_rejects_inverted_window(tmp_path: Path) -> None:
    service = CalendarService(
        provider=FakeCalendarProvider(),
        app_settings=_create_settings(tmp_path, write_enabled=True),
    )
    bad = _create_request().model_copy(
        update={"end": datetime(2026, 6, 1, 9, tzinfo=UTC), "dry_run": False}
    )
    with pytest.raises(CalendarError, match="end must be after"):
        service.create_event(bad)


def test_create_event_when_calendar_disabled(tmp_path: Path) -> None:
    service = CalendarService(
        provider=FakeCalendarProvider(),
        app_settings=_create_settings(tmp_path, enabled=False, write_enabled=True),
    )
    with pytest.raises(CalendarError, match="ENABLE_GOOGLE_CALENDAR"):
        service.create_event(_create_request())
