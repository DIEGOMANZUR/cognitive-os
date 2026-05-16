"""Google Maps routing & geocoding (read-only).

`MapsService` exposes geocoding and route planning for the personal assistant.
Both are read-only Google API queries with no real-world side effect, so they
do not flow through the `ActionRequest`/approval lifecycle — they are JWT-gated
informational endpoints like the Gmail digest.

The real provider talks to the Routes API (`routes.googleapis.com`) and the
Geocoding API (`maps.googleapis.com`) with a restricted API key. Tests inject
`FakeMapsProvider`, so the suite never touches the network.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field

from cognitive_os.core.config import Settings, settings
from cognitive_os.core.resilience import retry_transient_http

TravelMode = Literal["driving", "walking", "bicycling", "transit"]
_TRAVEL_MODE_API = {
    "driving": "DRIVE",
    "walking": "WALK",
    "bicycling": "BICYCLE",
    "transit": "TRANSIT",
}
_MAX_INTERMEDIATES = 10
_KEY_RE = re.compile(r"(?i)(key=)[A-Za-z0-9._-]+")


class MapsError(RuntimeError):
    """Raised when a Maps query cannot be completed."""


def _redact(value: str) -> str:
    """Strip a leaked `key=` query parameter from any error string."""
    return _KEY_RE.sub(r"\1[REDACTED]", value)


class GeocodeResult(BaseModel):
    query: str
    formatted_address: str
    latitude: float
    longitude: float
    place_id: str | None = None


class RouteStep(BaseModel):
    instruction: str
    distance_meters: int = 0


class RoutePlan(BaseModel):
    origin: str
    destination: str
    travel_mode: TravelMode
    distance_meters: int
    duration_seconds: int
    distance_text: str
    duration_text: str
    static_duration_seconds: int | None = None
    static_duration_text: str | None = None
    traffic_delay_seconds: int | None = None
    traffic_delay_text: str | None = None
    traffic_aware: bool = False
    google_maps_url: str = ""
    steps: list[RouteStep] = Field(default_factory=list)
    intermediates: list[str] = Field(default_factory=list)


class MapsStatus(BaseModel):
    status: Literal["disabled", "blocked", "ready"]
    reason: str | None = None
    default_travel_mode: TravelMode


class GeocodeRequest(BaseModel):
    address: str = Field(min_length=1, max_length=500)


class RouteRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=500)
    destination: str = Field(min_length=1, max_length=500)
    intermediates: list[str] = Field(default_factory=list, max_length=_MAX_INTERMEDIATES)
    travel_mode: TravelMode | None = None
    traffic_aware: bool = True
    departure_time: datetime | None = None


class MapsProvider(Protocol):
    def geocode(self, address: str) -> GeocodeResult: ...

    def compute_route(
        self,
        *,
        origin: str,
        destination: str,
        intermediates: list[str],
        travel_mode: TravelMode,
        traffic_aware: bool,
        departure_time: datetime | None,
    ) -> RoutePlan: ...


class FakeMapsProvider:
    """Deterministic in-memory provider for tests."""

    def __init__(
        self,
        *,
        geocode_results: dict[str, GeocodeResult] | None = None,
        route: RoutePlan | None = None,
        raise_on: set[str] | None = None,
    ) -> None:
        self._geocode_results = geocode_results or {}
        self._route = route
        self._raise_on = raise_on or set()
        self.calls: list[str] = []

    def geocode(self, address: str) -> GeocodeResult:
        self.calls.append(f"geocode:{address}")
        if "geocode" in self._raise_on:
            raise MapsError("fake geocode failure")
        if address in self._geocode_results:
            return self._geocode_results[address]
        return GeocodeResult(
            query=address,
            formatted_address=f"{address} (fake)",
            latitude=0.0,
            longitude=0.0,
            place_id=None,
        )

    def compute_route(
        self,
        *,
        origin: str,
        destination: str,
        intermediates: list[str],
        travel_mode: TravelMode,
        traffic_aware: bool,
        departure_time: datetime | None,
    ) -> RoutePlan:
        self.calls.append(f"route:{origin}->{destination}")
        if "route" in self._raise_on:
            raise MapsError("fake route failure")
        if self._route is not None:
            return self._route
        return RoutePlan(
            origin=origin,
            destination=destination,
            travel_mode=travel_mode,
            distance_meters=1000,
            duration_seconds=600,
            distance_text="1.0 km",
            duration_text="10 min",
            static_duration_seconds=540 if traffic_aware and travel_mode == "driving" else None,
            static_duration_text="9 min" if traffic_aware and travel_mode == "driving" else None,
            traffic_delay_seconds=60 if traffic_aware and travel_mode == "driving" else None,
            traffic_delay_text="1 min" if traffic_aware and travel_mode == "driving" else None,
            traffic_aware=traffic_aware and travel_mode == "driving",
            google_maps_url=_build_google_maps_url(
                origin=origin,
                destination=destination,
                intermediates=intermediates,
                travel_mode=travel_mode,
            ),
            steps=[RouteStep(instruction="Head to destination", distance_meters=1000)],
            intermediates=list(intermediates),
        )


def _format_distance(meters: int) -> str:
    if meters >= 1000:
        return f"{meters / 1000:.1f} km"
    return f"{meters} m"


def _format_duration(seconds: int) -> str:
    minutes = seconds // 60
    if minutes >= 60:
        hours, rem = divmod(minutes, 60)
        return f"{hours} h {rem} min" if rem else f"{hours} h"
    return f"{minutes} min" if minutes else f"{seconds} s"


def _parse_duration_seconds(raw: object) -> int:
    """Routes API returns durations as a string like `"123s"`."""
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, str):
        match = re.match(r"^(\d+(?:\.\d+)?)s$", raw.strip())
        if match:
            return int(float(match.group(1)))
    return 0


def _build_google_maps_url(
    *,
    origin: str,
    destination: str,
    intermediates: list[str],
    travel_mode: TravelMode,
) -> str:
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": travel_mode,
    }
    if intermediates:
        params["waypoints"] = "|".join(intermediates)
    return f"https://www.google.com/maps/dir/?{urlencode(params)}"


class GoogleMapsProvider:
    """Real provider: Routes API for directions, Geocoding API for addresses."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings
        self._timeout = app_settings.http_timeout_seconds

    @property
    def _api_key(self) -> str:
        return self._settings.google_maps_api_key.get_secret_value()

    def geocode(self, address: str) -> GeocodeResult:
        url = f"{self._settings.google_maps_base_url.rstrip('/')}/maps/api/geocode/json"
        try:
            response = retry_transient_http(
                lambda: httpx.get(
                    url,
                    params={"address": address, "key": self._api_key},
                    timeout=self._timeout,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise MapsError(f"Geocoding request failed: {_redact(str(exc))}") from exc
        except ValueError as exc:
            raise MapsError("Geocoding API returned invalid JSON.") from exc

        status = str(payload.get("status") or "")
        results = payload.get("results") or []
        if status != "OK" or not results:
            reason = payload.get("error_message") or status or "no results"
            raise MapsError(f"Geocoding failed for {address!r}: {reason}")
        top = results[0]
        location = (top.get("geometry") or {}).get("location") or {}
        return GeocodeResult(
            query=address,
            formatted_address=str(top.get("formatted_address") or address),
            latitude=float(location.get("lat", 0.0)),
            longitude=float(location.get("lng", 0.0)),
            place_id=str(top.get("place_id")) if top.get("place_id") else None,
        )

    def compute_route(
        self,
        *,
        origin: str,
        destination: str,
        intermediates: list[str],
        travel_mode: TravelMode,
        traffic_aware: bool,
        departure_time: datetime | None,
    ) -> RoutePlan:
        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        body: dict[str, Any] = {
            "origin": {"address": origin},
            "destination": {"address": destination},
            "travelMode": _TRAVEL_MODE_API[travel_mode],
        }
        if intermediates:
            body["intermediates"] = [{"address": stop} for stop in intermediates]
        effective_traffic = traffic_aware and travel_mode == "driving"
        if effective_traffic:
            body["routingPreference"] = "TRAFFIC_AWARE_OPTIMAL"
            departure = departure_time or datetime.now(tz=UTC)
            body["departureTime"] = departure.astimezone(UTC).isoformat().replace("+00:00", "Z")
        field_mask = (
            "routes.distanceMeters,routes.duration,routes.staticDuration,"
            "routes.legs.steps.navigationInstruction,"
            "routes.legs.steps.distanceMeters"
        )
        try:
            response = retry_transient_http(
                lambda: httpx.post(
                    url,
                    json=body,
                    headers={
                        "X-Goog-Api-Key": self._api_key,
                        "X-Goog-FieldMask": field_mask,
                    },
                    timeout=self._timeout,
                )
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise MapsError(f"Routes request failed: {_redact(str(exc))}") from exc
        except ValueError as exc:
            raise MapsError("Routes API returned invalid JSON.") from exc

        routes = payload.get("routes") or []
        if not routes:
            raise MapsError(f"No route found from {origin!r} to {destination!r}.")
        route = routes[0]
        distance_meters = int(route.get("distanceMeters", 0))
        duration_seconds = _parse_duration_seconds(route.get("duration"))
        static_duration_seconds = _parse_duration_seconds(route.get("staticDuration")) or None
        traffic_delay_seconds = None
        if static_duration_seconds is not None:
            traffic_delay_seconds = max(0, duration_seconds - static_duration_seconds)
        steps: list[RouteStep] = []
        for leg in route.get("legs") or []:
            for step in leg.get("steps") or []:
                instruction = (step.get("navigationInstruction") or {}).get("instructions")
                if instruction:
                    steps.append(
                        RouteStep(
                            instruction=str(instruction),
                            distance_meters=int(step.get("distanceMeters", 0)),
                        )
                    )
        return RoutePlan(
            origin=origin,
            destination=destination,
            travel_mode=travel_mode,
            distance_meters=distance_meters,
            duration_seconds=duration_seconds,
            distance_text=_format_distance(distance_meters),
            duration_text=_format_duration(duration_seconds),
            static_duration_seconds=static_duration_seconds,
            static_duration_text=(
                _format_duration(static_duration_seconds)
                if static_duration_seconds is not None
                else None
            ),
            traffic_delay_seconds=traffic_delay_seconds,
            traffic_delay_text=(
                _format_duration(traffic_delay_seconds)
                if traffic_delay_seconds is not None
                else None
            ),
            traffic_aware=effective_traffic,
            google_maps_url=_build_google_maps_url(
                origin=origin,
                destination=destination,
                intermediates=intermediates,
                travel_mode=travel_mode,
            ),
            steps=steps,
            intermediates=list(intermediates),
        )


class MapsService:
    """Read-only routing/geocoding facade with capability gating."""

    def __init__(
        self,
        provider: MapsProvider | None = None,
        app_settings: Settings = settings,
    ) -> None:
        self._settings = app_settings
        self._provider = provider

    def _resolve_provider(self) -> MapsProvider:
        if self._provider is None:
            self._provider = GoogleMapsProvider(self._settings)
        return self._provider

    def status(self) -> MapsStatus:
        default_mode: TravelMode = self._settings.maps_default_travel_mode
        if not self._settings.enable_maps_routing:
            return MapsStatus(
                status="disabled",
                reason="ENABLE_MAPS_ROUTING is false.",
                default_travel_mode=default_mode,
            )
        key = self._settings.google_maps_api_key.get_secret_value()
        if not key or "CHANGEME" in key:
            return MapsStatus(
                status="blocked",
                reason="GOOGLE_MAPS_API_KEY is not configured.",
                default_travel_mode=default_mode,
            )
        return MapsStatus(status="ready", reason=None, default_travel_mode=default_mode)

    def _require_ready(self) -> None:
        current = self.status()
        if current.status != "ready":
            raise MapsError(current.reason or "Maps routing is not available.")

    def geocode(self, address: str) -> GeocodeResult:
        cleaned = address.strip()
        if not cleaned:
            raise MapsError("Address must not be empty.")
        self._require_ready()
        return self._resolve_provider().geocode(cleaned)

    def plan_route(
        self,
        *,
        origin: str,
        destination: str,
        intermediates: list[str] | None = None,
        travel_mode: TravelMode | None = None,
        traffic_aware: bool = True,
        departure_time: datetime | None = None,
    ) -> RoutePlan:
        origin_clean = origin.strip()
        destination_clean = destination.strip()
        if not origin_clean or not destination_clean:
            raise MapsError("Both origin and destination are required.")
        stops = [stop.strip() for stop in (intermediates or []) if stop.strip()]
        if len(stops) > _MAX_INTERMEDIATES:
            raise MapsError(f"At most {_MAX_INTERMEDIATES} intermediate stops are allowed.")
        self._require_ready()
        mode: TravelMode = travel_mode or self._settings.maps_default_travel_mode
        return self._resolve_provider().compute_route(
            origin=origin_clean,
            destination=destination_clean,
            intermediates=stops,
            travel_mode=mode,
            traffic_aware=traffic_aware,
            departure_time=departure_time,
        )
