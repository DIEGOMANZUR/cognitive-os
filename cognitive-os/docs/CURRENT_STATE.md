# Estado Actual Canonico — Cognitive OS

Fecha de sincronizacion documental: **2026-05-22**
Branch: `codex/fase-34-baseline-hardening`

Este archivo es la **fuente corta de verdad** del estado operativo actual. Si
otro Markdown discrepa, este archivo manda y el otro debe corregirse. Los
conteos estructurales del "Snapshot Tecnico" se generan con
`scripts/sync_doc_counts.py` y `full-qa.sh` falla si quedan desincronizados.

## Cambios Mas Recientes

**Remediacion del audit comercial (2026-05-22, aplicada en el working tree).**
Tras `docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md` se cerraron las 8 fallas
accionables (AUDIT-2026-A..H):

- **A (P0)** — `telegram_bot.py`: `_dispatch` ahora es fail-closed
  (`if user_id not in self.allowed_user_ids`); `main()` se niega a arrancar con
  la allowlist vacia en vez de quedar un bot mudo que rechaza a todos.
- **B (P1)** — `core/health.py` distingue `verified` de `configured`. El overall
  de `/health/dashboard` es `ok` solo si cada componente fue probado en vivo;
  `configured` (cableado, sin llamada real) ya no se pinta verde. Nuevo
  `POST /health/verify` que hace probe real (completion LLM minima, embedding
  real, login IMAP) bajo demanda del operador.
- **C (P1)** — kill switch `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` (default
  `true`) para la unica ruta de auto-deploy del plan de aprendizaje (Fase D,
  auto-promote de warnings). En `false` toda warning aprendida pasa por la
  puerta de aprobacion del operador.
- **D (P2)** — matriz parametrizada de los 37 comandos Telegram (auth-deny +
  no-crash) y comandos flag-gated.
- **E (P2)** — carril `tests/live/` (marker `live_readonly`, opt-in
  `LIVE_TESTS_ENABLED=1`): 7 smokes read-only contra proveedores reales +
  `scripts/full-qa-live.sh`.
- **F (P2)** — componente `operational_backlog` en health: approvals/jobs/
  action-requests atascados + lag del beat, con tile dedicado en el frontend.
- **G (P3)** — `scripts/sync_doc_counts.py` mantiene los conteos canonicos
  sincronizados con el codigo; `--check` corre dentro de `full-qa.sh`.
- **H (P3)** — `scripts/dev_up.sh` valida las variables que `docker compose`
  interpola sin default antes de levantar la infraestructura.

Pendiente (no funcional, higiene de repo): AUDIT-2026-I/J/K — bitacoras vivas
trackeadas, arboles de backup en el workspace, historia de fases en el README.

## Postura Del Producto

Cognitive OS esta optimizado para un **PC dedicado de Diego**, no para un
producto multiusuario expuesto a internet. La prioridad declarada por el
operador es:

1. **Friccion operativa casi nula por sobre seguridad estricta.**
2. Usar el perfil real de Edge cuando haga falta.
3. Permitir al agente operar ampliamente en el PC dedicado.
4. Mantener trazabilidad, diagnostico, idempotencia y recuperacion como
   controles principales.
5. Mantener una excepcion dura en mail: el flujo normal **no envia mails, no
   crea drafts y solo propone texto**. Diego copia y envia manualmente salvo
   peticion absolutamente explicita.

La seguridad estricta sigue documentada como referencia tecnica para `strict` o
para un futuro despliegue multiusuario, pero **no es el objetivo principal de
este host**. Para el modelo operativo vigente ver
[`ZERO_FRICTION_OPERATING_MODEL.md`](ZERO_FRICTION_OPERATING_MODEL.md).

## Snapshot Tecnico

Conteos estructurales derivados del codigo (generados por
`scripts/sync_doc_counts.py`; verificados en `full-qa.sh` con `--check`):

<!-- AUTO:counts:start -->
<!-- Generado por scripts/sync_doc_counts.py — no editar a mano. -->

