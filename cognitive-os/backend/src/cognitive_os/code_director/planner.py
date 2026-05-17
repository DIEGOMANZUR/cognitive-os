"""Planners: turn a `CodeBuildRequest` into a `BuildPlan`.

Two implementations behind the `Planner` Protocol:

- `HeuristicPlanner` — deterministic scaffold→implement→review(+test). No
  LLM. Used as the always-available fallback and in tests.
- `LLMPlanner` — asks the configured primary LLM to decompose the
  objective into real, dependency-ordered subtasks with per-role
  adapter/model assignment. Falls back to the heuristic planner on ANY
  failure (no key, timeout, malformed JSON, schema mismatch) so a build
  request never dies because the planner LLM hiccuped.

The LLM call is injected (`llm_completion`) so unit tests exercise the
parsing/validation/fallback paths without spending a token.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import structlog

from cognitive_os.code_director.schemas import (
    BuildPlan,
    CodeBuildRequest,
    SubtaskSpec,
)

_log = structlog.get_logger(__name__)

# A minimal text-in/text-out LLM seam. Production wires it to the configured
# primary chat model; tests pass a deterministic stub.
LLMCompletion = Callable[[str], str]


class Planner(Protocol):
    def plan(self, request: CodeBuildRequest, *, workspace_dir: Path) -> BuildPlan: ...


# ---------------------------------------------------------------------------
# Heuristic (always available; also the fallback)
# ---------------------------------------------------------------------------


class HeuristicPlanner:
    """Deterministic three/four-stage plan. No LLM."""

    def plan(self, request: CodeBuildRequest, *, workspace_dir: Path) -> BuildPlan:
        coder_adapter, coder_model = request.adapter_preference.for_role("coder")
        reviewer_adapter, reviewer_model = request.adapter_preference.for_role("reviewer")
        tester_adapter, tester_model = request.adapter_preference.for_role("tester")

        subtasks: list[SubtaskSpec] = [
            SubtaskSpec(
                subtask_id="st-scaffold",
                title="Scaffold project structure",
                description=(
                    "Create the initial directory tree, dependency manifests "
                    "and minimal boilerplate satisfying the operator "
                    f"objective:\n\n{request.objective}\n\n"
                    + (f"Operator notes:\n{request.notes}\n" if request.notes else "")
                ),
                role="coder",
                adapter=coder_adapter,
                model=coder_model,
                expected_paths=["README.md", "pyproject.toml", "package.json"],
            ),
            SubtaskSpec(
                subtask_id="st-implement",
                title="Implement objective",
                description=(
                    "Implement the application end-to-end inside the "
                    "workspace. Write idiomatic, tested code. Honor any "
                    f"explicit constraints from the objective:\n\n{request.objective}"
                ),
                role="coder",
                adapter=coder_adapter,
                model=coder_model,
                depends_on=["st-scaffold"],
            ),
            SubtaskSpec(
                subtask_id="st-review",
                title="Self-review and propose fixes",
                description=(
                    "Review the workspace. Report problems found (missing "
                    "files, TODOs, untested branches). Propose concrete "
                    "patches or a human-readable summary."
                ),
                role="reviewer",
                adapter=reviewer_adapter,
                model=reviewer_model,
                depends_on=["st-implement"],
            ),
        ]
        if request.run_tests_in_sandbox:
            subtasks.append(
                SubtaskSpec(
                    subtask_id="st-test",
                    title="Run tests in sandbox",
                    description=(
                        "Execute the project's test suite inside "
                        "openshell_sandbox. Report failures with file:line."
                    ),
                    role="tester",
                    adapter=tester_adapter,
                    model=tester_model,
                    depends_on=["st-review"],
                )
            )

        estimated_calls = max(len(subtasks), int(len(request.objective) / 400))
        estimated_runtime = min(request.budget.max_runtime_minutes, max(5, estimated_calls * 2))
        return BuildPlan(
            workspace_dir=str(workspace_dir),
            subtasks=subtasks,
            estimated_runtime_minutes=estimated_runtime,
            estimated_calls=estimated_calls,
            estimated_cost_usd=request.budget.max_total_cost_usd,
            rationale=(
                "Heuristic planner: scaffold → implement → review (+ optional sandboxed test run)."
            ),
        )


# ---------------------------------------------------------------------------
# LLM-driven
# ---------------------------------------------------------------------------

_PLAN_SCHEMA_HINT = """\
Return ONLY a JSON object, no prose, with this exact shape:
{
  "subtasks": [
    {
      "subtask_id": "kebab-id",
      "title": "short imperative title",
      "description": "what the coding agent must do, self-contained",
      "role": "coder" | "reviewer" | "tester",
      "depends_on": ["other-subtask-id", ...],
      "expected_paths": ["relative/path", ...]
    }
  ],
  "rationale": "one paragraph: why this decomposition"
}
Rules:
- 2 to 12 subtasks. Order them so dependencies come first.
- The LAST subtask MUST be a "reviewer" role that checks the whole build.
- Only reference subtask_ids that exist in this same list in depends_on.
- expected_paths are hints (may be empty).
- Do NOT include adapter or model fields; the director assigns those.
"""


class LLMPlanner:
    """Decomposes the objective via the configured LLM, with heuristic fallback."""

    def __init__(
        self,
        *,
        llm_completion: LLMCompletion | None = None,
        fallback: Planner | None = None,
    ) -> None:
        self._llm = llm_completion
        self._fallback = fallback or HeuristicPlanner()

    def _resolve_llm(self) -> LLMCompletion | None:
        if self._llm is not None:
            return self._llm
        try:
            from cognitive_os.agents.llm_factory import (  # noqa: PLC0415
                create_primary_chat_model,
            )

            model = create_primary_chat_model()

            def _call(prompt: str) -> str:
                resp = model.invoke(prompt)
                content = getattr(resp, "content", resp)
                return content if isinstance(content, str) else str(content)

            return _call
        except Exception as exc:  # noqa: BLE001 - missing key / circuit open
            _log.info("llm_planner_unavailable", error_type=type(exc).__name__)
            return None

    def plan(self, request: CodeBuildRequest, *, workspace_dir: Path) -> BuildPlan:
        llm = self._resolve_llm()
        if llm is None:
            return self._fallback.plan(request, workspace_dir=workspace_dir)
        prompt = self._build_planning_prompt(request)
        try:
            raw = llm(prompt)
            parsed = _extract_json(raw)
            plan = self._assemble_plan(parsed, request, workspace_dir)
        except Exception as exc:  # noqa: BLE001 - any LLM/parse failure -> fallback
            _log.warning(
                "llm_planner_fell_back",
                error_type=type(exc).__name__,
                error=str(exc)[:200],
            )
            return self._fallback.plan(request, workspace_dir=workspace_dir)
        return plan

    @staticmethod
    def _build_planning_prompt(request: CodeBuildRequest) -> str:
        parts = [
            "You are a senior tech lead decomposing a software build into "
            "subtasks for autonomous coding agents.",
            "",
            "OBJECTIVE:",
            request.objective,
        ]
        if request.notes:
            parts += ["", "OPERATOR NOTES:", request.notes]
        if request.run_tests_in_sandbox:
            parts += [
                "",
                "The operator wants tests executed in a sandbox; include a "
                "final 'tester' subtask after the reviewer.",
            ]
        parts += ["", _PLAN_SCHEMA_HINT]
        return "\n".join(parts)

    def _assemble_plan(
        self,
        parsed: dict[str, object],
        request: CodeBuildRequest,
        workspace_dir: Path,
    ) -> BuildPlan:
        raw_subtasks = parsed.get("subtasks")
        if not isinstance(raw_subtasks, list) or not raw_subtasks:
            msg = "LLM plan has no subtasks"
            raise ValueError(msg)
        # Cap at 12 subtasks. If the original list had a reviewer at the
        # tail (per the schema hint), preserve it after the truncation so
        # we never deliver a plan without the final QA step.
        if len(raw_subtasks) > 12:
            tail_reviewer = None
            for candidate in reversed(raw_subtasks):
                if (
                    isinstance(candidate, dict)
                    and str(candidate.get("role", "")).strip().lower() == "reviewer"
                ):
                    tail_reviewer = candidate
                    break
            head = raw_subtasks[:12]
            if tail_reviewer is not None and tail_reviewer not in head:
                # Drop the last head item to make room for the reviewer so
                # the plan stays bounded at 12.
                head = head[:11] + [tail_reviewer]
            raw_subtasks = head

        ids: set[str] = set()
        subtasks: list[SubtaskSpec] = []
        for idx, item in enumerate(raw_subtasks):
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "coder")).strip().lower()
            if role not in {"coder", "reviewer", "tester", "planner"}:
                role = "coder"
            adapter, model = request.adapter_preference.for_role(
                role  # type: ignore[arg-type]
            )
            sid = str(item.get("subtask_id") or f"st-{idx + 1}").strip()[:64] or f"st-{idx + 1}"
            # depends_on is validated against the final id set after the loop.
            deps = [
                str(d).strip()
                for d in (item.get("depends_on") or [])
                if isinstance(d, str) and d.strip()
            ]
            paths = [
                str(p).strip()
                for p in (item.get("expected_paths") or [])
                if isinstance(p, str) and p.strip()
            ][:25]
            subtasks.append(
                SubtaskSpec(
                    subtask_id=sid,
                    title=str(item.get("title") or sid)[:200],
                    description=str(item.get("description") or "")[:8000]
                    or f"Work on: {request.objective[:200]}",
                    role=role,  # type: ignore[arg-type]
                    adapter=adapter,
                    model=model,
                    depends_on=deps,
                    expected_paths=paths,
                )
            )
            ids.add(sid)

        if not subtasks:
            msg = "LLM plan produced no usable subtasks"
            raise ValueError(msg)

        # Drop dependencies the LLM hallucinated (ids not in the plan) so the
        # director's topological sort never raises on planner output.
        for st in subtasks:
            st.depends_on = [d for d in st.depends_on if d in ids and d != st.subtask_id]

        estimated_calls = max(len(subtasks), int(len(request.objective) / 300))
        estimated_runtime = min(request.budget.max_runtime_minutes, max(5, estimated_calls * 3))
        rationale = str(parsed.get("rationale") or "LLM-decomposed build plan.")[:8000]
        return BuildPlan(
            workspace_dir=str(workspace_dir),
            subtasks=subtasks,
            estimated_runtime_minutes=estimated_runtime,
            estimated_calls=estimated_calls,
            estimated_cost_usd=request.budget.max_total_cost_usd,
            rationale=f"LLM planner: {rationale}",
        )


def _extract_json(raw: str) -> dict[str, object]:
    """Pull the first balanced JSON object out of an LLM response.

    Handles models that wrap JSON in ```json fences or add prose around it.
    """
    text = raw.strip()
    if text.startswith("```"):
        # strip ```json ... ``` fences
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    if start == -1:
        msg = "no JSON object in LLM response"
        raise ValueError(msg)
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                obj = json.loads(candidate)
                if not isinstance(obj, dict):
                    msg = "LLM JSON is not an object"
                    raise TypeError(msg)
                return obj
    msg = "unbalanced JSON in LLM response"
    raise ValueError(msg)


def default_planner() -> Planner:
    """Production planner: LLM-driven with heuristic fallback."""
    return LLMPlanner()


__all__ = [
    "HeuristicPlanner",
    "LLMCompletion",
    "LLMPlanner",
    "Planner",
    "default_planner",
]
