"""P1 commercial-audit hardening — Health overall is honest.

Contract (AUDIT-2026-B closed; `docs/CURRENT_STATE.md` §Health):

  ``/health/dashboard`` overall MUST distinguish:
    * ``ok``        — every component verified live (or honestly disabled).
    * ``configured``— wiring complete but at least one component not probed.
    * ``degraded``  — any component broken or in an unknown state.

The existing test_health_dashboard.py exercises the live aggregation. This
file pins the rollup function ``_overall_status`` to a golden truth table
so a refactor cannot silently widen ``ok`` to include ``configured``
(precisely the misbehaviour the audit flagged).

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §D8/P1-07.
"""

from __future__ import annotations

import pytest

from cognitive_os.core.health import ComponentHealth, _overall_status


def _comp(name: str, status: str) -> ComponentHealth:
    return ComponentHealth(name=name, status=status)


# Truth table for the overall rollup.
TRUTH_TABLE: list[tuple[list[ComponentHealth], str, str]] = [
    # All verified live → ok
    (
        [_comp("a", "ok"), _comp("b", "ready"), _comp("c", "disabled")],
        "ok",
        "all_verified_or_disabled",
    ),
    # Any configured among verified → configured
    ([_comp("a", "ok"), _comp("b", "configured")], "configured", "mix_ok_and_configured"),
    # All configured → configured
    ([_comp("a", "configured"), _comp("b", "configured")], "configured", "all_configured"),
    # Any degraded → degraded (wins over configured/ok)
    ([_comp("a", "ok"), _comp("b", "degraded")], "degraded", "any_degraded"),
    # Unknown status family → degraded
    ([_comp("a", "ok"), _comp("b", "weird_status")], "degraded", "unknown_status"),
    # Empty list — degenerate but must not crash (defaults to "ok" because the
    # status set is empty and there is no configured/degraded element).
    ([], "ok", "empty_components"),
    # Only disabled
    ([_comp("a", "disabled"), _comp("b", "disabled")], "ok", "only_disabled"),
    # Configured + disabled → configured
    ([_comp("a", "configured"), _comp("b", "disabled")], "configured", "configured_and_disabled"),
]


@pytest.mark.parametrize(
    ("components", "expected", "label"),
    TRUTH_TABLE,
    ids=[row[-1] for row in TRUTH_TABLE],
)
def test_overall_status_truth_table(
    components: list[ComponentHealth], expected: str, label: str
) -> None:
    del label
    assert _overall_status(components) == expected


def test_overall_status_configured_never_paints_ok() -> None:
    """Regression for AUDIT-2026-B (configured ≠ ok)."""
    components = [
        _comp("postgres", "ok"),
        _comp("primary_llm", "configured"),
        _comp("embeddings", "configured"),
        _comp("mail", "configured"),
    ]
    assert _overall_status(components) == "configured"
    # Critical: the overall MUST NOT be "ok" when any component is merely
    # configured. The historical bug painted such dashboards green.
    assert _overall_status(components) != "ok"


def test_overall_status_degraded_wins_over_configured() -> None:
    components = [
        _comp("postgres", "ok"),
        _comp("primary_llm", "configured"),
        _comp("redis", "degraded"),
    ]
    assert _overall_status(components) == "degraded"


def test_overall_status_handles_ready_as_verified() -> None:
    """`ready` is the verified-state for services that don't expose latency."""
    components = [_comp("godaddy", "ready"), _comp("kimi", "ok")]
    assert _overall_status(components) == "ok"
