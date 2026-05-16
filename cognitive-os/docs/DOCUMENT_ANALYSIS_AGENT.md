# Document Analysis Agent

> **Estado actual (2026-05-15, 04:47 hora Chile):** subagente legal estable,
> ruta `legal` del grafo. Modos verificados en
> `backend/src/cognitive_os/deepagents/document_analysis/schemas.py::DocumentAnalysisMode`
> (`evidence_matrix`, `timeline`, `contradictions`, `full_report`,
> `legal_draft_support`, `case_summary`). Endpoints expuestos: 7 rutas
> bajo `/document-analysis/{task_id}/*` (incluyendo `download`, `report`).
> Worker Celery: `cognitive_os.run_document_analysis` en queue `agent_longrun`.
> Stack documental soportado vía PyPDF 6.10.2, PyMuPDF 1.27.2.3, ReportLab
> 4.5.0, python-docx 1.2.0, openpyxl 3.1.5, python-pptx 1.0.2.
> **No** participa en la fusión OpenHarness ni en el carril de mail
> personal; esas capacidades viven fuera de la ruta legal.

El Document Analysis Agent es un subagente legal de Cognitive OS para analizar documentos ya
ingestados con trazabilidad probatoria. Produce matriz hecho/evidencia/cita, timeline,
contradicciones, vacíos probatorios, reportes JSON/Markdown y DOCX opcional.

Este agente produce análisis y borradores de apoyo. No reemplaza revisión humana profesional ni presentación legal final.

## Qué Hace

- Trabaja solo con `doc_ids` autorizados.
- Mantiene citas con `doc_id`, `chunk_id` y páginas.
- Separa hechos, inferencias, incertidumbres y ausencia de evidencia.
- Marca borradores legales como sujetos a `HumanReview`.
- Ejecuta tareas largas por Celery en cola `agent_longrun`.

## Qué No Hace

- No inventa jurisprudencia ni hechos.
- No usa documentos fuera del scope.
- No cita sin página.
- No ejecuta shell, OpenShell, browser automation, email ni publicación.
- No modifica documentos originales.

## Modos

- `evidence_matrix`: matriz hecho/evidencia/cita.
- `timeline`: cronología con certeza de fecha.
- `contradictions`: contradicciones con dos citas.
- `full_report`: reporte completo.
- `legal_draft_support`: secciones de borrador, siempre con revisión humana.
- `case_summary`: resumen del caso con citas e incertidumbres.

## Uso API

Enviar `POST /document-analysis/run` con `DocumentAnalysisTask`. Ejemplo mínimo:

```json
{
  "task_id": "task-1",
  "thread_id": "thread-1",
  "user_id": null,
  "case_id": null,
  "doc_ids": ["DOC_ID_1"],
  "query": "Analiza los hechos principales y arma matriz con citas",
  "modes": ["evidence_matrix", "timeline"],
  "output_formats": ["json", "markdown"]
}
```

El endpoint devuelve `job_id`. Revisar progreso con `/jobs/{job_id}` y eventos con
`/jobs/{job_id}/events`.

## Reportes

- Metadata: `GET /document-analysis/{task_id}`
- Markdown: `GET /document-analysis/{task_id}/report`
- Descargas:
  - `/document-analysis/{task_id}/download/json`
  - `/document-analysis/{task_id}/download/markdown`
  - `/document-analysis/{task_id}/download/docx`

Las respuestas no exponen rutas absolutas del host.

## CLI

```bash
cd backend
uv run python ../scripts/test_document_analysis_agent.py \
  --doc-id DOC_ID_1 \
  --mode evidence_matrix \
  --mode timeline \
  --query "Analiza los hechos principales y arma matriz con citas"
```

## Quality Score

El evaluador determinístico calcula un puntaje 0-100. Penaliza citas incompletas, hechos sin
soporte, contradicciones sin dos fuentes, timeline inconsistente e incertidumbre no declarada. Si
el score baja de 85, el resultado queda `partial` y requiere revisión humana.

## Citas

Cada afirmación factual debe enlazar a `doc_id`, `chunk_id` si existe, `page_start` y `page_end`.
Las contradicciones deben citar ambos lados. La ausencia de evidencia se registra como vacío
probatorio, no como prueba concluyente.

## Aprobación De Drafts

`legal_draft_support` crea secciones de apoyo en `draft_sections` y marca
`human_review_required=true`. El uso externo de esos textos debe pasar por el flujo central de
aprobaciones.

## Depuración

- Revisar `JobEvents`.
- Revisar `storage/workspaces/{thread_id}/{task_id}/analysis/report.md`.
- Revisar `warnings`, `uncertainty_notes` y `quality_score`.
- Si DeepAgents falla, el servicio usa fallback determinístico mínimo con la advertencia
  `deepagent_failed_fallback_used`.

## Limitaciones

- El fallback no reemplaza revisión experta.
- Las consultas a Neo4j están limitadas a patrones predefinidos.
- DOCX es opcional y no bloquea JSON/Markdown.
- La calidad depende de la ingesta, OCR y chunking previos.
