# Document Analysis Agent (referencia técnica)

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7).** Esta rama `codex/commercial-zero-friction-hardening` queda certificada como **APTA COMERCIAL LOCAL-FIRST** para PC dedicado. Branch inicial Prompt 1: HEAD `2bb4966`. Working tree del Prompt 7 consolida los cambios de Prompts 3 (F-P2-001..006), 4 (F-P4-001 fix wrapper timeout mcp_client live probe) y 6 (V2-EVAL-001 DocAnalysis API consistency). El commit final del Prompt 7 firma todo el delta V2.0 sin push. Evidencia viva en `tmp/v2_07_absolute_release_closure_20260527_175541/`.
>
> **Hallazgos cerrados V2.0 (12):** F-P2-001 wildcard_allow_all transparency · F-P2-002 stress flake eliminado (0% en 5×1232) · F-P2-003 `?limit=` honored en `/approvals` y `/actions/drive/files` · F-P2-004 `/chat` 404/400 con `missing_doc_ids`/`invalid_doc_ids` · F-P2-005 docs sync (este bloque) · F-P2-006 `_check_mcp(verify_live=True)` → overall `ok` · F-P4-001 timeout wrapper +5s sobre `mcp_inventory_timeout_seconds` · F-P4-002 fallback heurístico DocAnalysis documentado · F-P4-003 Kimi extension boot oscillation documentado · V2-EVAL-001 `GET /document-analysis/{id}` mirror artefacto · V2-EVAL-004 endpoints memoria/aprendizaje live (303 proposals, 209 recipes, 94 warnings) · V2-EVAL-005 Code Director adapter=deepagent plan+approval+reject sin exec.
>
> **Gates V2.0 medidos antes del cierre absoluto:** `bash scripts/full-qa.sh` **1232 passed, 1 skipped, 28 deselected** (ruff/format/mypy/alembic/sync_doc_counts/git-diff verdes); `bash scripts/stress-qa.sh 5` **5/5 verde × 1232 passed**, flakiness **0%**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/openapi_readonly_smoke.py` **70 GET / 0 failures**; `bash scripts/verify_desktop_launchers.sh` OK; security-readonly-qa (bandit/semgrep/secret-scan) clean; `POST /health/verify` overall **`ok`** con `mcp_client` live `ok` 6/6 y 69 tools; checklist 400 puntos ejecutada.
>
> **Criterio de verdad:** no se declara envío de correo, draft real ni escritura DNS. Mail queda normalizado como read-only (sync/list/classify/digest + proposed replies como texto). GoDaddy preview/dry-run. Action Plane mantiene `validate→preview→request→approve→dispatch→execute→audit` con idempotencia y reapers. El runtime corre en `127.0.0.1` sin exposición LAN/internet. El frontend `cognitive.doctormanzur.com` se levanta on-demand sólo con `scripts/testsprite_web/deploy_and_verify.sh`; Prompt 7 V2.0 no lo expone permanentemente. **Cognitive OS queda certificado en este commit como APTO COMERCIAL LOCAL-FIRST para PC dedicado, con funcionamiento real activado, documentación sincronizada, dos ciclos completos verdes posteriores al último cambio, Git ordenado y sin P0/P1/P2 abiertos.**

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
