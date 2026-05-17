"""Context-aware prompt assembly for the Code Director (F9b + F9c).

The director never codes; it tells an autonomous coding agent *exactly*
what to do. A blind one-line prompt wastes the agent's turn — it
re-scaffolds files that already exist, ignores what upstream subtasks
produced, and on a retry it re-runs the same failing approach.

This module turns a `SubtaskSpec` plus live workspace state into a
structured, **strictly bounded** prompt that includes:

- the current workspace tree (so the agent does not recreate files);
- the contents of the most relevant files (expected paths + files
  upstream subtasks touched), truncated;
- a summary of what each upstream dependency produced;
- on a retry, the *previous attempt's* error/stderr with an explicit
  "fix this specific failure, do not start over" directive (F9c).

Everything here is pure string/filesystem work — no LLM, no network —
so it is fully unit-testable and can never spend a token. Every
inclusion is size-capped so a pathological workspace cannot blow up the
prompt (or the downstream context window / cost).
"""

from __future__ import annotations

from pathlib import Path

from cognitive_os.code_director.schemas import (
    CodeBuildRequest,
    StepResult,
    SubtaskSpec,
)

# --- hard bounds (a hostile workspace must not be able to exceed these) -----
_MAX_TREE_ENTRIES = 200
_MAX_FILE_BYTES = 16_384
_MAX_FILE_LINES = 160
_MAX_TOTAL_CONTENT_BYTES = 24_576
_MAX_RELEVANT_FILES = 12
_STDOUT_TAIL = 1_500
_ERROR_TAIL = 1_500
_STDERR_TAIL = 2_000
_FILES_TOUCHED_CAP = 40

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    ".turbo",
    ".cache",
    "target",
    ".idea",
    ".gradle",
}

# Conservative text allowlist: anything outside this is treated as binary
# and only ever listed in the tree, never inlined.
_TEXT_SUFFIXES = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".json",
    ".jsonc",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".env",
    ".md",
    ".rst",
    ".txt",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".sh",
    ".bash",
    ".dockerfile",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".rb",
    ".php",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".xml",
    ".gitignore",
    ".dockerignore",
}
_TEXT_NAMES = {
    "Dockerfile",
    "Makefile",
    "README",
    "LICENSE",
    ".gitignore",
    ".dockerignore",
    ".env.example",
}


def _is_text_path(path: Path) -> bool:
    if path.name in _TEXT_NAMES:
        return True
    return path.suffix.lower() in _TEXT_SUFFIXES


def _iter_workspace_files(root: Path) -> list[Path]:
    """Bounded, deterministic walk of the workspace.

    Skips VCS/build/cache dirs and hidden directories. Returns at most
    ``_MAX_TREE_ENTRIES`` files, sorted by relative path for stable
    prompts (so an unchanged workspace yields an unchanged prompt).
    """
    if not root.is_dir():
        return []
    out: list[Path] = []
    stack: list[Path] = [root]
    while stack and len(out) < _MAX_TREE_ENTRIES * 4:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if name in _SKIP_DIRS or (name.startswith(".") and name != "."):
                    continue
                stack.append(entry)
            elif entry.is_file():
                out.append(entry)
    out.sort(key=lambda p: str(p))
    return out[:_MAX_TREE_ENTRIES]


def _render_tree(root: Path, files: list[Path]) -> str:
    if not files:
        return "(workspace is empty — you are creating it from scratch)"
    lines: list[str] = []
    for f in files:
        try:
            rel = f.relative_to(root).as_posix()
            size = f.stat().st_size
        except (OSError, ValueError):
            continue
        lines.append(f"  {rel} ({size}B)")
    truncated = len(_iter_workspace_files(root)) >= _MAX_TREE_ENTRIES
    if truncated:
        lines.append(f"  ... (listing capped at {_MAX_TREE_ENTRIES} files)")
    return "\n".join(lines)


def _read_snippet(path: Path) -> str | None:
    """Read a bounded, text-only snippet, or None if not safely readable."""
    if not _is_text_path(path):
        return None
    try:
        if path.stat().st_size > _MAX_FILE_BYTES * 8:
            head = path.read_bytes()[:_MAX_FILE_BYTES]
        else:
            head = path.read_bytes()[: _MAX_FILE_BYTES * 8]
    except OSError:
        return None
    if b"\x00" in head[:1024]:
        return None  # looks binary despite the extension
    text = head.decode("utf-8", errors="replace")
    out_lines = text.splitlines()[:_MAX_FILE_LINES]
    snippet = "\n".join(out_lines)
    if len(snippet) > _MAX_FILE_BYTES:
        snippet = snippet[:_MAX_FILE_BYTES] + "\n... (truncated)"
    elif len(out_lines) >= _MAX_FILE_LINES:
        snippet += "\n... (truncated)"
    return snippet


