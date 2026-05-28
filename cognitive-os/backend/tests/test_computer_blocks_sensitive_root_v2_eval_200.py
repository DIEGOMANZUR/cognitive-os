"""Regression tests for V2-EVAL-200 (P1).

The Prompt 5 independent evaluator found that
`POST /actions/computer/inventory` with `root_path=/home/jgonz/.ssh,
include_hidden=true, recursive=true` returned `status=ok` and listed
`id_ed25519`, `id_ed25519.pub`, `known_hosts` — SSH private key metadata
leak. Same bypass applied to `build_organize_plan`.

Root cause: `_is_sensitive_path(relative)` walked path parts RELATIVE to root,
so `~/.ssh/id_ed25519` with `root=~/.ssh` yields `relative=id_ed25519` (no
`.ssh` component) and the check passed.

Fix (in `cognitive_os/actions/computer.py`): new `_is_sensitive_root(root)`
helper checks the resolved absolute root against `SENSITIVE_PATH_MARKERS`,
called from `build_organize_plan`, `build_inventory`, and
`execute_organize_plan`.

These tests assert the regression cannot recur by:
1. Direct unit test of `_is_sensitive_root` against 4 sensitive paths.
2. End-to-end test of `ComputerActionService.build_inventory` and
   `build_organize_plan` against the same sensitive paths.
3. End-to-end test that legitimate non-sensitive subpaths of HOME still work
   (so the fix does not over-block).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cognitive_os.actions.computer import (
    ComputerActionService,
    _is_sensitive_root,
)
from cognitive_os.actions.schemas import (
    ComputerInventoryRequest,
    ComputerOrganizeRequest,
)
from cognitive_os.core.config import Settings

SENSITIVE_ROOT_PATHS = [
    ".ssh",
    ".gnupg",
    "credentials",
    "secret_store/tokens",
]


@pytest.mark.parametrize("rel_sensitive", SENSITIVE_ROOT_PATHS)
def test_is_sensitive_root_detects_marker_in_resolved_path(
    tmp_path: Path,
    rel_sensitive: str,
) -> None:
    """Unit-level: the helper detects markers anywhere in the resolved path."""
    target = tmp_path / rel_sensitive
    target.mkdir(parents=True)
    assert _is_sensitive_root(target) is True, (
        f"_is_sensitive_root({target}) should be True (contains marker)"
    )


def test_is_sensitive_root_allows_neutral_root(tmp_path: Path) -> None:
    """Negative control: a benign directory passes."""
    target = tmp_path / "Documents" / "Reports"
    target.mkdir(parents=True)
    assert _is_sensitive_root(target) is False


def test_is_sensitive_root_detects_via_resolve_strict_false(tmp_path: Path) -> None:
    """Even when the path does not exist, the marker check applies (resolve
    with strict=False returns the would-be absolute path)."""
    target = tmp_path / "future" / ".ssh"
    assert _is_sensitive_root(target) is True


def _make_service(allowed_root: Path) -> ComputerActionService:
    """Build a `ComputerActionService` that allows `allowed_root` and enables actions."""
    settings = Settings.model_construct(
        enable_computer_actions=True,
        computer_allowed_roots=[str(allowed_root)],
        computer_max_files_per_plan=100,
        computer_organize_dry_run_only=False,
        local_storage_dir=str(allowed_root / ".storage"),
        operator_profile="dedicated_local",
        local_autonomy_mode="full",
        approval_require_four_eyes=False,
    )
    return ComputerActionService(app_settings=settings)


@pytest.mark.parametrize("rel_sensitive", SENSITIVE_ROOT_PATHS)
def test_build_inventory_rejects_sensitive_root(
    tmp_path: Path,
    rel_sensitive: str,
) -> None:
    """ComputerActionService.build_inventory returns status=blocked when the root
    resolves under a sensitive marker, even with include_hidden=True."""
    root = tmp_path / rel_sensitive
    root.mkdir(parents=True)
    (root / "id_ed25519").write_text("FAKE_KEY_NO_REAL")
    service = _make_service(tmp_path)

    result = service.build_inventory(
        ComputerInventoryRequest(
            root_path=str(root),
            include_hidden=True,
            recursive=True,
        )
    )

    assert result.status == "blocked", f"expected blocked, got {result.status}"
    assert "sensitive" in (result.reason or "").lower()


@pytest.mark.parametrize("rel_sensitive", SENSITIVE_ROOT_PATHS)
def test_build_organize_plan_rejects_sensitive_root(
    tmp_path: Path,
    rel_sensitive: str,
) -> None:
    """ComputerActionService.build_organize_plan returns status=blocked when the root
    resolves under a sensitive marker."""
    root = tmp_path / rel_sensitive
    root.mkdir(parents=True)
    (root / "config").write_text("fake")
    service = _make_service(tmp_path)

    plan = service.build_organize_plan(
        ComputerOrganizeRequest(root_path=str(root), strategy="by_type")
    )

    assert plan.status == "blocked", f"expected blocked, got {plan.status}"
    assert "sensitive" in (plan.reason or "").lower()


def test_build_inventory_allows_neutral_subpath_of_home(tmp_path: Path) -> None:
    """Negative control end-to-end: a benign subpath of the allow-list root
    still returns status=completed (the fix does not over-block)."""
    root = tmp_path / "Documents"
    root.mkdir()
    (root / "report.pdf").write_text("hello")
    service = _make_service(tmp_path)

    result = service.build_inventory(ComputerInventoryRequest(root_path=str(root), recursive=True))

    assert result.status == "completed", (
        f"benign root must not be blocked; got {result.status} ({result.reason})"
    )
    assert result.file_count >= 1


def test_build_organize_plan_allows_neutral_subpath_of_home(tmp_path: Path) -> None:
    """Negative control end-to-end for organize plan."""
    root = tmp_path / "Inbox"
    root.mkdir()
    (root / "draft.txt").write_text("draft")
    service = _make_service(tmp_path)

    plan = service.build_organize_plan(
        ComputerOrganizeRequest(root_path=str(root), strategy="by_type")
    )

    assert plan.status == "ok", f"benign root must not be blocked; got {plan.status}"
