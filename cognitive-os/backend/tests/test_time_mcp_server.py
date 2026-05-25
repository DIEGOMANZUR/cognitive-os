from __future__ import annotations

import datetime as dt

import pytest

from cognitive_os.integrations import time_mcp_server


def test_time_convert_requires_explicit_timezone() -> None:
    with pytest.raises(ValueError, match="explicit timezone"):
        time_mcp_server.time_convert("2026-05-25T02:00:00", "America/Santiago")


def test_time_convert_to_america_santiago() -> None:
    result = time_mcp_server.time_convert(
        "2026-05-25T02:00:00Z",
        "America/Santiago",
        locale="es-CL",
    )

    assert result["iso_utc"] == "2026-05-25T02:00:00.000Z"
    assert result["local_datetime"] == "2026-05-24T22:00:00-04:00"
    assert result["date"] == "2026-05-24"
    assert result["time"] == "22:00:00"
    assert result["weekday"] == "domingo"
    assert result["utc_offset"] == "-04:00"
    assert result["utc_offset_minutes"] == -240


def test_describe_time_defaults_to_english_weekday() -> None:
    result = time_mcp_server.describe_time(
        dt.datetime(2026, 5, 25, 2, 0, 0, tzinfo=dt.UTC),
        "UTC",
    )

    assert result["local_datetime"] == "2026-05-25T02:00:00+00:00"
    assert result["weekday"] == "Monday"


def test_rejects_invalid_timezone() -> None:
    with pytest.raises(ValueError, match="Invalid IANA timezone"):
        time_mcp_server.time_now("Chile/Nowhere")
