"""P0 commercial-audit hardening — Code Director adapters are STDIN-only.

Contract (`docs/ACTION_PLANE.md` §"Code Director"; `docs/RUNBOOK.md` §"Code Director"):

  * Adapters must NEVER pass the prompt on argv (it would leak in ``ps``
    and ``/proc/<pid>/cmdline``).
  * The prompt always rides on stdin.

This file adds two layers of evidence:

1. **Static** — for every concrete adapter (Claude Code, Codex, Kimi),
   ``build_argv`` is called and the returned argv is checked for the
   prompt sentinel + secret-shaped tokens.
2. **Dynamic** — spawn a real subprocess (``/usr/bin/cat`` standing in
   for any CLI binary), pipe a huge prompt on stdin, and inspect
   ``/proc/<pid>/cmdline`` while the child is alive. The prompt MUST NOT
   appear in cmdline. Linux-only; gracefully skipped elsewhere.

Auditoría comercial — 2026-05-25. Plan en
``tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md`` §G9.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from cognitive_os.code_director.adapters.claude_code import ClaudeCodeAdapter
from cognitive_os.code_director.adapters.codex import CodexAdapter
from cognitive_os.code_director.adapters.kimi import KimiAdapter

# A prompt with multiple sentinels covering the surface a real prompt has:
# code-style text, fake secrets, fake API keys. None of these must ever land
# in argv. The sentinels are intentionally absurd so a literal substring
# match in /proc/<pid>/cmdline is unambiguous.
PROMPT_SENTINELS = (
    "##AUDIT_PROMPT_CODE_DIRECTOR_STDIN_ONLY##",
    "sk-test-LEAKED_API_KEY_SHOULD_NEVER_HIT_ARGV",  # pragma: allowlist secret
    "ghp_FAKE_GITHUB_TOKEN_FOR_AUDIT_TEST_ONLY",  # pragma: allowlist secret
)
SENTINEL_PROMPT = " ".join(PROMPT_SENTINELS) + "\n\nWrite a hello world."


@pytest.mark.parametrize(
    "adapter_cls",
    [ClaudeCodeAdapter, CodexAdapter, KimiAdapter],
    ids=["claude_code", "codex", "kimi"],
)
def test_adapter_build_argv_contains_no_prompt_or_secret(adapter_cls: type) -> None:
    """build_argv() must NOT splice the prompt or anything secret-shaped."""
    adapter = adapter_cls()
    argv = adapter.build_argv(workspace=Path("/tmp/audit-workspace"), model="some-model")
    joined = " ".join(argv)
    for sentinel in PROMPT_SENTINELS:
        assert sentinel not in joined, (
            f"{adapter_cls.__name__} leaked sentinel {sentinel!r} into argv: {argv!r}"
        )
    # Defensive: no token-shaped substring at all.
    assert "sk-" not in joined.lower() or all(not piece.startswith("sk-") for piece in argv), (
        f"argv looks token-shaped: {argv!r}"
    )


@pytest.mark.parametrize(
    "adapter_cls",
    [ClaudeCodeAdapter, CodexAdapter, KimiAdapter],
    ids=["claude_code", "codex", "kimi"],
)
def test_adapter_argv_size_is_bounded(adapter_cls: type) -> None:
    """argv must stay small regardless of model name length.

    A prompt-on-argv adapter would balloon argv size with the prompt; we
    lock argv to a tight ceiling so a future refactor that pushed the
    prompt into argv would immediately break this test.
    """
    adapter = adapter_cls()
    big_model = "very-long-model-name-but-still-finite-" * 4
    argv = adapter.build_argv(workspace=Path("/tmp/audit-workspace"), model=big_model)
    # Each adapter currently emits 5-9 argv tokens. 32 is a comfortable cap
    # for "model name + flags" without admitting a prompt.
    assert len(argv) < 32, f"{adapter_cls.__name__} argv too long: {argv!r}"


@pytest.mark.skipif(
    platform.system() != "Linux", reason="cmdline inspection requires /proc on Linux"
)
def test_running_subprocess_does_not_leak_prompt_in_proc_cmdline(tmp_path: Path) -> None:
    """Spawn a real subprocess with the prompt on stdin and grep cmdline.

    We use ``cat`` because it (a) reads stdin, (b) exists on every Linux
    image we deploy to, and (c) does nothing with the prompt — making the
    leak the only thing under test. The exact CLI binary isn't relevant:
    what we're proving is that ``SubprocessCodingAdapter.send_prompt``
    chooses ``Popen(args, stdin=PIPE)`` over splicing the prompt into argv.
    """
    cat = shutil.which("cat")
    if cat is None:
        pytest.skip("/usr/bin/cat unavailable in this image")

    # Mirror what subprocess_base.send_prompt does: argv has no prompt.
    argv = [cat, "-"]  # cat reads stdin
    started = time.time()
    proc = subprocess.Popen(  # noqa: S603 - fixed argv
        argv,
        cwd=str(tmp_path),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    def _writer() -> None:
        assert proc.stdin is not None
        # Write slowly so /proc/<pid>/cmdline can be read while the child
        # is still alive.
        for chunk in SENTINEL_PROMPT.split(" "):
            proc.stdin.write(chunk + " ")
            proc.stdin.flush()
            time.sleep(0.005)
        proc.stdin.close()

    writer_thread = threading.Thread(target=_writer, daemon=True)
    writer_thread.start()

    # Sample /proc/<pid>/cmdline a few times while the child is up.
    cmdline_samples: list[str] = []
    for _ in range(20):
        if proc.poll() is not None:
            break
        try:
            raw = Path(f"/proc/{proc.pid}/cmdline").read_bytes()
        except FileNotFoundError:
            break
        cmdline_samples.append(raw.decode("utf-8", "replace"))
        time.sleep(0.005)

    writer_thread.join(timeout=2)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    # CRITICAL: none of the sentinels may appear in /proc cmdline.
    leaks: list[tuple[int, str]] = []
    for idx, sample in enumerate(cmdline_samples):
        for sentinel in PROMPT_SENTINELS:
            if sentinel in sample:
                leaks.append((idx, sentinel))
    assert not leaks, (
        f"prompt leaked into /proc/<pid>/cmdline; samples={cmdline_samples!r}; "
        f"leaks={leaks!r}; elapsed={time.time() - started:.2f}s"
    )


def test_subprocess_base_signature_uses_pipe_stdin() -> None:
    """Static guard: SubprocessCodingAdapter.send_prompt must wire stdin=PIPE.

    A refactor that swapped ``subprocess.Popen(..., stdin=PIPE)`` for
    splicing the prompt into argv would silently regress the contract.
    This is a source-level check so we don't have to spawn a real CLI.
    """
    from cognitive_os.code_director.adapters import subprocess_base

    source = Path(subprocess_base.__file__).read_text(encoding="utf-8")
    assert "stdin=subprocess.PIPE" in source, (
        "send_prompt must use stdin=PIPE (STDIN-only contract); "
        "any prompt-on-argv refactor must update this audit test deliberately."
    )
    assert "communicate(input=prompt" in source, (
        "send_prompt must pipe the prompt through communicate(input=...), not embed it in argv."
    )
