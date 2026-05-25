"""Local read-only MCP server for time utilities."""

from __future__ import annotations

import datetime as dt
import os
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import FastMCP

_EXPLICIT_TZ_RE = re.compile(r"(?:Z|[+-]\d{2}:?\d{2})$", re.IGNORECASE)
_WEEKDAYS_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
_WEEKDAYS_ES = (
    "lunes",
    "martes",
    "mi\u00e9rcoles",
    "jueves",
    "viernes",
    "s\u00e1bado",
    "domingo",
)


def _zone_info(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        msg = f"Invalid IANA timezone: {timezone}"
        raise ValueError(msg) from exc


def _is_valid_timezone(timezone: str | None) -> bool:
    if not timezone:
        return False
    try:
        _zone_info(timezone)
    except ValueError:
        return False
    return True


def _default_timezone() -> str:
    candidates = (
        os.environ.get("TIME_MCP_DEFAULT_TIMEZONE"),
        os.environ.get("TZ"),
        "America/Santiago",
        "UTC",
    )
    for candidate in candidates:
        if candidate and _is_valid_timezone(candidate):
            return candidate
    return "UTC"


DEFAULT_TIMEZONE = _default_timezone()
mcp = FastMCP(name="cognitive-os-time")


def _format_offset(total_minutes: int) -> str:
    sign = "+" if total_minutes >= 0 else "-"
    absolute = abs(total_minutes)
    hours, minutes = divmod(absolute, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _weekday_name(index: int, locale: str) -> str:
    language = locale.replace("_", "-").split("-", maxsplit=1)[0].lower()
    if language == "es":
        return _WEEKDAYS_ES[index]
    return _WEEKDAYS_EN[index]


def describe_time(value: dt.datetime, timezone: str, locale: str = "en-US") -> dict[str, str | int]:
    """Return a stable JSON-serializable description of a datetime."""
    zone = _zone_info(timezone)
    utc_value = value.astimezone(dt.UTC) if value.tzinfo else value.replace(tzinfo=dt.UTC)
    local_value = utc_value.astimezone(zone)
    offset = local_value.utcoffset() or dt.timedelta()
    offset_minutes = round(offset.total_seconds() / 60)
    offset_text = _format_offset(offset_minutes)
    date_text = local_value.strftime("%Y-%m-%d")
    time_text = local_value.strftime("%H:%M:%S")

    return {
        "timezone": timezone,
        "locale": locale,
        "unix_ms": int(utc_value.timestamp() * 1000),
        "iso_utc": utc_value.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "local_datetime": f"{date_text}T{time_text}{offset_text}",
        "date": date_text,
        "time": time_text,
        "weekday": _weekday_name(local_value.weekday(), locale),
        "utc_offset": offset_text,
        "utc_offset_minutes": offset_minutes,
    }


@mcp.tool()
def time_now(timezone: str = DEFAULT_TIMEZONE, locale: str = "en-US") -> dict[str, str | int]:
    """Return the current time in an IANA timezone."""
    return describe_time(dt.datetime.now(dt.UTC), timezone, locale)


@mcp.tool()
def time_convert(
    datetime: str,
    timezone: str,
    locale: str = "en-US",
) -> dict[str, str | int]:
    """Convert an ISO 8601 datetime with explicit Z/offset to an IANA timezone."""
    if not _EXPLICIT_TZ_RE.search(datetime):
        msg = "datetime must include an explicit timezone suffix: Z, +HH:MM, or -HH:MM"
        raise ValueError(msg)
    normalized = re.sub(r"Z$", "+00:00", datetime, flags=re.IGNORECASE)
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        msg = f"Invalid ISO datetime: {datetime}"
        raise ValueError(msg) from exc
    return describe_time(parsed, timezone, locale)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
