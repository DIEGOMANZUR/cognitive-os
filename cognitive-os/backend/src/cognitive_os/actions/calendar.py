"""Google Calendar (read-only) for the personal assistant.

This lane lists upcoming events so the agent can reason about the user's
agenda. It is intentionally read-only for now: creating/editing events is an
external action that must flow through the `ActionRequest`/approval lifecycle,
which is tracked as a separate follow-up. Tests inject `FakeCalendarProvider`,
so the suite never touches Google.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

import httpx
import structlog
from pydantic import BaseModel, Field

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.google_oauth import (
    GoogleCredentialsLoader,
    GoogleOAuthError,
    redact_google_error,
)
from cognitive_os.core.resilience import retry_transient_http
from cognitive_os.tools.policy import ToolAuditRecord, ToolRiskLevel, record_audit_event

_log = structlog.get_logger(__name__)

_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
_MAX_RESULTS = 50
_MAX_FREEBUSY_CALENDARS = 20


class CalendarError(RuntimeError):
    """Raised when a Calendar query cannot be completed."""


class CalendarEvent(BaseModel):
    event_id: str
    summary: str
    start: str
    end: str
    all_day: bool = False
    location: str | None = None
    html_link: str | None = None


class CalendarStatus(BaseModel):
    status: Literal["disabled", "blocked", "ready"]
    reason: str | None = None
    calendar_id: str = "primary"
    write_enabled: bool = False
    # GPT-5.5 P1 Fase 68b: scopes que el operador necesita autorizar pero el
    # token actual aún no tiene. Vacío = todo OK. Si no está vacío, la
    # capacidad se reporta `blocked` con guía para re-autorizar.
    missing_scopes: list[str] = []


class ListEventsRequest(BaseModel):
    time_min: datetime | None = None
    time_max: datetime | None = None
    max_results: int = Field(default=10, ge=1, le=_MAX_RESULTS)


class FreeBusyRequest(BaseModel):
    time_min: datetime | None = None
    time_max: datetime | None = None
    calendars: list[str] = Field(
        default_factory=lambda: ["primary"], max_length=_MAX_FREEBUSY_CALENDARS
    )


class FreeBusySlot(BaseModel):
    start: str
    end: str


class FreeBusyCalendar(BaseModel):
    calendar_id: str
    busy: list[FreeBusySlot] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class FreeBusyResult(BaseModel):
    time_min: str
    time_max: str
    calendars: list[FreeBusyCalendar] = Field(default_factory=list)
    busy_count: int = 0


class EventCreateRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    start: datetime
    end: datetime
    location: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=8000)
    attendees: list[str] = Field(default_factory=list, max_length=50)
    dry_run: bool = True


class EventCreatePreview(BaseModel):
    status: Literal["preview", "blocked", "created"]
    reason: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    event: CalendarEvent | None = None


class CalendarProvider(Protocol):
    def list_events(
        self,
        *,
        time_min: datetime,
        time_max: datetime,
        max_results: int,
    ) -> list[CalendarEvent]: ...

    def create_event(self, payload: dict[str, Any]) -> CalendarEvent: ...

    def freebusy(
        self,
        *,
        time_min: datetime,
        time_max: datetime,
        calendars: list[str],
    ) -> FreeBusyResult: ...


class FakeCalendarProvider:
    def __init__(
        self,
        *,
        events: list[CalendarEvent] | None = None,
        raises: bool = False,
        created_event: CalendarEvent | None = None,
        raise_on_create: bool = False,
    ) -> None:
        self._events = events or []
        self._raises = raises
        self._created_event = created_event
        self._raise_on_create = raise_on_create
        self.calls: list[dict[str, Any]] = []
        self.create_calls: list[dict[str, Any]] = []
        self.freebusy_calls: list[dict[str, Any]] = []

    def list_events(
        self,
        *,
        time_min: datetime,
        time_max: datetime,
        max_results: int,
    ) -> list[CalendarEvent]:
        self.calls.append({"time_min": time_min, "time_max": time_max, "max_results": max_results})
        if self._raises:
            raise CalendarError("fake calendar failure")
        return list(self._events[:max_results])

    def create_event(self, payload: dict[str, Any]) -> CalendarEvent:
        self.create_calls.append(payload)
        if self._raise_on_create:
            raise CalendarError("fake create failure")
        if self._created_event is not None:
            return self._created_event
        return CalendarEvent(
            event_id="fake-evt",
            summary=str(payload.get("summary", "")),
            start=str(payload.get("start", {}).get("dateTime", "")),
            end=str(payload.get("end", {}).get("dateTime", "")),
            location=payload.get("location"),
            html_link="https://calendar.google.com/fake",
        )

    def freebusy(
        self,
        *,
        time_min: datetime,
        time_max: datetime,
        calendars: list[str],
    ) -> FreeBusyResult:
        self.freebusy_calls.append(
            {"time_min": time_min, "time_max": time_max, "calendars": list(calendars)}
        )
        if self._raises:
            raise CalendarError("fake calendar failure")
        slots = [
            FreeBusySlot(start=event.start, end=event.end)
            for event in self._events
            if event.start and event.end
        ]
        return FreeBusyResult(
            time_min=_google_datetime(time_min),
            time_max=_google_datetime(time_max),
            calendars=[
                FreeBusyCalendar(
                    calendar_id=calendar_id,
                    busy=slots if calendar_id == "primary" else [],
                )
                for calendar_id in calendars
            ],
            busy_count=len(slots) if "primary" in calendars else 0,
        )


def _parse_event(raw: dict[str, Any]) -> CalendarEvent | None:
    event_id = str(raw.get("id") or "")
    if not event_id:
        return None
    start_obj = raw.get("start") or {}
    end_obj = raw.get("end") or {}
    start = str(start_obj.get("dateTime") or start_obj.get("date") or "")
    end = str(end_obj.get("dateTime") or end_obj.get("date") or "")
    all_day = "date" in start_obj and "dateTime" not in start_obj
    return CalendarEvent(
        event_id=event_id,
        summary=str(raw.get("summary") or "(sin título)"),
        start=start,
        end=end,
        all_day=all_day,
        location=str(raw["location"]) if raw.get("location") else None,
        html_link=str(raw["htmlLink"]) if raw.get("htmlLink") else None,
    )


def _parse_freebusy(
    raw: dict[str, Any],
    *,
    time_min: datetime,
    time_max: datetime,
    requested_calendars: list[str],
) -> FreeBusyResult:
    calendars_obj = raw.get("calendars") if isinstance(raw.get("calendars"), dict) else {}
    calendars: list[FreeBusyCalendar] = []
    busy_count = 0
    for calendar_id in requested_calendars:
        entry = calendars_obj.get(calendar_id) if isinstance(calendars_obj, dict) else None
        entry = entry if isinstance(entry, dict) else {}
        slots: list[FreeBusySlot] = []
        for slot in entry.get("busy") or []:
            if isinstance(slot, dict) and slot.get("start") and slot.get("end"):
                slots.append(FreeBusySlot(start=str(slot["start"]), end=str(slot["end"])))
        errors = [
            str(error.get("reason") or error)
            for error in entry.get("errors") or []
            if isinstance(error, dict)
        ]
        busy_count += len(slots)
        calendars.append(FreeBusyCalendar(calendar_id=calendar_id, busy=slots, errors=errors))
    return FreeBusyResult(
        time_min=_google_datetime(time_min),
        time_max=_google_datetime(time_max),
        calendars=calendars,
        busy_count=busy_count,
    )


def _google_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class GoogleCalendarProvider:
    """Real provider: Google Calendar API v3 over an authorized-user token."""

    def __init__(
        self,
        app_settings: Settings = settings,
        credentials_loader: GoogleCredentialsLoader | None = None,
    ) -> None:
        self._settings = app_settings
        self._loader = credentials_loader or GoogleCredentialsLoader(
            token_path=app_settings.google_token_dir.expanduser() / "token.json"
        )

    def list_events(
        self,
        *,
        time_min: datetime,
        time_max: datetime,
        max_results: int,
    ) -> list[CalendarEvent]:
        try:
            token = self._loader.access_token()
        except GoogleOAuthError as exc:
            raise CalendarError(str(exc)) from exc
        url = f"{_CALENDAR_API}/calendars/primary/events"
        params = {
            "timeMin": _google_datetime(time_min),
            "timeMax": _google_datetime(time_max),
            "maxResults": str(max_results),
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        try:
            response = retry_transient_http(
                lambda: httpx.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise CalendarError(
                f"Calendar request failed: {redact_google_error(str(exc))}"
            ) from exc
        except ValueError as exc:
            raise CalendarError("Calendar API returned invalid JSON.") from exc
        items = payload.get("items") or []
        events: list[CalendarEvent] = []
        for raw in items:
            if isinstance(raw, dict):
                parsed = _parse_event(raw)
                if parsed is not None:
                    events.append(parsed)
        return events

    def create_event(self, payload: dict[str, Any]) -> CalendarEvent:
        try:
            token = self._loader.access_token()
        except GoogleOAuthError as exc:
            raise CalendarError(str(exc)) from exc
        url = f"{_CALENDAR_API}/calendars/primary/events"
        try:
            response = retry_transient_http(
                lambda: httpx.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPError as exc:
            raise CalendarError(f"Calendar create failed: {redact_google_error(str(exc))}") from exc
        except ValueError as exc:
            raise CalendarError("Calendar create returned invalid JSON.") from exc
        parsed = _parse_event(body) if isinstance(body, dict) else None
        if parsed is None:
            raise CalendarError("Calendar create returned an unexpected payload shape.")
        return parsed

    def freebusy(
        self,
        *,
        time_min: datetime,
        time_max: datetime,
        calendars: list[str],
    ) -> FreeBusyResult:
        try:
            token = self._loader.access_token()
        except GoogleOAuthError as exc:
            raise CalendarError(str(exc)) from exc
        body = {
            "timeMin": _google_datetime(time_min),
            "timeMax": _google_datetime(time_max),
            "items": [{"id": calendar_id} for calendar_id in calendars],
        }
        try:
            response = retry_transient_http(
                lambda: httpx.post(
                    f"{_CALENDAR_API}/freeBusy",
                    json=body,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self._settings.http_timeout_seconds,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise CalendarError(
                f"Calendar freebusy failed: {redact_google_error(str(exc))}"
            ) from exc
        except ValueError as exc:
            raise CalendarError("Calendar freebusy returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise CalendarError("Calendar freebusy returned an unexpected payload shape.")
        return _parse_freebusy(
            payload,
            time_min=time_min,
            time_max=time_max,
            requested_calendars=calendars,
        )


class CalendarService:
    """Capability-gated, read-only Calendar facade."""

    def __init__(
        self,
        provider: CalendarProvider | None = None,
        app_settings: Settings = settings,
    ) -> None:
        self._settings = app_settings
        self._provider = provider

    def status(self) -> CalendarStatus:
        write_enabled = bool(self._settings.enable_google_calendar_write)
        if not self._settings.enable_google_calendar:
            return CalendarStatus(
                status="disabled",
                reason="ENABLE_GOOGLE_CALENDAR is false.",
                write_enabled=write_enabled,
            )
        token_path = self._settings.google_token_dir.expanduser() / "token.json"
        client_id = self._settings.google_client_id
        if not client_id or "CHANGEME" in client_id:
            return CalendarStatus(
                status="blocked",
                reason="GOOGLE_CLIENT_ID is not configured.",
                write_enabled=write_enabled,
            )
        if self._provider is None and not token_path.exists():
            return CalendarStatus(
                status="blocked",
                reason="No token.json found; run scripts/auth_google.py once.",
                write_enabled=write_enabled,
            )
        # Scope check (GPT-5.5 P1 Fase 68b): a token authorized only for
        # `calendar.readonly` would let `status` say `ready` even though
        # /freebusy and event creation need broader scopes. Surface the gap
        # instead of pretending the capability is operational.
        required = self._required_scopes(write_enabled, self._settings.google_calendar_scopes)
        missing: list[str] = []
        if self._provider is None and token_path.exists() and required:
            try:
                from cognitive_os.core.google_oauth import (  # noqa: PLC0415
                    GoogleCredentialsLoader,
                )

                missing = GoogleCredentialsLoader(token_path=token_path).missing_scopes(required)
            except Exception:  # noqa: BLE001 - scope check is best-effort
                missing = []
        if missing:
            return CalendarStatus(
                status="blocked",
                reason=(
                    "Google token is missing required Calendar scopes: "
                    + ", ".join(missing)
                    + ". Delete token.json and re-run scripts/auth_google.py "
                    "to re-consent."
                ),
                write_enabled=write_enabled,
                missing_scopes=missing,
            )
        return CalendarStatus(status="ready", reason=None, write_enabled=write_enabled)

    @staticmethod
    def _required_scopes(write_enabled: bool, configured: list[str]) -> list[str]:
        """Scopes Calendar must have to operate at this configuration.

        Honor whatever the operator put in `GOOGLE_CALENDAR_SCOPES` — that is
        the consent we asked them to grant via `scripts/auth_google.py` and the
        validation should match. Falls back to a sensible baseline only if the
        env var is empty (read-only listing + free/busy under `calendar.readonly`;
        event creation under `calendar.events`).
        """
        if configured:
            return list(configured)
        scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        if write_enabled:
            scopes.append("https://www.googleapis.com/auth/calendar.events")
        return scopes

    def _resolve_provider(self) -> CalendarProvider:
        if self._provider is None:
            self._provider = GoogleCalendarProvider(self._settings)
        return self._provider

    def _require_ready(self) -> None:
        current = self.status()
        if current.status != "ready":
            raise CalendarError(current.reason or "Calendar is not available.")

    def list_events(self, request: ListEventsRequest) -> list[CalendarEvent]:
        self._require_ready()
        now = datetime.now(tz=UTC)
        time_min = request.time_min or now
        time_max = request.time_max or (now + timedelta(days=7))
        if time_max <= time_min:
            raise CalendarError("time_max must be after time_min.")
        return self._resolve_provider().list_events(
            time_min=time_min,
            time_max=time_max,
            max_results=request.max_results,
        )

    def freebusy(self, request: FreeBusyRequest) -> FreeBusyResult:
        self._require_ready()
        now = datetime.now(tz=UTC)
        time_min = request.time_min or now
        time_max = request.time_max or (now + timedelta(days=7))
        if time_max <= time_min:
            raise CalendarError("time_max must be after time_min.")
        calendars = _clean_calendar_ids(request.calendars)
        return self._resolve_provider().freebusy(
            time_min=time_min,
            time_max=time_max,
            calendars=calendars,
        )

    def create_event(
        self,
        request: EventCreateRequest,
        *,
        requested_by: str | None = None,
    ) -> EventCreatePreview:
        """Create a Calendar event with preview-first + double opt-in.

        - `dry_run=True` (the default) **never** touches Google: it returns the
          exact payload that would be sent and a `preview` status.
        - `dry_run=False` requires `ENABLE_GOOGLE_CALENDAR_WRITE=true`; otherwise
          the request is recorded as `blocked` and audited.
        Every attempt (preview, blocked, created) emits an audit event so the
        operator can reconcile drift between intent and execution.
        """
        if request.end <= request.start:
            raise CalendarError("Event end must be after start.")
        current = self.status()
        if current.status != "ready":
            raise CalendarError(current.reason or "Calendar is not available.")
        payload: dict[str, Any] = {
            "summary": request.summary,
            "start": {"dateTime": _google_datetime(request.start)},
            "end": {"dateTime": _google_datetime(request.end)},
        }
        if request.location:
            payload["location"] = request.location
        if request.description:
            payload["description"] = request.description
        if request.attendees:
            payload["attendees"] = [{"email": email} for email in request.attendees]

        audit_args: dict[str, Any] = {
            "summary_len": len(request.summary),
            "attendees_count": len(request.attendees),
            "dry_run": request.dry_run,
        }

        if request.dry_run:
            _audit_calendar("preview_create_event", audit_args, requested_by, "preview")
            return EventCreatePreview(status="preview", payload=payload)

        if not self._settings.enable_google_calendar_write:
            _audit_calendar(
                "blocked_create_event",
                audit_args,
                requested_by,
                "blocked: write_disabled",
            )
            return EventCreatePreview(
                status="blocked",
                reason="ENABLE_GOOGLE_CALENDAR_WRITE is false; refusing to create event.",
                payload=payload,
            )

        try:
            event = self._resolve_provider().create_event(payload)
        except CalendarError:
            _audit_calendar("create_event_failed", audit_args, requested_by, "error")
            raise
        _audit_calendar(
            "create_event_succeeded",
            {**audit_args, "event_id": event.event_id},
            requested_by,
            "ok",
        )
        return EventCreatePreview(status="created", payload=payload, event=event)


def _clean_calendar_ids(raw: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in raw or ["primary"]:
        calendar_id = value.strip()
        if calendar_id and calendar_id not in cleaned:
            cleaned.append(calendar_id)
    if not cleaned:
        raise CalendarError("At least one calendar id is required.")
    return cleaned[:_MAX_FREEBUSY_CALENDARS]


def _audit_calendar(
    action: str,
    args_redacted: dict[str, Any],
    requested_by: str | None,
    result: str,
) -> None:
    try:
        record_audit_event(
            ToolAuditRecord(
                tool_name=f"calendar.{action}",
                risk_level=ToolRiskLevel.EXTERNAL_ACTION,
                args_redacted=args_redacted,
                result_summary=result,
                actor_id=requested_by,
            )
        )
    except Exception as exc:
        # Audit failures must not crash the caller (the user-facing action
        # already succeeded/failed by this point), but they MUST be logged
        # — otherwise we lose visibility into a broken audit pipeline.
        _log.warning("calendar_audit_failed", action=action, error=str(exc))
