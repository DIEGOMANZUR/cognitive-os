# Document Analysis Agent (referencia técnica)

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7):** esta rama `codex/commercial-zero-friction-hardening` en base `8a33475d0502` queda sincronizada para el cierre comercial local-first. La evidencia viva se concentra en `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/tmp/v2_07_absolute_release_closure_20260527_050231`. Estado de producto verificado durante Prompt 7: backend FastAPI local, frontend Next.js, Docker services, Postgres, Redis, Weaviate, Neo4j, Alembic head, worker, beat, health/readiness, LangGraph/chat, DeepAgents, MCP, RAG/documentos, Document Analysis, Action Plane sandbox, mail read-only, Telegram, Google read-only, GoDaddy dry-run, Kimi WebBridge y Code Director toy/guard rails.
>
> **Gates V2.0 ejecutados antes de los dos ciclos verdes finales:** `bash scripts/full-qa.sh` **1221 passed, 1 skipped, 28 deselected**; `bash scripts/stress-qa.sh 5` **5/5 verde x 1221 passed**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/sync_doc_counts.py --check` OK; `bash scripts/verify_desktop_launchers.sh` OK; OpenAPI read-only smoke **70 GET / 0 failures**; security read-only scan sin secretos críticos; CDP/Playwright forense **10 ciclos x 20 vistas** sin console/page errors ni 5xx, con un aborto `POST /auth/local-token` adjudicado como cierre de contexto del harness y no defecto de producto; Lighthouse local: accessibility 96, best-practices 100, SEO 100.
>
> **Criterio de verdad:** no se declara envio de correo, draft real ni escritura DNS. Mail queda normalizado como read-only: sync/list/classify/digest/proposed replies como texto, sin drafts ni sends. GoDaddy queda preview/dry-run; Action Plane mantiene sandbox/approval/audit/idempotencia segun riesgo. El tunnel publico `cognitive.doctormanzur.com` se valida con `scripts/testsprite_web/deploy_and_verify.sh` cuando Diego vaya a correr TestSprite web; Prompt 7 no lo expone permanentemente porque su propia regla prohibe exponer servicios a internet.

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Estado actual (2026-05-26, HEAD `8a33475`):** subagente legal estable dentro del
> modelo **COMERCIAL LOCAL-FIRST APROBADO + frontend/TestSprite web hardening**.
> La prioridad general del producto es baja fricción en el PC dedicado, pero esta
> ruta sigue siendo evidence-first: citas, scope de `doc_ids`, quality score y
> revisión humana cuando el modo produce apoyo legal. La capa pública/TestSprite
> no cambia este contrato: no usa mail ni envía comunicaciones.
>
> **Histórico (2026-05-20, Fase 74):** subagente legal estable, ruta `legal`
> del grafo. Modos verificados en
> `backend/src/cognitive_os/deepagents/document_analysis/schemas.py::DocumentAnalysisMode`
> (`evidence_matrix`, `timeline`, `contradictions`, `full_report`,
> `legal_draft_support`, `case_summary`). Endpoints: 7 rutas bajo
> `/document-analysis/{task_id}/*`. Worker Celery:
> `cognitive_os.run_document_analysis` en queue `agent_longrun`. Stack
> documental: PyPDF 6.10.2, PyMuPDF 1.27.2.3, ReportLab 4.5.0,
> python-docx 1.2.0, openpyxl 3.1.5, python-pptx 1.0.2.
>
> **Fase 72:** el subagente puede pedir Kimi WebBridge ad-hoc para
> validación cruzada de un dato del documento — campo
> `request_kimi_webbridge` en el `DocumentAnalysisTask`. Off por default
> (mantiene `allow_browser=False` para mitigar prompt-injection desde
> documentos hostiles); sólo se enciende cuando
> `dedicated_local + enable_kimi_webbridge + request_kimi_webbridge=true`.
> No participa en la fusión OpenHarness ni en el carril de mail personal.

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
