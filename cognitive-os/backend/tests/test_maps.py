from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from cognitive_os.actions.maps import (
    FakeMapsProvider,
    GeocodeResult,
    GoogleMapsProvider,
    MapsError,
    MapsService,
    RoutePlan,
    RouteStep,
    _format_distance,
    _format_duration,
    _parse_duration_seconds,
    _redact,
)
from cognitive_os.api.app import app
from cognitive_os.core.config import Settings


def _settings(*, enabled: bool = True, key: str = "AIzaTESTKEY123456") -> Settings:
    return Settings.model_construct(
        enable_maps_routing=enabled,
        google_maps_api_key=SecretStr(key),
        google_maps_base_url="https://maps.googleapis.com",
        maps_default_travel_mode="driving",
        http_timeout_seconds=5.0,
    )


def test_status_reports_disabled_blocked_and_ready() -> None:
    assert MapsService(app_settings=_settings(enabled=False)).status().status == "disabled"
    assert MapsService(app_settings=_settings(key="CHANGEME")).status().status == "blocked"
    ready = MapsService(app_settings=_settings()).status()
    assert ready.status == "ready"
    assert ready.default_travel_mode == "driving"


def test_geocode_and_route_blocked_when_not_ready() -> None:
    service = MapsService(
        provider=FakeMapsProvider(),
        app_settings=_settings(enabled=False),
    )
    with pytest.raises(MapsError, match="ENABLE_MAPS_ROUTING"):
        service.geocode("anywhere")
    with pytest.raises(MapsError, match="ENABLE_MAPS_ROUTING"):
        service.plan_route(origin="a", destination="b")


def test_geocode_uses_provider_when_ready() -> None:
    provider = FakeMapsProvider(
        geocode_results={
            "Plaza Mayor": GeocodeResult(
                query="Plaza Mayor",
                formatted_address="Plaza Mayor, Madrid, Spain",
                latitude=40.4,
                longitude=-3.7,
                place_id="abc",
            )
        }
    )
    service = MapsService(provider=provider, app_settings=_settings())
    result = service.geocode("  Plaza Mayor  ")
    assert result.formatted_address == "Plaza Mayor, Madrid, Spain"
    assert provider.calls == ["geocode:Plaza Mayor"]


def test_plan_route_validates_inputs_and_caps_intermediates() -> None:
    service = MapsService(provider=FakeMapsProvider(), app_settings=_settings())
    with pytest.raises(MapsError, match="origin and destination"):
        service.plan_route(origin="  ", destination="b")
    with pytest.raises(MapsError, match="intermediate stops"):
        service.plan_route(
            origin="a",
            destination="b",
            intermediates=[f"stop-{i}" for i in range(11)],
        )


def test_plan_route_passes_mode_and_intermediates_to_provider() -> None:
    provider = FakeMapsProvider()
    service = MapsService(provider=provider, app_settings=_settings())
    plan = service.plan_route(
        origin="A",
        destination="B",
        intermediates=["  ", "C"],
        travel_mode="walking",
        compute_alternatives=True,
    )
    assert plan.travel_mode == "walking"
    assert plan.intermediates == ["C"]
    assert plan.google_maps_url.startswith("https://www.google.com/maps/dir/")
    assert plan.alternative_count == 1
    assert "ETA" not in plan.route_advice
    assert provider.calls == ["route:A->B"]


def test_geocode_provider_failure_surfaces_maps_error() -> None:
    service = MapsService(
        provider=FakeMapsProvider(raise_on={"geocode"}),
        app_settings=_settings(),
    )
    with pytest.raises(MapsError, match="fake geocode failure"):
        service.geocode("x")


def test_helpers_format_and_parse() -> None:
    assert _format_distance(2500) == "2.5 km"
    assert _format_distance(800) == "800 m"
    assert _format_duration(45) == "45 s"
    assert _format_duration(600) == "10 min"
    assert _format_duration(3720) == "1 h 2 min"
    assert _parse_duration_seconds("123s") == 123
    assert _parse_duration_seconds(90) == 90
    assert _parse_duration_seconds("bogus") == 0
    google_key_like = "AIza" + "SECRET123"
    assert _redact(f"error key={google_key_like} trailing") == "error key=[REDACTED] trailing"


def test_google_provider_geocode_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "status": "OK",
        "results": [
            {
                "formatted_address": "1 Infinite Loop, Cupertino, CA",
                "geometry": {"location": {"lat": 37.33, "lng": -122.03}},
                "place_id": "place-123",
            }
        ],
    }

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    provider = GoogleMapsProvider(_settings())
    result = provider.geocode("Apple Park")
    assert result.latitude == 37.33
    assert result.place_id == "place-123"


def test_google_provider_geocode_raises_on_zero_results(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "ZERO_RESULTS", "results": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(MapsError, match="Geocoding failed"):
        GoogleMapsProvider(_settings()).geocode("nowhere")


def test_google_provider_compute_route_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "routes": [
            {
                "distanceMeters": 5200,
                "duration": "780s",
                "staticDuration": "720s",
                "legs": [
                    {
                        "steps": [
                            {
                                "navigationInstruction": {"instructions": "Turn left"},
                                "distanceMeters": 200,
                            },
                            {
                                "navigationInstruction": {"instructions": "Continue straight"},
                                "distanceMeters": 5000,
                            },
                        ]
                    }
                ],
            }
        ]
    }

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        assert kwargs["json"]["computeAlternativeRoutes"] is True
        assert "routes.routeLabels" in kwargs["headers"]["X-Goog-FieldMask"]
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    plan = GoogleMapsProvider(_settings()).compute_route(
        origin="A",
        destination="B",
        intermediates=[],
        travel_mode="driving",
        traffic_aware=True,
        departure_time=None,
        compute_alternatives=True,
    )
    assert isinstance(plan, RoutePlan)
    assert plan.distance_meters == 5200
    assert plan.duration_seconds == 780
    assert plan.static_duration_seconds == 720
    assert plan.traffic_delay_seconds == 60
    assert plan.traffic_severity == "light"
    assert plan.traffic_aware is True
    assert plan.departure_time is not None
    assert plan.arrival_time is not None
    assert "Usa esta ruta" in plan.route_advice
    assert "origin=A" in plan.google_maps_url
    assert "destination=B" in plan.google_maps_url
    assert plan.distance_text == "5.2 km"
    assert plan.duration_text == "13 min"
    assert plan.steps == [
        RouteStep(instruction="Turn left", distance_meters=200),
        RouteStep(instruction="Continue straight", distance_meters=5000),
    ]


@pytest.mark.asyncio
async def test_maps_endpoints_require_auth() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status_resp = await client.get("/actions/maps/status")
        geocode_resp = await client.post("/actions/maps/geocode", json={"address": "x"})
        route_resp = await client.post(
            "/actions/maps/route",
            json={"origin": "a", "destination": "b"},
        )
    assert status_resp.status_code == 401
    assert geocode_resp.status_code == 401
    assert route_resp.status_code == 401
