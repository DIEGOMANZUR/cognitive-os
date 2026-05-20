from __future__ import annotations

from cognitive_os.deepagents.factory import create_controlled_deep_agent
from cognitive_os.deepagents.research_deepagent import (
    _skills_and_memory,
    coerce_deepagent_result,
    create_workspace,
)
from cognitive_os.deepagents.schemas import DeepAgentResult, DeepAgentTask, DeepAgentToolPolicy
from cognitive_os.integrations.mcp_client import (
    load_mcp_tools_for_role_sync as _load_mcp_tools_for,
)

SYSTEM_PROMPT_DOCUMENT = """
Eres un subagente de analisis documental largo dentro de Cognitive OS.

Objetivo:
Crear matrices hecho/evidencia/cita, detectar contradicciones, proponer lineas de tiempo
y redactar resumen ejecutivo usando solo documentos ya ingestados.

Reglas:
1. No uses web por defecto.
2. Cita siempre paginas y doc_id.
3. No ejecutes shell.
4. No modifiques archivos del proyecto.
5. Puedes escribir artefactos Markdown solo en el workspace temporal.
"""


def run_document_analysis_deepagent(task: DeepAgentTask) -> DeepAgentResult:
    workspace = create_workspace(task)
    # Fase 72 H: Kimi WebBridge opt-in. Por seguridad mantenemos
    # allow_browser=False para mitigar prompt injection desde documentos
    # hostiles; pero el operador puede solicitar el bridge ad-hoc en
    # dedicated_local con request_kimi_webbridge=True. El bridge sigue
    # gated por KIMI_WEBBRIDGE_ALLOWED_DOMAINS + approval por mutation.
    from cognitive_os.core.config import settings as _settings  # noqa: PLC0415

    allow_bridge = (
        task.request_kimi_webbridge
        and _settings.enable_kimi_webbridge
        and _settings.operator_profile == "dedicated_local"
    )
    policy = DeepAgentToolPolicy(
        allow_local_rag=True,
        allow_neo4j_read=True,
        allow_web=False,
        allow_workspace_write=True,
        allow_shell=False,
        allow_browser=False,
        allow_email=False,
        allow_social_posting=False,
        allow_delete=False,
        allow_kimi_webbridge=allow_bridge,
    )
    skills_paths, startup_memory = _skills_and_memory(task, "document_analysis")
    mcp_tools = _load_mcp_tools_for("document_analysis")
    agent = create_controlled_deep_agent(
        task,
        policy,
        workspace,
        system_prompt=SYSTEM_PROMPT_DOCUMENT,
        skills_paths=skills_paths,
        startup_memory=startup_memory,
        mcp_tools=mcp_tools,
    )
    raw_output = agent.invoke(
        {
            "messages": [
                (
                    "human",
                    f"Analiza documentos para: {task.query}. "
                    "Si corresponde, crea matriz Markdown en workspace.",
                )
            ]
        }
    )
    result = coerce_deepagent_result(raw_output, task)
    if not result.generated_files:
        matrix = workspace.root_dir / "document_matrix.md"
        matrix.write_text(
            f"# Matriz hecho/evidencia/cita\n\nConsulta: {task.query}\n",
            encoding="utf-8",
        )
        result.generated_files.append("document_matrix.md")
    (workspace.root_dir / "result.json").write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return result
