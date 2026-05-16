from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

from cognitive_os.actions.calendar import CalendarEvent, CalendarService, FakeCalendarProvider
from cognitive_os.actions.drive import DriveFile, DriveService, FakeDriveProvider
from cognitive_os.actions.maps import (
    FakeMapsProvider,
    GeocodeResult,
    MapsService,
    RoutePlan,
    RouteStep,
)
from cognitive_os.assist.note_index import NoteIndexService
from cognitive_os.assist.schemas import PersonalNoteView
from cognitive_os.core.config import Settings
from cognitive_os.deepagents.policies import DeepAgentPolicyViolation
from cognitive_os.deepagents.schemas import DeepAgentToolPolicy, DeepAgentWorkspace
from cognitive_os.deepagents.tools import (
    build_deepagent_tools,
    geocode_address,
    list_calendar_events,
    plan_route,
    search_drive_files,
    search_notes,
)
from tests.test_note_index import FakeNoteStore


def _workspace(tmp_path: Path) -> DeepAgentWorkspace:
    return DeepAgentWorkspace(
        root_dir=tmp_path / "ws",
        thread_id="t",
        task_id="task",
    )


def _maps_service(*, enabled: bool = True) -> MapsService:
    cfg = Settings.model_construct(
        enable_maps_routing=enabled,
        google_maps_api_key=SecretStr("AIzaTEST"),
        google_maps_base_url="https://maps.googleapis.com",
        maps_default_travel_mode="driving",
        http_timeout_seconds=5.0,
    )
    return MapsService(provider=FakeMapsProvider(), app_settings=cfg)


def _calendar_service(tmp_path: Path, *, enabled: bool = True) -> CalendarService:
    cfg = Settings.model_construct(
        enable_google_calendar=enabled,
        google_client_id="id.apps",
        google_token_dir=tmp_path,
        google_calendar_scopes=["https://www.googleapis.com/auth/calendar.events"],
        http_timeout_seconds=5.0,
    )
    provider = FakeCalendarProvider(
        events=[
            CalendarEvent(
                event_id="e1",
                summary="Reunión",
                start=datetime(2026, 6, 1, 10, tzinfo=UTC).isoformat(),
                end=datetime(2026, 6, 1, 11, tzinfo=UTC).isoformat(),
            )
        ]
    )
    return CalendarService(provider=provider, app_settings=cfg)


def _drive_service(tmp_path: Path, *, enabled: bool = True) -> DriveService:
    cfg = Settings.model_construct(
        enable_google_drive=enabled,
        google_client_id="id.apps",
        google_token_dir=tmp_path,
        google_drive_scopes=["https://www.googleapis.com/auth/drive"],
        google_drive_deliverables_folder_name="Cognitive OS Deliverables",
        http_timeout_seconds=5.0,
    )
    provider = FakeDriveProvider(
        files=[DriveFile(file_id="f1", name="informe.pdf", mime_type="application/pdf")]
    )
    return DriveService(provider=provider, app_settings=cfg)


