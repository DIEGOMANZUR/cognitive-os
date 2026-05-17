"""F9b/F9c: the director builds context-aware, bounded prompts.

These tests prove the prompt the coding agent receives reflects live
workspace state, what upstream subtasks produced, and — on a retry —
the previous attempt's error (instead of replaying the same prompt).
All filesystem-only; no LLM, no token spend.
"""

from __future__ import annotations

from pathlib import Path

from cognitive_os.code_director.prompt_builder import (
    _MAX_TREE_ENTRIES,
    build_subtask_prompt,
)
from cognitive_os.code_director.schemas import (
    AdapterPreference,
    CodeBuildRequest,
    StepResult,
    SubtaskSpec,
)


def _request(**ov: object) -> CodeBuildRequest:
    base: dict[str, object] = {
        "objective": "Build a FastAPI service with a RAG endpoint" + " " * 40,
        "adapter_preference": AdapterPreference(default_adapter="claude_code"),
    }
    base.update(ov)
    return CodeBuildRequest(**base)


def _subtask(**ov: object) -> SubtaskSpec:
    base: dict[str, object] = {
        "subtask_id": "st-impl",
        "title": "Implement the RAG endpoint",
        "description": "Add POST /rag that retrieves and answers.",
        "role": "coder",
        "adapter": "claude_code",
    }
    base.update(ov)
    return SubtaskSpec(**base)


# ---- F9b: workspace + upstream context ------------------------------------


def test_prompt_lists_existing_workspace_files(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('hi')\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")

    prompt = build_subtask_prompt(subtask=_subtask(), request=_request(), workspace=tmp_path)
    assert "CURRENT WORKSPACE FILES:" in prompt
    assert "app/main.py" in prompt
    assert "pyproject.toml" in prompt


def test_prompt_says_empty_when_workspace_empty(tmp_path: Path) -> None:
    prompt = build_subtask_prompt(subtask=_subtask(), request=_request(), workspace=tmp_path)
    assert "workspace is empty" in prompt


def test_prompt_inlines_expected_path_contents(tmp_path: Path) -> None:
    (tmp_path / "models.py").write_text("class User:\n    id: int\n")
    prompt = build_subtask_prompt(
        subtask=_subtask(expected_paths=["models.py"]),
        request=_request(),
        workspace=tmp_path,
    )
    assert "RELEVANT FILE CONTENTS" in prompt
    assert "class User:" in prompt


def test_prompt_includes_upstream_outputs(tmp_path: Path) -> None:
    (tmp_path / "schema.py").write_text("TABLES = ['users']\n")
    up_spec = SubtaskSpec(
        subtask_id="st-schema",
        title="DB schema",
        description="make schema",
        role="coder",
        adapter="claude_code",
    )
    up_result = StepResult(
        success=True,
        stdout="created schema.py with users table",
        files_touched=["schema.py"],
    )
    prompt = build_subtask_prompt(
        subtask=_subtask(depends_on=["st-schema"]),
        request=_request(),
        workspace=tmp_path,
        upstream=[(up_spec, up_result)],
    )
    assert "WHAT UPSTREAM SUBTASKS PRODUCED" in prompt
    assert "st-schema" in prompt
    assert "created schema.py with users table" in prompt
    # And the upstream-touched file gets inlined for the dependent subtask.
    assert "TABLES = ['users']" in prompt


def test_prompt_never_reads_outside_workspace(tmp_path: Path) -> None:
    secret = tmp_path.parent / "secret.env"
    secret.write_text("API_KEY=supersecret")  # pragma: allowlist secret
    ws = tmp_path / "ws"
    ws.mkdir()
    prompt = build_subtask_prompt(
        subtask=_subtask(expected_paths=["../secret.env"]),
        request=_request(),
        workspace=ws,
    )
    assert "supersecret" not in prompt


def test_prompt_skips_binary_and_caps_listing(tmp_path: Path) -> None:
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02" * 10)
    for i in range(_MAX_TREE_ENTRIES + 50):
        (tmp_path / f"f{i:04d}.txt").write_text("x")
    prompt = build_subtask_prompt(
        subtask=_subtask(expected_paths=["blob.bin"]),
        request=_request(),
        workspace=tmp_path,
    )
    # Binary content never inlined.
    assert "\x00" not in prompt
    # Tree listing is bounded.
    assert "listing capped at" in prompt


# ---- F9c: error-directed retry --------------------------------------------


def test_first_attempt_has_no_failure_block(tmp_path: Path) -> None:
    prompt = build_subtask_prompt(
        subtask=_subtask(),
        request=_request(),
        workspace=tmp_path,
        attempt=0,
        last_result=None,
    )
    assert "PREVIOUS ATTEMPT" not in prompt


def test_retry_injects_previous_error_and_correction(tmp_path: Path) -> None:
    failed = StepResult(
        success=False,
        error="ModuleNotFoundError: no module named 'fastapi'",
        stderr="Traceback ...\n  File main.py line 1\n",
        exit_code=1,
    )
    prompt = build_subtask_prompt(
        subtask=_subtask(),
        request=_request(),
        workspace=tmp_path,
        attempt=1,
        last_result=failed,
    )
    assert "PREVIOUS ATTEMPT (#1) FAILED (exit code 1)" in prompt
    assert "Do NOT start over" in prompt
    assert "ModuleNotFoundError" in prompt
    assert "Traceback" in prompt


def test_retry_after_success_has_no_failure_block(tmp_path: Path) -> None:
    ok = StepResult(success=True, stdout="all good")
    prompt = build_subtask_prompt(
        subtask=_subtask(),
        request=_request(),
        workspace=tmp_path,
        attempt=1,
        last_result=ok,
    )
    assert "PREVIOUS ATTEMPT" not in prompt


def test_prompt_carries_objective_and_operator_notes(tmp_path: Path) -> None:
    prompt = build_subtask_prompt(
        subtask=_subtask(),
        request=_request(notes="Use Postgres, not SQLite."),
        workspace=tmp_path,
    )
    assert "OVERALL OBJECTIVE:" in prompt
    assert "OPERATOR NOTES:" in prompt
    assert "Use Postgres, not SQLite." in prompt
    assert "OUTPUT CONTRACT:" in prompt