def _relevant_paths(
    subtask: SubtaskSpec,
    upstream: list[tuple[SubtaskSpec, StepResult]],
) -> list[str]:
    """Order: this subtask's expected paths, then upstream-touched files.

    Deduplicated, order-preserving, capped. These are the files most
    likely to matter for the current step.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in subtask.expected_paths:
        rel = raw.strip().lstrip("/")
        if rel and rel not in seen:
            seen.add(rel)
            ordered.append(rel)
    for _spec, result in upstream:
        for raw in result.files_touched:
            rel = raw.strip().lstrip("/")
            if rel and rel not in seen:
                seen.add(rel)
                ordered.append(rel)
    return ordered[: _MAX_RELEVANT_FILES * 2]


def _render_relevant_files(root: Path, rels: list[str]) -> str:
    blocks: list[str] = []
    budget = _MAX_TOTAL_CONTENT_BYTES
    included = 0
    for rel in rels:
        if included >= _MAX_RELEVANT_FILES or budget <= 0:
            break
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue  # path-escape attempt — never read outside workspace
        if not candidate.is_file():
            continue
        snippet = _read_snippet(candidate)
        if snippet is None:
            continue
        snippet = snippet[:budget]
        budget -= len(snippet)
        included += 1
        blocks.append(f"--- {rel} ---\n{snippet}")
    if not blocks:
        return ""
    return "\n\n".join(blocks)


def _render_upstream(upstream: list[tuple[SubtaskSpec, StepResult]]) -> str:
    if not upstream:
        return ""
    chunks: list[str] = []
    for spec, result in upstream:
        status = "ok" if result.success else "FAILED"
        touched = result.files_touched[:_FILES_TOUCHED_CAP]
        touched_line = ", ".join(touched) if touched else "(none reported)"
        if len(result.files_touched) > _FILES_TOUCHED_CAP:
            touched_line += f", ... (+{len(result.files_touched) - _FILES_TOUCHED_CAP})"
        stdout_tail = result.stdout.strip()[-_STDOUT_TAIL:]
        part = [
            f"[{spec.subtask_id}] ({spec.role}) -> {status}",
            f"  files: {touched_line}",
        ]
        if stdout_tail:
            part.append(f"  output (tail):\n{_indent(stdout_tail, 4)}")
        chunks.append("\n".join(part))
    return "\n\n".join(chunks)


def _render_previous_failure(attempt: int, last_result: StepResult | None) -> str:
    """F9c: turn the prior failed attempt into a corrective directive."""
    if last_result is None or last_result.success:
        return ""
    err = (last_result.error or "").strip()[-_ERROR_TAIL:]
    stderr_tail = (last_result.stderr or "").strip()[-_STDERR_TAIL:]
    exit_part = f" (exit code {last_result.exit_code})" if last_result.exit_code is not None else ""
    lines = [
        f"YOUR PREVIOUS ATTEMPT (#{attempt}) FAILED{exit_part}.",
        "Do NOT start over or re-scaffold. Diagnose and fix the specific",
        "failure below, then re-run only what is needed to verify it.",
    ]
    if err:
        lines.append("\nError:\n" + _indent(err, 2))
    if stderr_tail:
        lines.append("\nStderr (tail):\n" + _indent(stderr_tail, 2))
    if not err and not stderr_tail:
        lines.append("\n(no error text was captured — inspect the workspace state)")
    return "\n".join(lines)


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line for line in text.splitlines())


def build_subtask_prompt(
    *,
    subtask: SubtaskSpec,
    request: CodeBuildRequest,
    workspace: Path,
    upstream: list[tuple[SubtaskSpec, StepResult]] | None = None,
    attempt: int = 0,
    last_result: StepResult | None = None,
) -> str:
    """Assemble the full, bounded prompt for one subtask attempt.

    ``upstream`` are the *completed direct dependencies* (spec, last
    result) so the agent sees what it can build on. ``attempt`` is the
    0-based retry index and ``last_result`` is this subtask's previous
    attempt — when that attempt failed, an error-directed correction
    block is injected (F9c) instead of replaying the same prompt.
    """
    upstream = upstream or []
    files = _iter_workspace_files(workspace)

    sections: list[str] = [
        "You are an autonomous coding agent working inside a sandboxed "
        "workspace. A director has decomposed a larger objective and is "
        "delegating ONE subtask to you. Make your changes directly in the "
        "workspace files. Keep changes minimal and focused on this subtask.",
        f"OVERALL OBJECTIVE:\n{request.objective}",
        (
            f"YOUR SUBTASK [{subtask.subtask_id}] (role: {subtask.role}):\n"
            f"{subtask.title}\n\n{subtask.description}"
        ),
        f"CURRENT WORKSPACE FILES:\n{_render_tree(workspace, files)}",
    ]

    relevant = _render_relevant_files(workspace, _relevant_paths(subtask, upstream))
    if relevant:
        sections.append(
            "RELEVANT FILE CONTENTS (already in the workspace — edit, do "
            f"not blindly recreate):\n{relevant}"
        )

    upstream_block = _render_upstream(upstream)
    if upstream_block:
        sections.append(f"WHAT UPSTREAM SUBTASKS PRODUCED (build on this):\n{upstream_block}")

    failure_block = _render_previous_failure(attempt, last_result)
    if failure_block:
        sections.append(failure_block)

    if subtask.expected_paths:
        sections.append(
            "EXPECTED PATHS TO CREATE/MODIFY:\n"
            + "\n".join(f"  - {p}" for p in subtask.expected_paths)
        )

    if request.notes:
        sections.append(f"OPERATOR NOTES:\n{request.notes}")

    sections.append(
        "OUTPUT CONTRACT: apply the changes to the workspace now. When "
        "done, print a short summary of which files you created or "
        "modified and why. If you could not finish, state precisely what "
        "blocked you so the director can plan a follow-up."
    )

    return "\n\n".join(sections)


__all__ = ["build_subtask_prompt"]
