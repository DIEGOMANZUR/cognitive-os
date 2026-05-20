"""Prompts and parsing helpers for the Fase 78 recipe extractor.

The extractor feeds a trajectory of ``JobEvent`` rows from a successful
job into the secondary chat model and asks for a reusable procedure in
strict JSON. This module keeps the wire shape isolated so the extractor
can stay readable and the tests can pin specific failure modes (skip
signal, malformed JSON, missing required keys) without booting an LLM.
"""

from __future__ import annotations

import json
from typing import Any

# Fields the extractor refuses to materialise a recipe without. Keeping the
# list short avoids false negatives on terse trajectories while still
# rejecting "the model returned an empty object" cases.
_REQUIRED_RECIPE_KEYS: tuple[str, ...] = ("title", "summary", "steps")
_MAX_TITLE_LEN = 200
_MAX_SUMMARY_LEN = 1200


RECIPE_EXTRACT_SYSTEM = """\
Eres un extractor procedimental para Cognitive OS.
Recibes la trayectoria de tool calls de un agente que completó una tarea
correctamente y debes producir una receta reutilizable en JSON estricto.

Reglas:
- Generaliza los pasos: no copies inputs literales del usuario.
- Si la trayectoria es trivial o demasiado específica para reutilizarse,
  responde {"skip": true, "reason": "<motivo breve>"} y nada más.
- No inventes herramientas que no aparezcan en la trayectoria.
- Mantén las descripciones en español, breves y accionables.

Output JSON exacto (sin texto adicional, sin markdown fences):
{
  "title": "Verbo + objeto (≤ 12 palabras)",
  "summary": "1-2 frases describiendo el objetivo de la receta.",
  "preconditions": ["..."],
  "inputs_typical": {"param": "tipo"},
  "steps": [
    {"step": 1, "tool": "<tool_name>", "purpose": "...", "input_pattern": "..."}
  ],
  "outputs_typical": "Descripción del resultado.",
  "estimated_runtime_seconds": 90,
  "success_indicators": ["..."],
  "tags": ["..."]
}
"""

# Curated by hand so the LLM has a concrete shape to imitate. Keep both
# examples in Spanish to bias the output language.
RECIPE_EXTRACT_FEWSHOTS: tuple[dict[str, str], ...] = (
    {
        "role": "user",
        "content": (
            "Trayectoria:\n"
            "[1] tool=search_local_docs input={'q':'contratos 2026'} ok\n"
            "[2] tool=read_document_pages input={'doc_id':'abc','pages':[1,2]} ok\n"
            "[3] tool=write_workspace_file input={'name':'resumen.md'} ok\n"
            "[4] tool=graph_query_readonly input={'cypher':'MATCH (c:Cliente)'} ok\n"
            "[5] tool=write_workspace_file input={'name':'final.md'} ok\n"
            "agent=research duration=120s status=completed"
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "title": "Resumir contratos del año por cliente",
                "summary": (
                    "Reúne contratos del año en la base local, los lee, los "
                    "cruza con la entidad cliente del grafo y emite un resumen."
                ),
                "preconditions": [
                    "Documentos del año indexados en Weaviate",
                    "Grafo Neo4j con nodos :Cliente cargados",
                ],
                "inputs_typical": {"year": "int"},
                "steps": [
                    {
                        "step": 1,
                        "tool": "search_local_docs",
                        "purpose": "Encontrar contratos relevantes del año",
                        "input_pattern": "{'q': 'contratos <year>'}",
                    },
                    {
                        "step": 2,
                        "tool": "read_document_pages",
                        "purpose": "Leer páginas clave de cada contrato",
                        "input_pattern": "{'doc_id': '<id>', 'pages': [...]}",
                    },
                    {
                        "step": 3,
                        "tool": "graph_query_readonly",
                        "purpose": "Cruzar con la entidad cliente del grafo",
                        "input_pattern": "{'cypher': 'MATCH (c:Cliente) ...'}",
                    },
                    {
                        "step": 4,
                        "tool": "write_workspace_file",
                        "purpose": "Guardar el resumen final en el workspace",
                        "input_pattern": "{'name': 'final.md'}",
                    },
                ],
                "outputs_typical": "Un archivo markdown con los contratos resumidos por cliente.",
                "estimated_runtime_seconds": 120,
                "success_indicators": [
                    "Existe final.md en el workspace",
                    "Cada cliente listado tiene al menos un contrato citado",
                ],
                "tags": ["contratos", "resumen", "graph"],
            },
            ensure_ascii=False,
        ),
    },
)