| Conteo canónico | Valor |
|---|---|
| Endpoints REST (`@app.*` en `api/app.py`) | 147 |
| Tareas Celery (`workers/tasks.py`) | 23 |
| Migraciones Alembic (`alembic/versions/`) | 20 |
| Head Alembic | 202605200003 |
| Vistas frontend (`frontend/app/views/*.tsx`) | 20 |
<!-- AUTO:counts:end -->

| Area | Estado actual |
|---|---|
| Backend | FastAPI 0.115+, 147 decoradores REST en `api/app.py` |
| Frontend | Next.js 16.2.6 + React 19, 20 vistas en `frontend/app/views` |
| Infra | Docker Compose local con Postgres 16+pgvector, Redis 7, Weaviate 1.29.0, Neo4j 5; todo ligado a `127.0.0.1` |
| DB | 20 migraciones Alembic, head `202605200003`, `alembic check` sin drift |
| Celery | 23 tareas, 5 colas (`default`, `ingestion`, `agent_longrun`, `maintenance`, `mail`), hasta 13 jobs beat segun flags |
| Telegram | 37 slash commands; modo conversacional sin slash en `dedicated_local`; dispatch fail-closed |
| Mail | Gmail `TODOS`/`SPAM` + GoDaddy `Spam`; clasificacion propia del agente; digest 10:00 y 20:00 Chile; respuestas propuestas como texto |
| Health | `/health/dashboard` expone 18 componentes (17 checks + checkpointer); `/health/verify` hace probe en vivo |
| Learning | Fases A-E en produccion: recipes, failure postmortem, tool scorecard, skill promotion, nightly reflection; auto-promote con kill switch |
| Code Director | Planner LLM-driven + adapters Claude Code/Codex/Kimi/DeepAgents bajo budget/audit |
| Browser | Kimi WebBridge + Edge real disponibles para el perfil dedicado |
| LLM | primary+agent `gpt-5.5` (Responses API + prompt caching 24h), secondary/fallback `gemini-3.1-pro-low`, vision `glm-4.6v` |
| QA backend | `pytest` hermetico con DB de test aislada (`cognitive_os_test`) |
| QA frontend | Playwright oficial: 22 tests en desktop/mobile |
| QA oficial | `scripts/full-qa.sh` (build Next aislado en `.next-qa`); `stress-qa.sh` para flakiness; `full-qa-live.sh` opt-in para smokes reales |

## Ultimo Gate Verde Conocido

Gate ejecutado al cierre de la remediacion del audit (AUDIT-2026-A..H):

- `bash scripts/full-qa.sh` -> **941 passed, 1 skipped, 28 deselected**,
  ruff OK, ruff format OK, mypy OK (`135 source files`), Alembic check OK,
  `npm ci`, frontend lint OK, frontend build OK, `sync_doc_counts --check` OK,
  `git diff --check` OK.
- `bash scripts/stress-qa.sh 3` -> 3 pasadas verdes, **941 passed** en cada una.
- Carril live opt-in (`LIVE_TESTS_ENABLED=1 pytest -m live_readonly`):
  **8/8 smokes verdes** tras corregir el scope OAuth de Google Calendar (ver
  abajo).

Pendiente de re-validar tras reiniciar el runtime con el codigo nuevo:
`npx playwright test` (22 esperados) y `/health/dashboard` autenticado contra
el codigo nuevo. **El proceso `uvicorn` / `next start` vivo sigue sirviendo el
codigo previo hasta el proximo reinicio**; recien tras reiniciar apareceran
`POST /health/verify` y el componente `operational_backlog` (18 componentes en
total).

Si se necesita declarar un release nuevo, volver a correr estos comandos en el
mismo orden y actualizar este archivo con fecha y resultado.

## Hallazgo Resuelto: Scope OAuth De Google Calendar

El carril live detecto que `freeBusy` devolvia `HTTP 403
ACCESS_TOKEN_SCOPE_INSUFFICIENT` aunque `CalendarService.status()` informaba
`ready`. Causa: `GOOGLE_CALENDAR_SCOPES` estaba en
`https://www.googleapis.com/auth/calendar.events`, que permite crear/leer
eventos pero **no** la consulta free/busy. Correccion aplicada: se cambio a
`https://www.googleapis.com/auth/calendar` (acceso completo) y se re-corrio
`scripts/auth_google.py` para re-consentir. Verificado: `freeBusy` responde
`200`. Esto es exactamente el falso-positivo que AUDIT-2026-B/E buscaban
exponer.

