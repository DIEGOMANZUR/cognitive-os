# 17 - Final Context Reconstruction

Fecha local: 2026-05-24T20:29:28-04:00

## Fuentes leidas

Documentos canonicos presentes y revisados por headings/contratos:

- `docs/CURRENT_STATE.md`
- `docs/ZERO_FRICTION_OPERATING_MODEL.md`
- `README.md`
- `docs/USER_GUIDE.md`
- `docs/PROJECT_GUIDE.md`
- `docs/ARCHITECTURE.md`
- `docs/COGNITIVE_OS_GUIDE.md`
- `docs/ACTION_PLANE.md`
- `docs/RUNBOOK.md`
- `docs/AGENT_LEARNING_PLAN.md`
- `docs/FRONTEND_ARCHITECTURE.md`
- `docs/DOCUMENT_ANALYSIS_AGENT.md`
- `docs/DEEPAGENTS_INTEGRATION.md`
- `docs/DEEPAGENTS_SKILLS_MEMORY.md`
- `docs/OPERATOR_VARIABLE_CHECKLIST.md`
- `docs/SETTINGS_REGISTRY_TABLE.md`
- `docs/OPENHARNESS_FUSION.md`

Reportes TestSprite previos revisados:

- `00_CANONICAL_READING_SUMMARY.md` a `16_FINAL_REAUDIT_REPORT.md`.
- Reportes recientes `17_TESTSPRITE_ZERO_DEFECTS_CONTEXT.md` a
  `24_TESTSPRITE_ZERO_DEFECTS_CERTIFICATION.md`.
- Certificacion historica `34_COMMERCIAL_QUALITY_CERTIFICATION.md`.

No faltan los documentos requeridos por el prompt.

## Estado canonico reconstruido

El estado declarado por la documentacion vigente es **RELEASE APPROVED** para
instalacion local-first en PC dedicado, con `dedicated_local/full` como perfil
principal. La seguridad estricta existe como perfil conservador, pero no es el
objetivo comercial de este host.

Perfil objetivo:

- `OPERATOR_PROFILE=dedicated_local`
- `LOCAL_AUTONOMY_MODE=full`
- `CODE_DIRECTOR_BUDGET_MODE=soft`

Contratos duros:

- Health honesto: `configured` no equivale a `verified ok`.
- Readiness accionable: debe explicar flags faltantes.
- Trazabilidad: `ActionRequest`, `JobEvent`, `AuditEvent`.
- Idempotencia y no dispatch duplicado peligroso.
- No secretos en respuestas/reportes/logs.
- No mail send/draft en flujo normal.
- No DNS real write por defecto.
- No falsos verdes ni fallos silenciosos.

## Estado declarado por auditorias previas

Los cierres anteriores declaran:

- 20 migraciones Alembic, head `202605200003`.
- Backend FastAPI con endpoints REST amplios y Action Plane.
- Celery con 23 tareas y 5 colas (`default`, `ingestion`,
  `agent_longrun`, `maintenance`, `mail`).
- Frontend Next.js con 20 vistas SPA.
- Telegram con 37 slash commands y modo conversacional en `dedicated_local`.
- `/health/dashboard` con 18 componentes y `POST /health/verify`.
- MCP runtime historico 5/5 servers y 67 tools.
- Mail como excepcion dura: lectura, digest, propuestas como texto; sin drafts
  ni envio normal.

## Hallazgos anteriores y fixes relevantes

- `AUDIT-2026-A..H`: cerrados historicamente.
- `TS-ZF-20260523-001`: Playwright auto-mint JWT para cero friccion.
- `TS-ZF-20260523-006`: `eager_defaults=True` para evitar `MissingGreenlet`
  en endpoints de preview/request.
- Prompt TestSprite reciente:
  - `TS-001`: bootstrap publico UI/API y Health live corregido.
  - `TS-004`: estado MCP visible incluso con degradacion corregido.

## Riesgos residuales declarados

- TestSprite puede generar falsos positivos o POSTs inseguros si el caso no se
  expresa como GET-only.
- Las URLs publicas dependen del tunnel/Cloudflare.
- Live read-only toca proveedores reales y se ejecuta solo si el gate lo
  habilita explicitamente.
- El runtime vivo puede quedar detras del filesystem si no se reinicia tras
  cambios.

## Superficies criticas a revalidar

- Frontend completo: tabs, command palette, health, jobs, approvals, mail,
  docs, document-analysis, research, code-director, MCP/system.
- Backend: auth, system, health, jobs, approvals, actions, mail, docs,
  research, code-director, deepagents, audit, invalid payloads.
- Workers/beat/reapers.
- Telegram commands y fail-closed.
- TestSprite final release audit.
- Gates oficiales: `full-qa.sh`, `stress-qa.sh`, Playwright, launchers,
  `git diff --check`, Alembic, sync doc counts.

## Contradicciones o gaps de evidencia

- Hay reportes historicos con conteos distintos por evolucion del repo. La
  fuente vigente es el codigo actual y `scripts/sync_doc_counts.py --check`.
- Existen cambios sin commit de los prompts TestSprite recientes; por eso este
  cierre debe validar el filesystem actual, no solo el commit `5459ec5`.
- TestSprite frontend multi-ID fallo con 500 remoto en el prompt anterior; se
  mitigo ejecutando singles y reruns focales.

## Qué NO endurecer

- No convertir `dedicated_local/full` en `strict`.
- No reintroducir aprobaciones redundantes para acciones locales/reversibles
  permitidas por el perfil.
- No bloquear lectura, diagnostico, preview ni preparacion local por posture
  SaaS.
- No debilitar mail read-only ni DNS dry-run.
