# 00 · Canonical Reading Summary — Cognitive OS (TestSprite Audit 2026-05-23)

Fecha: 2026-05-23
Branch: `codex/commercial-zero-friction-hardening`
Commit base: `9b22f77` (`docs: sync current commercial state`)
Auditor: Claude Opus 4.7 (run "REVISIÓN PROYECTO COGNITIVE OS CON TESTSPRITE")

## 1. Postura real de producto

Cognitive OS corre como **sistema personal mono-operador en PC dedicado**
(`OPERATOR_PROFILE=dedicated_local`, `LOCAL_AUTONOMY_MODE=full`,
`CODE_DIRECTOR_BUDGET_MODE=soft`). La prioridad es **cero fricción operativa
por sobre seguridad estricta**. Esto **no** es un producto SaaS multi-tenant; el
endurecimiento "estricto" sigue cableado en `strict` como referencia técnica,
pero no es el objetivo de este host.

Fuentes que mandan (orden de precedencia):

1. `docs/CURRENT_STATE.md` (estado vigente, 2026-05-22, commit `5953b40`).
2. `docs/ZERO_FRICTION_OPERATING_MODEL.md` (modelo operativo).
3. `docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md` (auditoría más reciente,
   AUDIT-2026-A..K cerrados).
4. `docs/USER_GUIDE.md`, `docs/PROJECT_GUIDE.md`, `docs/ARCHITECTURE.md`.
5. `docs/ACTION_PLANE.md`, `docs/RUNBOOK.md`, `docs/AGENT_LEARNING_PLAN.md`.
6. `docs/qa/MAP.md`, `docs/qa/FINAL_AUDIT_REPORT.md`,
   `docs/qa/commercial_zero_friction_hardening/*`.

## 2. Contratos funcionales (lo que el sistema sí hace)

- **Frontend:** Next.js 16.2.6 + React 19, **20 tabs** en una SPA (`app/page.tsx`),
  dark-only glass cockpit PWA, sin Tailwind/shadcn/MUI. Tokens en
  `app/globals.css`, `<Icon />` para iconos estructurales, `asArray<T>` en
  vistas con colecciones, `usePolledFetch` con pause offline/hidden, command
  palette `Ctrl/Cmd+K` (capture phase).
- **Backend:** FastAPI 0.115+, **147 endpoints REST** en `api/app.py`, JWT
  bearer, CORS abierto a `:3000`/`:3001`/`:3101` por default.
- **Async:** Celery 5 colas (`default`, `ingestion`, `agent_longrun`,
  `maintenance`, `mail`); **23 tareas**; hasta **13 jobs beat**; reapers de
  approvals/jobs/action-requests; componente health `operational_backlog`.
- **Persistencia:** Postgres 16+pgvector + Redis 7 + Weaviate 1.29.0 + Neo4j 5,
  ligados a `127.0.0.1`. **20 migraciones Alembic** head `202605200003`.
  Test DB aislada `cognitive_os_test`.
- **Telegram:** **37 slash commands**; modo conversacional sin slash en
  `dedicated_local`; dispatch **fail-closed** (allowlist vacía rechaza
  arranque). AUDIT-2026-A.
- **Health:** `/health/dashboard` con **18 componentes** (17 checks +
  `checkpointer`); distinción `ok`/`configured`/`degraded`/`disabled`;
  `POST /health/verify` para probe LLM/embeddings/IMAP real. AUDIT-2026-B.
- **MCP:** `/system/mcp` carga inventario en paralelo, timeout default 30s
  (`MCP_INVENTORY_TIMEOUT_SECONDS`); runtime verificado 5/5 servers, 67 tools.
- **Action Plane:** Validate → Preview → Request → Approve → Dispatch →
  Execute → Audit. `ActionRequest` idempotente con dispatch state
  (`submitting/submitted/failed`). En `dedicated_local/full` algunas approvals
  se auto-resuelven; en `strict` queda preview-first.
- **LLM:** primary+agent `gpt-5.5` (Responses API + 24h cache), secondary
  `gemini-3.1-pro-low`, vision `glm-4.6v`.
