"""Regresiones post-evaluación funcional 2026-05-25.

Cubre los hallazgos del comité evaluador independiente
(`FULL_FUNCTIONAL_EVALUATION.md` → `corregir_cognitive.md`) que originaron
parches en este commit:

- FUNC-EVAL-2026-001 — router LLM no debe clasificar preguntas
  informacionales como ``comm`` con ``proposed_action=send_email``.
- FUNC-EVAL-2026-003 — ``output_formats`` default cubre los 4 formatos
  (json, markdown, csv, docx).
- FUNC-EVAL-2026-005 — ``_execute`` envuelve los executors de Playwright
  sync (browser_preview/browser_interactive) con ``asyncio.to_thread``
  para evitar el crash ``sync_api inside asyncio loop``.
- FUNC-EVAL-2026-006 — el digest de mail redacta RUT chilenos y nombres
  ALL-CAPS estilo notificación judicial en ``summary_text``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from cognitive_os.deepagents.document_analysis.schemas import default_output_formats
from cognitive_os.mail.schemas import MailDigestMessage
from cognitive_os.mail.service import (
    PersonalMailService,
    _redact_digest_pii,
)

# ---------------------------------------------------------------------------
# FUNC-EVAL-2026-001 — router does not propose send_email for plain prompts.
# ---------------------------------------------------------------------------


def test_router_system_prompt_excludes_repeat_or_introspection_from_comm() -> None:
    """The hardened system prompt MUST explicitly exclude internal verbs.

    We don't invoke an LLM here (hermetic suite, no network). Instead we
    assert that the source contains the strengthened classification rules
    so a future refactor can't silently regress to the bare-bones
    instructions that mis-routed ``"¿qué eres?"`` to ``comm``.
    """

    graph_src = Path(__file__).resolve().parents[1] / "src" / "cognitive_os" / "agents" / "graph.py"
    source = graph_src.read_text(encoding="utf-8")
    assert "FUNC-EVAL-2026-001" in source, (
        "Hardened router prompt for FUNC-EVAL-2026-001 was removed from graph.py."
    )
    # Internal reformulation verbs MUST NOT be treated as comm.
    for verb in ("repíteme", "responde", "explica", "resume"):
        assert verb in source.lower(), f"Router prompt no longer mentions verb '{verb}'."
    # The rule about needing a recipient/external send for comm MUST stay.
    assert "EXTERNAL" in source, "Router prompt no longer asserts the EXTERNAL recipient rule."


# ---------------------------------------------------------------------------
# FUNC-EVAL-2026-003 — Document analysis emits the 4 formats by default.
# ---------------------------------------------------------------------------


def test_document_analysis_default_output_formats_covers_all_four() -> None:
    formats = default_output_formats()
    assert set(formats) == {"json", "markdown", "csv", "docx"}, (
        f"Default output_formats regressed to {formats!r}; FUNC-EVAL-2026-003 expects all 4."
    )


# ---------------------------------------------------------------------------
# FUNC-EVAL-2026-005 — _execute hands off Playwright executors to a thread.
# ---------------------------------------------------------------------------


def test_action_service_browser_executors_use_to_thread() -> None:
    """Static guard: ``ActionRequestService._execute`` must wrap
    ``BrowserPreviewService.execute`` and ``BrowserInteractiveService.execute``
    with ``asyncio.to_thread`` so they never run inside the FastAPI event
    loop. The sync Playwright API refuses to share an active event loop.
    """

    service_src = (
        Path(__file__).resolve().parents[1] / "src" / "cognitive_os" / "actions" / "service.py"
    )
    source = service_src.read_text(encoding="utf-8")

    # We must see both browser_preview and browser_interactive guarded.
    browser_preview_block = re.search(
        r'if action_type == "browser_preview":.*?return preview_result\.model_dump',
        source,
        re.DOTALL,
    )
    assert browser_preview_block is not None, "browser_preview branch missing in _execute."
    assert "asyncio.to_thread" in browser_preview_block.group(0), (
        "FUNC-EVAL-2026-005 regression: browser_preview executor is no longer "
        "wrapped with asyncio.to_thread."
    )

    browser_interactive_block = re.search(
        r'if action_type == "browser_interactive":.*?return interactive_result\.model_dump',
        source,
        re.DOTALL,
    )
    assert browser_interactive_block is not None, "browser_interactive branch missing in _execute."
    assert "asyncio.to_thread" in browser_interactive_block.group(0), (
        "FUNC-EVAL-2026-005 regression: browser_interactive executor is no "
        "longer wrapped with asyncio.to_thread."
    )


# ---------------------------------------------------------------------------
# FUNC-EVAL-2026-006 — mail digest redacts PII (RUT + court-style names).
# ---------------------------------------------------------------------------


def test_redact_digest_pii_masks_rut() -> None:
    snippet = "Causa rol 12345-2024. Su RUT 12.345.678-9 figura como demandante."
    redacted = _redact_digest_pii(snippet)
    assert "12.345.678-9" not in redacted
    assert "[REDACTED_RUT]" in redacted


def test_redact_digest_pii_masks_full_caps_names_three_words_or_more() -> None:
    snippet = "Sr. (a): DIEGO IGNACIO MANZUR NAOUM informa que la causa avanza."
    redacted = _redact_digest_pii(snippet)
    assert "DIEGO IGNACIO MANZUR NAOUM" not in redacted
    assert "[REDACTED_NAME]" in redacted


def test_redact_digest_pii_preserves_normal_text() -> None:
    snippet = "Notificación de audiencia el 2026-06-01 en sala 4."
    assert _redact_digest_pii(snippet) == snippet


def test_redact_digest_pii_does_not_over_match_acronyms() -> None:
    """Two consecutive ALL-CAPS tokens shouldn't trigger the name redactor."""

    snippet = "Resolución SII vs CMF emitida el lunes."
    # CMF/SII are 3-letter acronyms but only 2 consecutive — not 3+ words.
    assert _redact_digest_pii(snippet) == snippet


def test_render_digest_summary_redacts_pii_in_snippets() -> None:
    """End-to-end: PersonalMailService._render_digest_summary applies the
    redactor before persisting the summary_text artefact.
    """

    now = datetime.now(UTC)
    message = MailDigestMessage(
        id="msg-1",
        folder="INBOX",
        sender="no-responder@pjud.cl",
        subject="Causa informa estado",
        snippet="Sr. (a): DIEGO IGNACIO MANZUR NAOUM RUT 12.345.678-9 informa...",
        received_at=now,
        classification="normal",
        importance_score=0.2,
        proposed_reply_text=None,
        proposed_reply_rationale=None,
    )
    rendered = PersonalMailService._render_digest_summary(now, [message], [message], [])
    assert "DIEGO IGNACIO MANZUR NAOUM" not in rendered
    assert "12.345.678-9" not in rendered
    assert "[REDACTED_NAME]" in rendered
    assert "[REDACTED_RUT]" in rendered