class RecipeParseError(ValueError):
    """Raised when the LLM output cannot be coerced into a recipe payload."""


def parse_recipe_response(raw: str | bytes | dict[str, Any] | None) -> dict[str, Any]:
    """Coerce the LLM output into either a recipe or a structured skip signal.

    Returns a dict with one of two shapes::

        {"skip": True, "reason": "..."}
        {"title": "...", "summary": "...", "steps": [...], ...}

    Raises :class:`RecipeParseError` if the input is empty, not JSON, or
    a recipe missing required keys. The extractor treats the parse error
    as a soft failure (logs + does NOT mark the job processed) so a later
    beat cycle can retry.
    """
    if raw is None:
        msg = "Empty LLM response."
        raise RecipeParseError(msg)
    if isinstance(raw, dict):
        payload = raw
    else:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        text = text.strip()
        if not text:
            msg = "Empty LLM response."
            raise RecipeParseError(msg)
        # Tolerate stray ```json fences from non-strict models.
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            msg = f"LLM output is not valid JSON: {exc.msg}"
            raise RecipeParseError(msg) from exc
    if not isinstance(payload, dict):
        msg = "LLM output must be a JSON object."
        raise RecipeParseError(msg)
    if payload.get("skip") is True:
        return {"skip": True, "reason": str(payload.get("reason") or "no reason given")}
    missing = [key for key in _REQUIRED_RECIPE_KEYS if not payload.get(key)]
    if missing:
        msg = f"Recipe missing required keys: {missing}"
        raise RecipeParseError(msg)
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        msg = "Recipe must include a non-empty `steps` list."
        raise RecipeParseError(msg)
    # Defensive truncation so a runaway LLM cannot blow up the proposal row.
    payload["title"] = str(payload["title"])[:_MAX_TITLE_LEN]
    payload["summary"] = str(payload["summary"])[:_MAX_SUMMARY_LEN]
    return payload


def build_recipe_messages(trajectory_text: str) -> list[dict[str, str]]:
    """Assemble the message list for the secondary LLM (system + few-shots + user)."""
    return [
        {"role": "system", "content": RECIPE_EXTRACT_SYSTEM},
        *RECIPE_EXTRACT_FEWSHOTS,
        {"role": "user", "content": trajectory_text},
    ]


def serialize_trajectory(
    *,
    job_type: str,
    agent_name: str | None,
    duration_seconds: float,
    events: list[dict[str, Any]],
) -> str:
    """Render the trajectory into a compact text format for the user message.

    Why a custom format: passing raw JSON inflates token usage 3-4x without
    helping the model, and the secondary tier (gemini-3.1-pro-low) follows
    structured-but-terse inputs much more reliably than nested JSON. We
    keep the same shape as the few-shot examples so the model has zero
    ambiguity about what the trajectory looks like.
    """
    lines: list[str] = []
    for idx, event in enumerate(events, start=1):
        event_type = str(event.get("event_type") or "?")
        message = str(event.get("message") or "").strip()
        meta = event.get("metadata") or event.get("metadata_json") or {}
        tool = str(meta.get("tool") or meta.get("tool_name") or "")
        bits = [f"[{idx}] event={event_type}"]
        if tool:
            bits.append(f"tool={tool}")
        if message:
            bits.append(f"msg={message[:160]}")
        lines.append(" ".join(bits))
    header = (
        f"Trayectoria del job:\n"
        f"agent={agent_name or 'unknown'} job_type={job_type} "
        f"duration={int(duration_seconds)}s status=completed\n"
    )
    return header + "\n".join(lines)