- **Learning:** Fases A-E en producción (recetas, post-mortem, scorecard,
  skill promotion, nightly reflection). Único auto-deploy: warnings de Fase D
  con kill switch `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` (default `true`).

## 3. Contratos de cero fricción

En `dedicated_local/full`:

- Edge real / Kimi WebBridge **permitidos**.
- Filesystem local **amplio**: lee/escribe en `/home/jgonz` sin aprobación
  por archivo (`COMPUTER_ALLOWED_ROOTS` configurable).
- Auto-resolución de approvals para acciones internas previamente validadas.
- Telegram conversacional sin `/`.
- Frontend command palette `Ctrl/Cmd+K` desde cualquier foco.
- `/system/readiness` lista capacidades bloqueadas y cómo desbloquearlas.

## 4. Controles que sí se mantienen (no negociables)

- `AuditEvent`, `JobEvent`, `ActionRequest` con timeline trazable.
- Idempotencia en dispatch (`dispatch_state`) y request (idempotency key +
  índice parcial UNIQUE).
- Reapers visibles vía `operational_backlog`.
- Health/readiness honesto: `ok` solo si verificado; `configured` si solo
  cableado.
- MCP diagnosticable: `/system/mcp` reporta `connected/tools_count/error`.
- Tests herméticos contra DB de test; producción nunca se toca.
- Auth fail-closed donde la falla es silenciosa (Telegram).
- `.env`/tokens fuera de git; `.next-qa` aislado del frontend vivo.

## 5. Mail como excepción dura

El contrato vigente — y este audit lo respeta absolutamente:

1. Digest 10:00 y 20:00 Chile.
2. Fuentes: Gmail `TODOS`+`SPAM` (`diegomanzurn@gmail.com`), GoDaddy `Spam`
   (`diego@doctormanzur.com`).
3. Clasificación spam **por el agente**, no la carpeta.
4. Máximo 50 correos en el resumen.
5. Respuestas como **texto separado**, no draft.
6. **No crea drafts** en Gmail/GoDaddy.
7. **No envía SMTP** en flujo normal.
8. `/mail/sync/dispatch` y `/mail/digest/preview` son read-only (`sync_first=false`).
9. Escape hatch `/mail/messages/{id}/approve-send` exige simultáneamente:
   `ENABLE_EMAIL_SEND=true` + `MAIL_ALLOW_EXPLICIT_SEND=true` +
   `explicit_send_confirmation="SEND_THIS_EMAIL_EXPLICITLY"`.

Razón: enviar mail es comunicación humana externa, no acción técnica.
Cualquier sugerencia de fix que afloje este contrato se rechaza.

## 6. Superficies críticas a auditar

| Superficie | Archivos clave | Riesgo si falla |
|---|---|---|
| Frontend SPA | `frontend/app/views/*.tsx`, `app/page.tsx`, `globals.css` | Cockpit muerto, hydration mismatch, console.error |
| API REST | `backend/src/cognitive_os/api/app.py` (147 endpoints) | 500 en flujo normal, contrato roto |
| Action Plane | `backend/src/cognitive_os/actions/*` | Acción duplicada, draft inesperado, DNS real |
| Mail | `backend/src/cognitive_os/mail/*`, `actions/gmail_digest.py` | Envío automático prohibido |
| Telegram | `backend/src/cognitive_os/telegram_bot.py` | Allowlist vacía, fail-open, comando crashea |
| Celery | `backend/src/cognitive_os/workers/tasks.py` (23 tareas) | Job perdido, dispatch duplicado, beat stuck |
| Health | `backend/src/cognitive_os/core/health.py` | `ok` falso, operador adivina |
| MCP | `backend/src/cognitive_os/mcp/*`, `/system/mcp` | Carga secuencial, falsos timeouts |
| Code Director | `backend/src/cognitive_os/code_director/*` | Adapter crashea, prompt en `ps`, budget ignorado |
| Document Analysis | `backend/src/cognitive_os/document_analysis/*` | Quotes sin citation, no progress |
| Research/DeepAgents | `backend/src/cognitive_os/research/*`, `deepagents/*` | Plan→sintesis sin scoring, SSE muerto |
| Learning | `deepagents/skill_promoter.py`, `failure_postmortem.py` | Auto-deploy sin kill switch |
| Health backlog | `core/health.py::_check_operational_backlog` | Reaper invisible |
| Scripts/launchers | `scripts/*.sh`, `~/Escritorio/cognitive-os.sh` | Doble arranque, PID recycle |
| Migrations | `backend/alembic/versions/*` | Drift, constraint que rechaza payload válido |