def _note_index_with(notes: list[tuple[str, str, str, str]]) -> NoteIndexService:
    """notes = list of (note_id, user_id, title, body)."""
    service = NoteIndexService(store=FakeNoteStore())
    for note_id, user_id, title, body in notes:
        view = PersonalNoteView(
            id=note_id,
            user_id=user_id,
            title=title,
            body_markdown=body,
            tags=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        service.index_note(view)
    return service


def test_plan_route_returns_dump_when_policy_allows() -> None:
    policy = DeepAgentToolPolicy()
    result = plan_route(
        "Origen",
        "Destino",
        policy=policy,
        maps_service=_maps_service(),
    )
    assert result["origin"] == "Origen"
    assert result["destination"] == "Destino"
    assert result["distance_meters"] >= 0
    assert "travel_mode" in result


def test_plan_route_blocked_by_policy() -> None:
    policy = DeepAgentToolPolicy(allow_maps=False)
    result = plan_route("A", "B", policy=policy, maps_service=_maps_service())
    assert result == {
        "error": "policy_violation",
        "detail": "DeepAgent tool blocked by policy: plan_route",
    }


def test_plan_route_rejects_unknown_travel_mode() -> None:
    policy = DeepAgentToolPolicy()
    result = plan_route(
        "A",
        "B",
        travel_mode="teleport",
        policy=policy,
        maps_service=_maps_service(),
    )
    assert result["error"] == "ValueError"
    assert "travel_mode" in result["detail"]


def test_plan_route_handles_service_failure() -> None:
    cfg = Settings.model_construct(
        enable_maps_routing=False,
        google_maps_api_key=SecretStr("CHANGEME"),
        google_maps_base_url="https://maps.googleapis.com",
        maps_default_travel_mode="driving",
        http_timeout_seconds=5.0,
    )
    service = MapsService(provider=FakeMapsProvider(), app_settings=cfg)
    result = plan_route("A", "B", policy=DeepAgentToolPolicy(), maps_service=service)
    assert result["error"] == "MapsError"


def test_geocode_address_returns_dump() -> None:
    fake = FakeMapsProvider(
        geocode_results={
            "Apple Park": GeocodeResult(
                query="Apple Park",
                formatted_address="1 Infinite Loop, Cupertino, CA",
                latitude=37.33,
                longitude=-122.03,
            )
        }
    )
    cfg = Settings.model_construct(
        enable_maps_routing=True,
        google_maps_api_key=SecretStr("AIzaTEST"),
        google_maps_base_url="https://maps.googleapis.com",
        maps_default_travel_mode="driving",
        http_timeout_seconds=5.0,
    )
    service = MapsService(provider=fake, app_settings=cfg)
    result = geocode_address("Apple Park", policy=DeepAgentToolPolicy(), maps_service=service)
    assert result["latitude"] == pytest.approx(37.33)
    assert result["formatted_address"].startswith("1 Infinite Loop")


def test_list_calendar_events_returns_event_dumps(tmp_path: Path) -> None:
    result = list_calendar_events(
        days_ahead=7,
        max_results=5,
        policy=DeepAgentToolPolicy(),
        calendar_service=_calendar_service(tmp_path),
    )
    assert isinstance(result["events"], list)
    assert result["events"][0]["event_id"] == "e1"


def test_list_calendar_events_blocked_by_service(tmp_path: Path) -> None:
    result = list_calendar_events(
        days_ahead=7,
        max_results=5,
        policy=DeepAgentToolPolicy(),
        calendar_service=_calendar_service(tmp_path, enabled=False),
    )
    assert result["error"] == "CalendarError"


def test_search_drive_files_returns_file_dumps(tmp_path: Path) -> None:
    result = search_drive_files(
        query="informe",
        max_results=5,
        policy=DeepAgentToolPolicy(),
        drive_service=_drive_service(tmp_path),
    )
    assert result["files"][0]["file_id"] == "f1"


def test_search_drive_files_blocked_by_service(tmp_path: Path) -> None:
    result = search_drive_files(
        query="x",
        max_results=5,
        policy=DeepAgentToolPolicy(),
        drive_service=_drive_service(tmp_path, enabled=False),
    )
    assert result["error"] == "DriveError"


def test_search_notes_isolates_by_user() -> None:
    notes = [
        ("n1", "user-a", "Alpha", "compras"),
        ("n2", "user-a", "Beta", "compras supermercado"),
        ("n3", "user-b", "Gamma", "compras"),
    ]
    note_index = _note_index_with(notes)
    a_hits = search_notes(
        query="compras",
        limit=10,
        user_id="user-a",
        policy=DeepAgentToolPolicy(),
        note_index=note_index,
    )
    assert {hit["note_id"] for hit in a_hits["hits"]} == {"n1", "n2"}

    b_hits = search_notes(
        query="compras",
        limit=10,
        user_id="user-b",
        policy=DeepAgentToolPolicy(),
        note_index=note_index,
    )
    assert {hit["note_id"] for hit in b_hits["hits"]} == {"n3"}


def test_search_notes_returns_empty_without_user_scope() -> None:
    result = search_notes(
        query="x",
        limit=10,
        user_id=None,
        policy=DeepAgentToolPolicy(),
        note_index=NoteIndexService(store=FakeNoteStore()),
    )
    assert result["hits"] == []
    assert result["warning"] == "no_user_scope"


def test_search_notes_blocked_by_policy() -> None:
    result = search_notes(
        query="x",
        limit=10,
        user_id="user-a",
        policy=DeepAgentToolPolicy(allow_notes_read=False),
        note_index=NoteIndexService(store=FakeNoteStore()),
    )
    assert result["error"] == "policy_violation"


def test_build_deepagent_tools_exposes_new_personal_tools(tmp_path: Path) -> None:
    tools = build_deepagent_tools(
        policy=DeepAgentToolPolicy(),
        workspace=_workspace(tmp_path),
        allowed_doc_ids=["doc-1"],
        user_id="user-a",
    )
    names = {tool.name for tool in tools}
    assert {
        "plan_route",
        "geocode_address",
        "list_calendar_events",
        "search_drive_files",
        "search_notes",
        "solve_image_captcha",
        "solve_token_captcha",
    }.issubset(names)


def test_solve_image_captcha_tool_returns_text() -> None:
    from cognitive_os.actions.captcha import CaptchaSolverService, FakeCaptchaProvider
    from cognitive_os.deepagents.tools import solve_image_captcha

    cfg = Settings.model_construct(
        enable_captcha_solving=True,
        capsolver_api_key=SecretStr("CAP-REALKEY1234567890"),
        capsolver_base_url="https://api.capsolver.com",
        capsolver_poll_interval_seconds=0.0,
        capsolver_max_poll_seconds=10,
        http_timeout_seconds=5.0,
    )
    service = CaptchaSolverService(
        provider=FakeCaptchaProvider(create_response={"errorId": 0, "solution": {"text": "Z9Q"}}),
        app_settings=cfg,
    )
    result = solve_image_captcha(
        image_base64="aGk=",
        policy=DeepAgentToolPolicy(),
        captcha_service=service,
        user_id="user-a",
    )
    assert result == {"text": "Z9Q", "kind": "image_to_text"}


def test_solve_token_captcha_tool_blocked_by_policy() -> None:
    from cognitive_os.actions.captcha import CaptchaSolverService, FakeCaptchaProvider
    from cognitive_os.deepagents.tools import solve_token_captcha

    result = solve_token_captcha(
        kind="recaptcha_v2",
        website_url="https://x.com",
        website_key="k",
        page_action=None,
        policy=DeepAgentToolPolicy(allow_captcha_solving=False),
        captcha_service=CaptchaSolverService(provider=FakeCaptchaProvider()),
        user_id="user-a",
    )
    assert result["error"] == "policy_violation"


def test_policy_violation_class_used_by_other_tools_still_raises() -> None:
    # Sanity: blocking via policy still raises the right exception class
    # before being trapped by `_controlled_error`. This is documented behavior
    # of `validate_tool_allowed`.
    from cognitive_os.deepagents.policies import validate_tool_allowed

    with pytest.raises(DeepAgentPolicyViolation):
        validate_tool_allowed("plan_route", DeepAgentToolPolicy(allow_maps=False))


def test_plan_route_route_fields_round_trip_through_dump() -> None:
    """A fake route with explicit fields survives `.model_dump()` cleanly."""
    fake = FakeMapsProvider(
        route=RoutePlan(
            origin="A",
            destination="B",
            travel_mode="walking",
            distance_meters=500,
            duration_seconds=600,
            distance_text="500 m",
            duration_text="10 min",
            steps=[RouteStep(instruction="Camina recto", distance_meters=500)],
            intermediates=[],
        )
    )
    cfg = Settings.model_construct(
        enable_maps_routing=True,
        google_maps_api_key=SecretStr("AIzaTEST"),
        google_maps_base_url="https://maps.googleapis.com",
        maps_default_travel_mode="driving",
        http_timeout_seconds=5.0,
    )
    result = plan_route(
        "A",
        "B",
        travel_mode="walking",
        policy=DeepAgentToolPolicy(),
        maps_service=MapsService(provider=fake, app_settings=cfg),
    )
    assert result["distance_text"] == "500 m"
    assert result["steps"][0]["instruction"].startswith("Camina")