## Mail: Contrato Actual

El contrato actual de mail no es "agente envia correo". Es:

1. Dos veces al dia, 10:00 y 20:00 horario Chile, el worker genera digest.
2. Fuentes por defecto:
   - Gmail `diegomanzurn@gmail.com`: `TODOS` + `SPAM`.
   - GoDaddy `diego@doctormanzur.com`: `Spam`.
3. El agente no confia en la carpeta del proveedor: clasifica por contenido.
4. Excluye solo lo que **el propio agente** clasifica como spam.
5. Resume los ultimos 50 correos considerados.
6. Para correos importantes, propone respuestas en un campo de texto separado.
7. No crea drafts en Gmail/GoDaddy.
8. No envia SMTP en el flujo normal.
9. El boton manual de sync del frontend usa `/mail/sync/dispatch` y encola el
   worker `mail`.
10. El digest manual del frontend usa `/mail/digest/preview` con
    `sync_first=false`, por lo que no bloquea el proceso API leyendo IMAP/Gmail.
11. Existe `/mail/digest/dispatch` para encolar digest largo en el worker `mail`.
12. El escape hatch de envio real exige simultaneamente:
    `ENABLE_EMAIL_SEND=true`, `MAIL_ALLOW_EXPLICIT_SEND=true` y
    `explicit_send_confirmation="SEND_THIS_EMAIL_EXPLICITLY"`.

## Health: Contrato De Honestidad

`/health/dashboard` no miente sobre lo que verifico:

- `ok` (componente) — probado en vivo o apagado honestamente (`disabled`).
- `configured` — credenciales/cableado completos pero **sin llamada real**.
- `degraded` — fallo real o estado desconocido.
- Overall: `ok` solo si todo esta `verified`; `configured` si algo esta
  cableado-pero-no-probado; `degraded` si algo fallo.
- `POST /health/verify` fuerza el probe real de los componentes que gastan
  tokens/latencia (`primary_llm`, `embeddings`, `mail`). El frontend tiene el
  boton "Verificar en vivo".
- Componente `operational_backlog`: approvals pendientes, jobs/action-requests
  atascados mas alla del umbral de su reaper, y lag del beat. Se pone `degraded`
  cuando un reaper deberia haber limpiado una fila y no lo hizo.

## Frontend

El cockpit definitivo es **dark-only glass cockpit**, PWA instalable, sin
Tailwind/shadcn/MUI. Reglas vigentes:

- Tokens visuales en `frontend/app/globals.css`.
- Iconos estructurales via `<Icon />`, no emojis/glifos.
- `asArray<T>` en vistas que consumen colecciones.
- `usePolledFetch` pausa offline/tab oculta y reintenta al volver.
- `StatePrimitives` para skeleton/empty/error.
- `useFocusTrap` en modales.
- `playwright.config.ts` bloquea service workers/cache para E2E determinista.
- `full-qa.sh` construye Next en `.next-qa`; no tocar `.next` si el panel vivo
  esta sirviendo desde `next start`.

## Que No Debe Afirmarse Sin Re-Validar

- No afirmar que proveedores externos escriben correctamente si no se ejecuto
  smoke real contra Google/GoDaddy/SMTP/Kimi. El carril `tests/live/`
  (`LIVE_TESTS_ENABLED=1 pytest -m live_readonly` o `scripts/full-qa-live.sh`)
  existe justamente para eso, read-only.
- `/health/dashboard` ya NO miente: el overall es `ok` solo si cada componente
  fue verificado en vivo; si alguno esta solo `configured` el overall es
  `configured`, no `ok`. Para forzar la verificacion real usar `POST /health/verify`.
- No decir que la seguridad es de grado SaaS/multiusuario. El sistema actual es
  local, mono-operador y deliberadamente permisivo.
- No decir que el agente envia mails automaticamente. No lo hace y no debe
  hacerlo en el flujo normal.
- No afirmar que el runtime vivo ya corre el codigo nuevo sin haberlo
  reiniciado: `uvicorn`/`next start` cachean el codigo de arranque.