## 7. Documentos que mandan / contradicciones detectadas

Tras leer todos los markdowns canónicos no se observan contradicciones
materiales pendientes entre los documentos vigentes. Las contradicciones
históricas (audit 2026-05-20 strict-mode vs audit 2026-05-22 zero-friction)
quedaron resueltas: el `CODEX_COMMERCIAL_READINESS_AUDIT.md` declara
explícitamente que la postura SaaS de la primera versión fue **incorrecta** y
queda anulada. Hardening posteriores (`5953b40`) son ajustes runtime
documentados.

Riesgo de drift a vigilar (no es contradicción, es lo más cercano):

- `docs/qa/MAP.md` afirma 17 componentes en `/health/dashboard` en un
  párrafo histórico, mientras los docs vigentes dicen 18. Es texto de la
  fase 76 con disclaimer "histórico"; el snapshot vivo manda.
- `docs/qa/FINAL_AUDIT_REPORT.md` también conserva la versión histórica 16
  Playwright; el header vigente declara 31. Ya está advertido.

## 8. Decisiones que tomaré en esta auditoría

1. **Respetar la postura zero-friction.** Cualquier hallazgo del tipo
   "deberías pedir más confirmaciones" se rechaza salvo que evite pérdida de
   datos o duplicidad real.
2. **Respetar mail como excepción dura.** Cualquier hallazgo que afloje
   read-only/no-draft/no-send se rechaza.
3. **No tocar `supermemory` MCP.** Memoria del operador es protegida.
4. **Usar TestSprite MCP como motor principal** según fases 7/13; Playwright
   y pytest como gates fuertes complementarios.
5. **No correr live tests si fuerzan writes externos.** El carril
   `tests/live/` se ejecuta sólo opt-in y solo `live_readonly`.
6. **Severidad sobre el contrato vigente, no sobre uno SaaS.** Falsos
   positivos del tipo "auto-approve en `dedicated_local/full` es inseguro" se
   marcan como decisión documentada, no como bug.
7. **No regenerar baseline si no hay cambios.** El último gate verde es del
   commit `5953b40`/`9b22f77`. Si el código no cambió desde entonces,
   re-ejecutar gates es valioso para confirmar reproducibilidad, no para
   declarar nuevo veredicto.
8. **Mantener trazabilidad de cada fix con test de regresión.**

## 9. Lista NO RESTRINGIR (debe permanecer amplio)

Capacidades que el sistema **debe mantener amplias** en `dedicated_local/full`:

- Filesystem local en `/home/jgonz` para el agente.
- Edge real / Kimi WebBridge con perfil real del operador.
- Auto-resolución de approvals internas pre-validadas.
- Navegación/lectura/organización sin confirmar cada paso.
- Telegram conversacional sin `/`.
- UI como command center: command palette, atajos de teclado.
- Code Director con CLIs reales (Claude Code/Codex/Kimi/DeepAgents) bajo
  budget soft, sin pedir aprobación por subproceso.

## 10. Próximos pasos inmediatos

- **Fase 1:** mapear los 147 endpoints, 23 tareas Celery, 20 vistas frontend,
  37 commands Telegram contra archivos reales.
- **Fase 2:** confirmar TestSprite MCP operativo (ya en `testsprite_tests/`
  hay tmp con bootstrap logs recientes 2026-05-23).
- **Fase 3-4:** validar `.env` real, arrancar stack si no está vivo,
  capturar boot log.
- **Fase 5:** correr `full-qa.sh` + `playwright test` + `stress-qa.sh 3` +
  `full-qa-live.sh` (si `LIVE_TESTS_ENABLED=1` ya estaba seteado).

Documentado en `01_DISCOVERY_MAP.md` y siguientes.
