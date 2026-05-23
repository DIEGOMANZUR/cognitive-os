# CODEX COMMERCIAL READINESS AUDIT — Cognitive OS

> **Esta versión (2026-05-22, reescrita tras lectura profunda)** reemplaza dos
> auditorías previas en este mismo path:
>
> 1. Una auditoría del 2026-05-20 hecha bajo postura previa "strict / multi-tenant".
> 2. Una primera versión mía del 2026-05-22 que evaluó el sistema contra una
>    definición SaaS de "grado comercial". **Esa definición era incorrecta**.
>    Tras leer los 22 markdowns activos del proyecto — y muy especialmente
>    `CURRENT_STATE.md` + `ZERO_FRICTION_OPERATING_MODEL.md` + `AGENT_SELF.md` —
>    queda claro que el producto declara explícita y deliberadamente:
>    **"fricción casi nula por sobre seguridad estricta"** en `dedicated_local/full`,
>    con la sola excepción dura de mail. Esos no son bugs, son features.
>
> La nota previa del propio Codex/Diego al inicio del audit anterior es exacta:
> *"los hallazgos de seguridad sobre `dedicated_local/full`, auto-approve, Edge real
> o acceso amplio al PC pasan a ser riesgos aceptados del perfil local, no
> bloqueantes del objetivo actual"*. Este nuevo informe lo aplica desde la línea 1.

Fecha: **2026-05-22**
Auditor: Claude Opus 4.7 (responsable técnico entrante / release gatekeeper)
Modo: lectura → **remediación aplicada** (ver §0.1).
Branch vigente: `codex/commercial-zero-friction-hardening` · último commit
verificado `5953b40`.

---

## 0.1 Estado de remediación (2026-05-22, post-auditoría)

Tras la auditoría se ejecutó la remediación completa de **todos** los hallazgos
accionables: las 8 funcionales (A–H) y las 3 de higiene de repo (I–K).
`L`/`M` eran informativos (decisiones conscientes). Resumen:

| Hallazgo | Sev | Estado | Qué se hizo |
|---|---|---|---|
| AUDIT-2026-A | P0 | ✅ Resuelto | `_dispatch` ahora es fail-closed (`if user_id not in self.allowed_user_ids`); `main()` se niega a arrancar con allowlist vacía. +3 tests + matriz de 37 comandos. |
| AUDIT-2026-B | P1 | ✅ Resuelto | `health.py` distingue `verified` de `configured`; overall `ok`/`configured`/`degraded` honesto. Nuevo `POST /health/verify` (probe LLM/embeddings/IMAP real). Frontend: `configured`→warn, badges, sección "Verificación en vivo". |
| AUDIT-2026-C | P1 | ✅ Resuelto | Kill switch `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` (default `true`); gate en `failure_postmortem.py`; §1/§3.4 del plan, README y `DEEPAGENTS_SKILLS_MEMORY.md` reconocen la excepción; flag en `/config/public` + badge en MemoryView. |
| AUDIT-2026-D | P2 | ✅ Resuelto | Matriz parametrizada: 37 comandos × {auth-deny, no-crash} + flag-disabled + registro canónico. ~78 tests nuevos. |
| AUDIT-2026-E | P2 | ✅ Resuelto | Carril `tests/live/` (marker `live_readonly`, opt-in `LIVE_TESTS_ENABLED=1`), 8 smokes read-only + `scripts/full-qa-live.sh`. |
| AUDIT-2026-F | P2 | ✅ Resuelto | `_check_operational_backlog` en health: approvals/jobs/action-requests atascados + lag del beat. Tile "Backlog operacional" en HealthView. |
| AUDIT-2026-G | P3 | ✅ Resuelto | `scripts/sync_doc_counts.py` genera el bloque `AUTO:counts` de `CURRENT_STATE.md`; `--check` corre en `full-qa.sh`. |
| AUDIT-2026-H | P3 | ✅ Resuelto | `dev_up.sh` valida variables sin default antes de `docker compose`; RUNBOOK documenta el comando único. |
| AUDIT-2026-I | P3 | ✅ Resuelto | `task_plan.md`, `findings.md`, `progress.md` y los transcripts de sesión quedaron gitignored y fuera de control de versiones (archivos de trabajo locales). `AGENTS.md` y `docs/README.md` lo reflejan. |
| AUDIT-2026-J | P3 | ✅ Resuelto | `cognitive-os-backup-*/` y `cognitive-os-snapshot-*/` ya están gitignored; no contaminan el control de versiones. Su reubicación física fuera del workspace queda a criterio del operador. |
| AUDIT-2026-K | P3 | ✅ Resuelto | `README.md` reescrito: se eliminó la pila de snapshots históricos por fase; queda un único snapshot vigente + sección "Cambios Recientes". |
| AUDIT-2026-L/M | — | Informativo | Decisiones conscientes documentadas; no requieren acción. |

**QA post-remediación actualizada por hardening zero-friction:** `bash
scripts/full-qa.sh` verde — backend **944 passed,
1 skipped, 28 deselected**, ruff/format/mypy/Alembic verdes, frontend
lint/build verdes, `sync_doc_counts --check` y `git diff --check` verdes.
`npx playwright test --reporter=list` -> 31 passed. `stress-qa.sh 3` ->
3 pasadas de 944 passed sin flakiness.
`LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` -> 8 passed
(2 warnings de deprecacion MCP upstream, no bloqueantes). TestSprite MCP/CLI
-> 3/3 passed como smoke advisory acotado.

**Hallazgo live de Google Calendar resuelto:** el carril live habia detectado
`HTTP 403` en `GET /freeBusy` pese a que `CalendarService.status()` informaba
`ready`. Se corrigio con scope `https://www.googleapis.com/auth/calendar` y
re-consentimiento OAuth; `full-qa-live.sh` actual pasa el smoke de Google.

**Ajuste post-audit `5953b40`:** `/system/mcp` carga inventario de servidores
en paralelo, `MCP_INVENTORY_TIMEOUT_SECONDS` default 30s, runtime verificado
5/5 servers (`mem`, `gh`, `fs`, `cc`, `gem`) y 67 tools. El frontend estabiliza
`Ctrl/Cmd+K` del command palette con listener en capture phase.

---

## 0. Veredicto ejecutivo

**¿Grado comercial real, según la propia definición del producto?**
**Casi sí.** El sistema cumple **8 de los 9 criterios** que
`ZERO_FRICTION_OPERATING_MODEL.md` §"Qué significa grado comercial en este PC"
define como objetivo. Hay **un (1) P0 técnico real**, **dos (2) P1 que afectan
la promesa "fallos visibles"**, y el resto son P2/P3 de pulido.

| Criterio declarado por el producto | Estado verificado |
|---|---|
| Arranque reproducible | ✅ `dev_up.sh`, launchers de Escritorio con `flock` + preflight, `verify_desktop_launchers.sh`, `init_env.sh` |
| Stack local diagnosticable | ⚠️ `/health/dashboard` muestra `ok` global aunque LLM/embeddings/mail/MCP estén sólo `configured` (P1) |
| Jobs no se pierden silenciosamente | ✅ `dispatch_state` reservado atómicamente, `JobEvent submitted/failed`, 3 reapers |
| UI no miente sobre lo que hace | ✅ mail UI sin botón Enviar; badges "send bloqueado / sync continuo"; defensive `asArray<T>` |
| Mail cumple contrato lectura/propuesta | ✅ verificado en `MailInboxView.tsx`, `mail/service.py`, `actions/mail.py`, `actions/gmail_digest.py` |
| Frontend no queda deshidratado tras QA | ✅ `cfdd9f7` introdujo el isolated build en `.next-qa` |
| Tests/build/lint/mypy/Alembic/E2E verdes | ✅ Sesión: pytest 848, ruff/format/mypy/lint/build verdes; doc canónico confirma Playwright 22 |
| Fallos de credenciales/proveedores quedan visibles | ⚠️ Parcial — health agrega `configured` como `ok`; sin readiness live (P1) |
| El operador no tiene que adivinar qué está mal | ⚠️ Parcial — backlog de approvals / jobs zombie / dispatch zombies sin contadores en health (P2) |

**Veredicto operativo:** firmaría como responsable técnico de este sistema
**inmediatamente después** de cerrar 3 hallazgos:

1. **AUDIT-2026-A** — Telegram `_dispatch` fail-open con allowlist vacía (P0). ~45 min.
2. **AUDIT-2026-B** — `/health/dashboard` debe distinguir `configured` de `verified_live` (P1). ~2 h.
3. **AUDIT-2026-C** — Contradicción interna en `AGENT_LEARNING_PLAN.md` §1 vs §3.4 sobre auto-promote de warnings (P1 docs). ~30 min.

Total mínimo: **~3-4 horas de trabajo** para cumplir los 9 criterios.

### Lo que CERRÉ del audit anterior (no eran bugs, eran features documentadas)

Mi primera versión llamó P0/P1 a comportamientos que el producto **declara
explícitamente como features intencionales**. Tras leer los docs canónicos:

| Hallazgo previo | Severidad previa | Razón de cierre |
|---|---|---|
| `dedicated_local + full` auto-aprueba acciones irreversibles | P0 | `ZERO_FRICTION_OPERATING_MODEL.md` declara "fricción casi nula > seguridad estricta" como postura. `SECURITY.md` actualizado, `ARCHITECTURE.md`, `ACTION_PLANE.md`, `AGENT_SELF.md` están alineados. Mail es la excepción dura y se sostiene. **No es bug.** |
| MCP filesystem en `/home/jgonz`, Kimi WebBridge con perfil real de Edge | P1 | `AGENT_SELF.md` §2.7 + `ZERO_FRICTION_OPERATING_MODEL.md` lo declaran. Riesgo asumido conscientemente. **No es bug.** |
| Mail send paralelo al Action Plane | P2 | `CURRENT_STATE.md` §"Mail: Contrato Actual" + `USER_GUIDE.md` §6.8 + `ACTION_PLANE.md` §"Endpoints" formalizan que mail no pasa por ActionRequest. UI sin botón Enviar. Escape hatch SMTP con 3 condiciones simultáneas (`ENABLE_EMAIL_SEND=true` + `MAIL_ALLOW_EXPLICIT_SEND=true` + literal `SEND_THIS_EMAIL_EXPLICITLY`). **No es bug.** |
| OpenHarness `research/full` con FULL_AUTO | P2 | Opt-in (`ENABLE_OPENHARNESS_RESEARCH=false` default). Documentado en `SECURITY.md` y `OPENHARNESS_FUSION.md` §10 como "capacidad de operador consciente". **No es bug.** |
| dedicated_local relaja four-eyes y TTL approvals (168h vs 48h) | P1 | Declarado en `USER_GUIDE.md` §8 y `SECURITY.md`. **No es bug.** |

**Mi error fue:** evalué el sistema contra una definición de "grado comercial"
que el sistema NO se propone cumplir. Una vez aplicada la lente correcta
(PC dedicado mono-operador, no SaaS), los hallazgos reales se reducen
significativamente y se concentran donde el modelo zero-friction NO debería
fallar: el perímetro externo (Telegram), la honestidad del diagnóstico
(health), y la coherencia interna de los docs.

---

## 1. Cómo entiendo el proyecto (demostración de comprensión)

### 1.1 Identidad declarada del producto

Cognitive OS es **un sistema cognitivo local-first para una sola persona
en un PC dedicado**. Declaración canónica en:

- `docs/CURRENT_STATE.md` (120 LOC) — fuente corta de verdad operativa.
- `docs/ZERO_FRICTION_OPERATING_MODEL.md` (106 LOC) — la postura íntegra.
- `docs/AGENT_SELF.md` §1 (237 LOC total) — la "soul" del agente, cargada
  como SystemMessage en cada conversación.
- `AGENTS.md` (top-level, 388 LOC) — declaración para futuros agentes que
  toquen el repo.

La regla: **"fricción casi nula por sobre seguridad estricta"**. Los
controles principales NO son approvals — son trazabilidad, idempotencia,
reapers, timeouts, errores visibles, health, tests herméticos, secretos
fuera de git, y build aislado.

**Excepción dura — mail:** el flujo normal NO envía, NO crea drafts,
sólo propone texto. Razón documentada: "enviar un correo no es solo una
acción técnica; es comunicación humana externa".

### 1.2 Operador real

`AGENT_SELF.md` declara: Diego Manzur, `OPERATOR_PROFILE=dedicated_local`,
`TELEGRAM_AUTHORIZED_USER_IDS=7582093979`, bot `@Socio_dimn_bot`, PC
personal con perfil real de Edge logueado a Google/GoDaddy/Gmail/banca.

### 1.3 Arquitectura (verificada esta sesión contra el código)

- Backend FastAPI 0.115+ con **146 decoradores REST** (`api/app.py`).
- LangGraph 1.1.10 orquestador con grafo Planner → Researcher → Synthesizer
  → Scorer + subgrafos especializados.
- DeepAgents 0.6.x con **21 tools built-in tipadas** + tools dinámicas
  MCP cuando `ENABLE_MCP_CLIENT=true`.
- **23 tasks Celery** en **5 colas** (`default`, `ingestion`,
  `agent_longrun`, `maintenance`, `mail`) + **10 beat jobs**.
- **20 migraciones Alembic**, head `202605200003`, `alembic check`
  sin drift.
- **20 vistas Next.js 16.2.6** + PWA dark-only sin Tailwind/shadcn/MUI.
- **37 comandos Telegram** + modo conversacional sin slash en
  `dedicated_local`.
- Postgres 16+pgvector / Redis 7 / Weaviate 1.29 / Neo4j 5 — todos en `127.0.0.1`.
- **17 componentes en `/health/dashboard`**.

Cadena LLM verificada en Fase 66-74: primary+agent `gpt-5.5`,
secondary/fallback `gemini-3.1-pro-low`, visión `glm-4.6v`, Kimi-k2.6
sólo vía CLI del Code Director (HTTP da 403 documentado), embeddings
`gemini-embedding-001`. Modelos *reasoner* (tipo `deepseek-v4-pro`)
**rompen el DeepAgent en silencio** porque no soportan `tool_choice`
forzado — bug histórico documentado, ya resuelto al fijar `gpt-5.5`.

### 1.4 Plan de aprendizaje autónomo (Fases A-E, cerradas)

`docs/AGENT_LEARNING_PLAN.md` (1028 LOC) documenta:

| Fase | Trigger | Salida | Approval |
|---|---|---|---|
| **A** Recetas | beat */30 min | proposal `kind=procedure` (jobs ≥5 tools, ≥30s, status=succeeded) | Operator |
| **B** Skill promotion | beat 04:45 UTC | proposal `auto-skill YAML` (procedure ≥3 éxitos, <30% fallos) | **Explícito siempre** |
| **C** Tool scorecard | beat 04:15 UTC | `tool_invocation_metrics` rollup diario, inyectado al system prompt | (no requiere — es lectura) |
| **D** Failure post-mortem | beat 03:35 UTC | proposal `kind=warning` (patrón fail→fix) | **AUTO-promueve tras 3 detecciones** §3.4 |
| **E** Nightly reflection | beat 03:00 UTC | proposal `preference`/`lesson` con quote literal obligatoria | Operator + auto-disable si >50% rechazo |

**Contradicción interna identificada (AUDIT-2026-C):** el plan declara
en §1 "Principio rector: cero auto-deploy" pero §3.4 documenta el
auto-promote de Fase D. Esto sí es un hallazgo real, ver §3.2.

### 1.5 Action Plane

Ciclo: `validate → preview → request → approve → dispatch → execute → audit`.

- **En `strict`:** preview-first + `HumanApproval` para todo `EXTERNAL_ACTION`/`DANGEROUS`.
- **En `dedicated_local + full`:** `_should_auto_approve_action()` retorna
  `True` para **todo `action_type`** (salvo Mail con sus 3 flags y GoDaddy con
  sus 2 flags `dry_run_only` + `allow_production_writes` que actúan como
  capas externas independientes).
- **En `dedicated_local + guarded`:** auto-approve sólo para whitelist
  reversible: `drive_ensure_folder`, `drive_upload_file`,
  `computer_organize`.
- **`dispatch_state=submitting|submitted|failed`** reservado atómicamente
  con `SELECT ... FOR UPDATE` antes de `apply_async`.
- **`JobEvent action_request_dispatch_submitted/failed`** da visibilidad
  si broker cae.
- Worker `run_action_request_task_async` short-circuit si AR ya está
  `running` (anti broker-duplicate).

Esta capa es la **más sólida del sistema**. La idempotencia atómica es
ingeniería de calidad poco común en sistemas de este tamaño.

### 1.6 Telegram bot

Bot `@Socio_dimn_bot` con long-poll (sin webhook → NAT-friendly).
Comparte el **mismo service layer** que el panel REST — un `/approve`
por Telegram deja `AuditEvent actor="telegram:<chat_id>"`. Memoria
de conversación persistente por `chat_id` (LangGraph PostgresSaver).
En `dedicated_local`, mensajes sin slash entran al orquestador.
`/reset` rota el salt.

**El bot es la única superficie externa autenticada del sistema** —
único punto donde un mensaje puede entrar al sistema desde fuera del PC.
La auth se basa exclusivamente en `TELEGRAM_AUTHORIZED_USER_IDS`.

### 1.7 Frontend (cockpit Glass)

`FRONTEND_ARCHITECTURE.md` (299 LOC) lo documenta exhaustivamente:

- Next.js 16 App Router + React 19 + TypeScript estricto.
- CSS hand-rolled con tokens en `globals.css`. NO Tailwind, NO shadcn,
  NO styled-components.
- Tipografía Inter + JetBrains Mono self-hosted vía `next/font/google`.
- Iconografía: componente `<Icon name="…" />` con ~55 SVGs curados.
- Charts SVG puro en `components/Charts.tsx` (Sparkline/AreaChart/BarList/Donut).
- PWA instalable: manifest con 4 shortcuts, SW versionado
  `cogos-v2026-05-20-glass-2`, offline shell.
- Patterns clave: `usePolledFetch` resiliente (pausa offline/tab oculta,
  refetch al volver), `asArray<T>` defensive en 13 vistas,
  `StatePrimitives` (Skeleton/EmptyState/ErrorPanel/DataBoundary).
- A11y: `useFocusTrap` en modales, skip-link al main, role="dialog" +
  aria-modal + ESC.
- JWT en `localStorage` bajo `cogos.token` (riesgo XSS asumido para
  cockpit local single-operator).
- 22 specs Playwright passing según `CURRENT_STATE.md` y
  `ACCEPTANCE_CHECKLIST.md`.

### 1.8 Health dashboard

`core/health.py` agrega 17 componentes en `/health/dashboard`:
postgres, redis, weaviate, neo4j, primary_llm, embeddings, workers,
langsmith, voice, maps, google_calendar, google_drive, kimi_webbridge,
captcha_solver, mail, mcp_client, checkpointer. **El cálculo de
`overall`** mezcla `ok` (live verificado) con `configured` (sólo wiring
sin probe live) — ver AUDIT-2026-B.

---

## 2. QA verificado esta sesión

| Comando | Resultado |
|---|---|
| `cd backend && uv run pytest -q -x` | **✅ 848 passed, 1 skipped, 20 deselected** en 34s |
| `cd backend && uv run ruff check .` | ✅ All checks passed |
| `cd backend && uv run ruff format --check .` | ✅ 274 files already formatted |
| `cd backend && uv run mypy src` | ✅ 0 issues en 135 source files |
| `cd backend && uv run alembic heads` | ✅ `202605200003 (head)` |
| `cd backend && uv run alembic check` | ✅ No new upgrade operations detected |
| `cd frontend && npm run lint` | ✅ 0 warnings (`--max-warnings 0`) |
| `cd frontend && NEXT_DIST_DIR=.next-audit npm run build` | ✅ verde, **pero modificó `tsconfig.json` (incidente §9)** |
| `git status --short` | ` M cognitive-os/docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md` + ` M cognitive-os/frontend/tsconfig.json` |

**Nota post-hardening:** esta seccion conserva la evidencia de la sesion de
auditoria original. El cierre vigente posterior reejecuto los gates completos:
`full-qa.sh` 944 passed, Playwright 31 passed, stress QA 3 pasadas de 944,
live-readonly 8 passed, MCP 5/5 con 67 tools y TestSprite 3/3 passed como
smoke advisory.

**Conclusión:** el gate oficial está verde. Los componentes que reejecuté
independientemente confirman. No hay regresión detectable.

---

## 3. Hallazgos vigentes (con la lente correcta)

### 3.1 P0 — el único bloqueador real

#### AUDIT-2026-A — Telegram `_dispatch` acepta a CUALQUIER usuario cuando `TELEGRAM_AUTHORIZED_USER_IDS` está vacío

**Severidad:** P0 Critical
**Categoría:** Security-operational / Bug fail-open
**Área:** Telegram / Auth perímetro externo
**Estado:** Confirmado

**Evidencia:**

`backend/src/cognitive_os/integrations/telegram_bot.py:195`:
```python
if self.allowed_user_ids and user_id not in self.allowed_user_ids:
    self.send(chat_id, "🚫 *Forbidden*. Tu user_id no está en TELEGRAM_AUTHORIZED_USER_IDS.")
    return
```

Semántica Python: si `self.allowed_user_ids == set()` (vacío), entonces
`if {} and (...)` evalúa **False** → NO rechaza al usuario → el dispatch
sigue procesando el mensaje.

`backend/src/cognitive_os/integrations/telegram_bot.py:1613-1619`:
```python
allowed = set(settings.telegram_authorized_user_ids)
if not allowed:
    logger.warning(
        "TELEGRAM_AUTHORIZED_USER_IDS vacío — el bot rechazará todos los mensajes. "
        "Pegale tu user_id (entero, separado por coma)."
    )
bot = TelegramBot(token=token, allowed_user_ids=allowed)
```

**El log de arranque promete rechazo total; el `_dispatch` real hace lo opuesto.**

`cognitive-os/.env.example:185-187`:
```
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=CHANGEME
TELEGRAM_AUTHORIZED_USER_IDS=
```

La plantilla viene con el campo vacío.

`backend/tests/test_telegram_bot.py:420,454`: TODOS los tests usan
`allowed_user_ids={42}`. **0 tests cubren el caso `set()`**.

**Por qué este SÍ es P0 incluso en zero-friction:**

El modelo "fricción casi nula" del producto se aplica a controles
INTERNOS (approvals por action_type, four-eyes off, allow-lists amplias
para Edge/computer/MCP en perfil dedicado). PERO el bot de Telegram es
la **única superficie externa autenticada** del sistema. `AGENT_SELF.md`
§1 declara: *"Single-operator. El único humano autorizado es Diego (...).
No multi-cliente, no tenant, todo bound a 127.0.0.1."* — esa frontera
**existe precisamente porque Telegram es la única excepción**, el
único punto donde un mensaje entra desde fuera del 127.0.0.1.

Escenario realista de fallo:

1. Operador clona el repo nuevo (o un colaborador hace handoff).
2. Copia `.env.example` a `.env`.
3. Pone `TELEGRAM_ENABLED=true`, pega su `TELEGRAM_BOT_TOKEN`.
4. **Olvida pegar su `TELEGRAM_AUTHORIZED_USER_IDS`** (o lo deja vacío
   pensando que el warning del log lo protege).
5. Arranca el bot. El log dice "rechazará todos los mensajes" pero el
   código acepta cualquier `user_id`.
6. Cualquier persona que descubra el bot (filtrando el username
   `@Socio_dimn_bot` o si el token leakea) puede:
   - `/health`, `/jobs`, `/stats`, `/audit` — lectura del estado.
   - `/chat <mensaje>` → consume tokens del gateway LLM del operador.
   - Mensajes sin slash → modo conversacional persistente.
   - `/approve <prefijo>` → aprueba `HumanApproval` pendientes del
     operador (cualquiera de las que estén esperando).
   - `/maps`, `/drive`, `/calendar`, `/research`, `/codebuild` → toca
     integraciones externas con credenciales del operador.

**Esto NO es fricción interna que se afloja. Es la única auth de la
única puerta externa, fallando abierta.** No tiene defensa-en-profundidad
detrás — no hay segundo gate.

**Cómo lo resolvería (cambio mínimo + tests):**

1. `backend/src/cognitive_os/integrations/telegram_bot.py:195`:
   ```python
   if user_id not in self.allowed_user_ids:   # lista vacía deniega todo
       self.send(chat_id, "🚫 *Forbidden*. Tu user_id no está en TELEGRAM_AUTHORIZED_USER_IDS.")
       return
   ```

2. `backend/src/cognitive_os/integrations/telegram_bot.py` en el
   bootstrap (línea ~1613):
   ```python
   allowed = set(settings.telegram_authorized_user_ids)
   if not allowed:
       logger.error(
           "TELEGRAM_AUTHORIZED_USER_IDS vacío con bot configurado. "
           "Rehúso arrancar el bot — pegale tu user_id antes de habilitar."
       )
       raise SystemExit(2)
   ```

3. `backend/src/cognitive_os/core/config.py` — añadir un
   `@model_validator(mode="after")`:
   ```python
   def reject_telegram_bot_without_allowlist(self) -> Self:
       if self.environment == "production" and self.telegram_enabled:
           if not self.telegram_authorized_user_ids:
               msg = "TELEGRAM_ENABLED=true requires TELEGRAM_AUTHORIZED_USER_IDS"
               raise ValueError(msg)
       return self
   ```

4. `cognitive-os/.env.example:187`:
   ```
   TELEGRAM_AUTHORIZED_USER_IDS=<tu user_id numerico>  # obligatorio si TELEGRAM_ENABLED=true
   ```

5. **Tests nuevos en `backend/tests/test_telegram_bot.py`** (3 tests):

   ```python
   def test_dispatch_rejects_with_empty_allowed_user_ids(monkeypatch):
       bot = telegram_bot.TelegramBot(token="fake", allowed_user_ids=set())
       sent: list[str] = []
       monkeypatch.setattr(bot, "send", lambda c, t, markdown=True: sent.append(t))
       bot._dispatch({"message": {"text": "/health", "chat": {"id": 999}, "from": {"id": 999}}})
       assert any("Forbidden" in s for s in sent)

   def test_dispatch_rejects_unknown_user_with_populated_allowlist(monkeypatch):
       bot = telegram_bot.TelegramBot(token="fake", allowed_user_ids={42})
       sent: list[str] = []
       monkeypatch.setattr(bot, "send", lambda c, t, markdown=True: sent.append(t))
       bot._dispatch({"message": {"text": "/health", "chat": {"id": 7}, "from": {"id": 7}}})
       assert any("Forbidden" in s for s in sent)

   def test_run_forever_refuses_to_start_with_token_and_empty_allowlist(monkeypatch):
       from cognitive_os.core.config import settings as runtime_settings
       monkeypatch.setattr(runtime_settings, "telegram_bot_token",
                           type("S", (), {"get_secret_value": lambda self: "real-token"})())
       monkeypatch.setattr(runtime_settings, "telegram_authorized_user_ids", [])
       with pytest.raises(SystemExit) as exc:
           telegram_bot.main()  # o el entry point real
       assert exc.value.code == 2
   ```

**Criterio de aceptación:**
- Update con cualquier `text` y `from.id` NO en allowlist → NO se procesa
  (responde Forbidden).
- Allowlist vacía → NO se procesa ningún mensaje (responde Forbidden).
- `python -m cognitive_os.integrations.telegram_bot` con token configurado
  y allowlist vacía → `SystemExit(2)`.
- En `ENVIRONMENT=production`, Settings rechaza la combinación al cargar.

**Riesgo de reparación:** Bajo (~15 líneas + 3 tests).
**Esfuerzo:** ~45 min.
**Prioridad:** **1 (bloqueante).**

---

### 3.2 P1 High — afectan la promesa "fallos visibles"

#### AUDIT-2026-B — `/health/dashboard` reporta `status=ok` aunque proveedores estén sólo "configured" sin probe live

**Severidad:** P1 High
**Categoría:** Fake readiness / observability
**Estado:** Confirmado (reconocido por `CURRENT_STATE.md`)

**Evidencia:**

`backend/src/cognitive_os/core/health.py:106-113`:
```python
overall = (
    "ok"
    if all(component.status in {"ok", "configured", "disabled", "ready"}
           for component in components)
    else "degraded"
)
```

`_check_primary_llm` (líneas 190-208): si `PRIMARY_LLM_API_KEY != "CHANGEME"`  <!-- pragma: allowlist secret -->
retorna `configured` (no `ok`), pero el overall lo agrega como `ok`.

`_check_embeddings` (211-236): mismo patrón.

`_check_mail` (355-396): comentario explícito *"No live connection:
avoids per-/health latency and keeps the GoDaddy/Gmail credentials out
of every dashboard hit. Matches the contract used by primary_llm and
embeddings (configured iff wiring is complete)."*

`CURRENT_STATE.md` líneas 114-116:
> *"No confundir `/health/dashboard status=ok` con prueba de proveedor
> real: varios checks indican `configured` cuando hay credenciales pero
> no hacen una llamada completa al proveedor."*

`ZERO_FRICTION_OPERATING_MODEL.md` línea 84:
> *"El operador no tiene que adivinar qué está mal."*

**Por qué P1:** el modelo zero-friction descansa explícitamente en
"trazabilidad, diagnóstico rápido, fallos visibles" como controles
principales. Health miente verde mientras la API key del LLM está
revocada → el operador pierde tiempo persiguiendo errores fantasma. El
doc canónico explícitamente advierte de este gap como "no debe afirmarse
sin re-validar" — está reconocido pero no resuelto.

**Cómo lo resolvería (2 pasos independientes):**

**Paso 1 — Cambio rápido (no rompe nada, ~30 min):**

`backend/src/cognitive_os/core/health.py` — recalcular `overall` distinguiendo:
```python
VERIFIED_STATES = {"ok", "ready"}
CONFIGURED_STATES = {"configured", "disabled"}

statuses = {c.status for c in components}
if any(s not in (VERIFIED_STATES | CONFIGURED_STATES) for s in statuses):
    overall = "degraded"
elif statuses & CONFIGURED_STATES:
    overall = "configured"  # algunos componentes sólo wiring-OK
else:
    overall = "ok"  # todos verificados live
```

`frontend/app/views/HealthView.tsx`:
- `overall == "ok"` → badge verde.
- `overall == "configured"` → badge ámbar con tooltip *"Componentes
  configurados pero sin verificación live. Ejecutá `/health/verify` para
  probar."*
- `overall == "degraded"` → badge rojo.

`frontend/app/views/DashboardView.tsx`:
- Mismo tratamiento en el "Estado global".

Tests (`backend/tests/test_health_dashboard.py`):
```python
def test_overall_with_only_configured_returns_configured(): ...
def test_overall_with_one_degraded_returns_degraded(): ...
def test_overall_with_all_verified_returns_ok(): ...
```

**Paso 2 — Probe live opcional con cache (~1.5 h):**

- Flag `HEALTH_LIVE_VERIFICATION_ENABLED` (default `false` — no gastar
  tokens en cada poll del dashboard).
- Endpoint nuevo `POST /health/verify` (admin) que dispara probes live:
  - LLM con `max_tokens=1`, prompt mínimo.
  - Embeddings con string de 5 chars.
  - MCP con `mcp.list_tools()` por server.
  - Mail con `EHLO` (no enviar) IMAP/SMTP.
- Resultado cacheado 15 min.
- `ComponentHealth` añade campo `last_verified_live_at: datetime | None`.
- Beat opcional `health-verify` cada 15 min si la flag está activa.

**Archivos:** `core/health.py`, `api/app.py`, `core/config.py`,
`frontend/app/views/HealthView.tsx`, `frontend/app/views/DashboardView.tsx`,
`workers/tasks.py`, `workers/celery_app.py` (beat schedule).

**Criterio de aceptación:** un operador que mira `/health/dashboard` y ve
`ok` global puede asumir que LLM, embeddings, mail y MCP están realmente
funcionando (no sólo configurados). Si están sólo configurados, el
overall lo refleja con badge "configured" (no "ok").

**Esfuerzo:** ~2-3 horas.
**Prioridad:** 2.

---

#### AUDIT-2026-C — `AGENT_LEARNING_PLAN.md` contradice su propio principio rector

**Severidad:** P1 High (docs / contrato)
**Categoría:** Docs drift interna
**Área:** Learning plan / Memory
**Estado:** Confirmado por lectura literal

**Evidencia (contradicción literal dentro del mismo documento):**

`docs/AGENT_LEARNING_PLAN.md` §1.0 "Visión general del plan",
líneas 149-152:
> *"**Principio rector:** todo aprendizaje pasa por **proposals** →
> **operator approval** → **records activos**. **Cero `auto-deploy` de
> cambios al comportamiento.**"*

`docs/AGENT_LEARNING_PLAN.md` §3.4 "Política de promoción" (Fase D —
Failure post-mortem), línea 602:
> *"| 3ra detección del **mismo patrón** (similarity de embedding ≥ 0.85)
> | **Auto-promover a `DeepAgentMemoryRecord(kind="warning", source="consolidated")`
> sin approval** (es un patrón ya validado por evidencia) |"*

`backend/src/cognitive_os/deepagents/failure_postmortem.py:280-317`
**implementa exactamente §3.4**: si `occurrence_index >= threshold and
rejected_count == 0`, crea memoria activa con
`approved_by="auto_promotion"`.

`cognitive-os/ACCEPTANCE_CHECKLIST.md` línea 111 marca:
`[x] 3 detecciones del mismo patrón sin rechazo → auto-promoción a activo`.

`docs/DEEPAGENTS_SKILLS_MEMORY.md` línea 54:
*"`kind=warning` desde patrones `tool_failed → tool_succeeded`;
auto-promueve tras 3 repeticiones"*.

`cognitive-os/README.md` línea 33-35:
*"Todo el aprendizaje pasa por el approval gate del operador — cero
auto-deploy de comportamiento"*.

**Por qué P1:**

- La memoria activa **se inyecta al system prompt** del agente
  (`AGENT_LEARNING_PLAN.md` §3.5). Un warning auto-promovido **modifica
  el comportamiento del agente** sin que el operador lo vea
  explícitamente.
- El falso positivo se archiva tras 3 fallos (mitigación documentada),
  pero entre la auto-promoción y los 3 fallos el warning está activo y
  puede sesgar decisiones futuras.
- Más grave: las afirmaciones del README y SKILLS_MEMORY se vuelven
  literalmente falsas para alguien que las lee como contrato.
- El operador queda con una expectativa de "approval gate total" que no
  se cumple para Fase D.
- Esta confusión es exactamente lo que rompe la promesa zero-friction
  de "diagnóstico claro" — el operador no sabe por qué el agente
  cambió de comportamiento.

**Decisión necesaria del producto (Diego decide):**

**Opción A — Honrar el principio §1 (eliminar el auto-promote):**

- Cambiar `failure_postmortem.py:280-317` para que 3 detecciones
  generen una proposal de "alta confianza", NO una memoria activa.
- Actualizar §3.4, `ACCEPTANCE_CHECKLIST.md`, `DEEPAGENTS_SKILLS_MEMORY.md`.
- Costo: el operador debe aprobar warnings manualmente.
- Beneficio: el contrato queda íntegro.

**Opción B — Honrar §3.4 (la realidad implementada, docs-mayor):**

- Actualizar §1 del plan, README y SKILLS_MEMORY para decir:
  *"todo aprendizaje pasa por proposal → approval, **con la excepción
  documentada de warnings de Fase D que auto-promueven tras 3
  detecciones por evidencia estadística**"*.
- Añadir kill switch `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` (default
  `true`) en `core/config.py` para que el operador pueda apagarlo si
  prefiere comportamiento estricto.
- En la UI `MemoryView`, distinguir visiblemente warnings con
  `approved_by="auto_promotion"` de los aprobados por humano (badge
  diferente, posibilidad de revertir).
- Costo: cambio principalmente docs + flag.
- Beneficio: el comportamiento estadísticamente validado se mantiene,
  pero el contrato queda íntegro.

**Mi recomendación: Opción B.**

La evidencia estadística de 3 detecciones es defendible y el sistema ya
tiene archive automático tras 3 falsos positivos. Lo que rompe es la
frase categórica "cero auto-deploy". Basta arreglar la frase y dar
control al operador con un flag.

**Archivos (Opción B):**

- `docs/AGENT_LEARNING_PLAN.md` §1 — añadir la excepción.
- `docs/DEEPAGENTS_SKILLS_MEMORY.md` línea 47 — explicitar Fase D.
- `cognitive-os/README.md` líneas 33-35 — matizar.
- `backend/src/cognitive_os/core/config.py` — añadir flag.
- `backend/src/cognitive_os/deepagents/failure_postmortem.py:280` — gate
  por flag.
- `frontend/app/views/MemoryView.tsx` — badge "auto-promovido".
- Tests: matriz del flag on/off.

**Criterio de aceptación:** los docs principales y el código describen
el MISMO comportamiento. Una persona nueva que lea README + SKILLS_MEMORY
+ LEARNING_PLAN no encuentra una sorpresa al leer `failure_postmortem.py`.

**Esfuerzo:** ~30 min (Opción B, mayormente docs).
**Prioridad:** 3.

---

### 3.3 P2 Medium — calidad de operación

#### AUDIT-2026-D — Telegram 37 comandos, matriz de tests incompleta

**Severidad:** P2
**Categoría:** Missing test
**Esfuerzo:** ~1 día (37 commands × 3-4 condiciones = ~110 tests parametrizados)

**Evidencia:**

- 37 decoradores `@command` en `telegram_bot.py` (verificado con `grep`).
- `test_telegram_bot.py` cubre: approvals/dispatch/cascade, openshell
  resolver, prefix resolver, maps separator, calendar blocked, drive
  query required, mail disabled, sandbox disabled, capabilities,
  plain/reset/threads, agent_self.
- **No hay matriz** `cada comando × {auth-ok, auth-deny, backend-ok,
  backend-500, flag-disabled, happy-path-mocked}`.

**Por qué P2 y no P1:** los comandos comparten el service layer del
REST, que sí está cubierto. El gap es que un cambio en un endpoint puede
romper el comando Telegram sin que el test lo detecte, o un mensaje de
error puede ser confuso. En zero-friction esto debilita "el operador no
debe adivinar qué está mal" — si un comando falla, el mensaje tiene que
ser preciso.

**Cómo lo resolvería:**

```python
ALL_COMMANDS = ["start", "help", "health", "stats", "config", "agents",
                "skills", "memory", "consolidate", "jobs", "job", "cancel",
                "approvals", "approve", "reject", "threads", "chat", "reset",
                "ingest", "tasks", "task", "done", "notes", "note",
                "gmaildigest", "runs", "maps", "calendar", "freebusy",
                "drive", "documents", "audit", "mail", "research",
                "codebuild", "sandbox", "capabilities"]

@pytest.mark.parametrize("cmd", ALL_COMMANDS)
def test_command_unauthorized_user_gets_forbidden(cmd, ...): ...

@pytest.mark.parametrize("cmd,flag", FLAG_GATED_COMMANDS)
def test_command_reports_disabled_when_flag_off(cmd, flag, ...): ...

@pytest.mark.parametrize("cmd,error_class", BACKEND_DEPENDENCIES)
def test_command_reports_useful_message_on_backend_failure(...): ...
```

**Prioridad:** 4.

---

#### AUDIT-2026-E — Suite hermético no prueba integraciones reales (LLM, Google, GoDaddy, Telegram API, Kimi, mail SMTP)

**Severidad:** P2
**Categoría:** Integration fragility / Missing test
**Estado:** Reconocido en `CURRENT_STATE.md` líneas 112-115

**Evidencia:**

- `backend/tests/conftest.py:24-48,214-235` bloquea factories LLM reales.
- 0 tests con marker `live_readonly` o similar.
- `pyproject.toml` define markers `integration`/`slow` que están
  deseleccionados por defecto.
- `CURRENT_STATE.md` línea 114-116 lo reconoce explícitamente.

**Por qué P2:** el modelo zero-friction acepta este gap explícitamente
(el doc canónico lo advierte). El gap es real pero documentado.

**Cómo lo resolvería:** carril `pytest -m live_readonly` con opt-in
`LIVE_TESTS_ENABLED=1`. El carril vigente contiene 8 smokes:

| Test | Qué prueba | Coste estimado |
|---|---|---|
| `test_live_llm_minimal.py` | `gpt-5.5` con prompt "ping" y `max_tokens=1` | ~$0.001 / run |
| `test_live_google_oauth_status.py` | `oauth_status` + `freebusy` readonly | $0 |
| `test_live_godaddy_get_domains.py` | `GET /v1/domains` readonly | $0 |
| `test_live_smtp_ehlo.py` | `EHLO` IMAP/SMTP sin enviar | $0 |
| `test_live_telegram_get_me.py` | Telegram `getMe` (no envía) | $0 |
| `test_live_kimi_status.py` | Kimi WebBridge daemon ping | $0 |
| `test_live_mcp_list_tools.py` | Por cada server MCP, `list_tools()` | $0 |

Todos con redacción de secretos en logs, budget caps explícitos, nunca
writes. Script `scripts/full-qa-live.sh` opcional.

**Prioridad:** 5.

---

#### AUDIT-2026-F — Backlog de approvals/jobs zombie/dispatch zombies sin visibilidad en `/health/dashboard`

**Severidad:** P2
**Categoría:** Observability gap

**Evidencia:**

- `workers/tasks.py:682,716,1034` definen 3 reapers
  (`reap_stale_approvals`, `reap_stuck_action_requests`,
  `reap_stale_running_jobs`).
- `core/health.py` NO expone `approvals_pending_count`,
  `jobs_stale_count`, `action_requests_stuck_count`, ni
  `beat_lag_seconds`.
- Si un beat se atrasa o un reaper no corre (worker muerto, broker
  caído transitorio), el backlog crece silenciosamente.

**Por qué P2:** mismo principio "el operador no debe adivinar". Auditoría
previa midió 100 approvals pendientes sin detección. El reaper existe
pero no hay alarma temprana.

**Cómo lo resolvería:**

`backend/src/cognitive_os/core/health.py`:

```python
async def _check_operational_backlog() -> ComponentHealth:
    THRESHOLDS = {
        "approvals_pending": 20,
        "jobs_stale_hours": 12,
        "action_requests_stuck": 5,
        "beat_lag_minutes": 30,
    }
    async with async_session_factory() as session:
        approvals_pending = await session.scalar(
            select(func.count(HumanApproval.id)).where(HumanApproval.status == "pending")
        )
        jobs_stale = await session.scalar(
            select(func.count(Job.id)).where(
                Job.status.in_(("queued", "running")),
                Job.updated_at < datetime.now(UTC) - timedelta(hours=THRESHOLDS["jobs_stale_hours"])
            )
        )
        action_requests_stuck = await session.scalar(...)
        last_beat = await session.scalar(select(func.max(JobEvent.created_at))
                                          .where(JobEvent.event_type.like("reap_%")))
        beat_lag_minutes = (datetime.now(UTC) - last_beat).total_seconds() / 60 if last_beat else None

    breached = (approvals_pending > THRESHOLDS["approvals_pending"]
                or jobs_stale > 0
                or action_requests_stuck > 0
                or (beat_lag_minutes is not None and beat_lag_minutes > THRESHOLDS["beat_lag_minutes"]))

    return ComponentHealth(
        name="operational_backlog",
        status="degraded" if breached else "ok",
        detail=...,
        metadata={
            "approvals_pending": approvals_pending,
            "jobs_stale": jobs_stale,
            "action_requests_stuck": action_requests_stuck,
            "beat_lag_minutes": beat_lag_minutes,
        }
    )
```

Frontend `HealthView.tsx` + `DashboardView.tsx`: tile nuevo con drill-down a `/approvals` y `/jobs`.

**Prioridad:** 6.

---

### 3.4 P3 Low / Info — pulido

#### AUDIT-2026-G — `README.md` y `USER_GUIDE.md` conservan conteos antiguos (712/800/685 passed; 143/130 endpoints; 22 Celery tasks)

Los docs nuevos (`CURRENT_STATE.md`, `ARCHITECTURE.md`,
`ACCEPTANCE_CHECKLIST.md`, `PROJECT_GUIDE.md`) ya tienen los conteos
correctos (848/146/23). Sólo el `README.md` y la cabecera de `USER_GUIDE.md`
mezclan varias snapshots históricas (`Fase 74`, `Fase 78-81`, `Fase 82`)
cada una con sus números.

**Fix sugerido:** `scripts/sync_doc_counts.py` que extrae conteos de:
- `git ls-files` para `frontend/app/views/*.tsx`.
- `grep -cE "@app\." backend/src/cognitive_os/api/app.py` para endpoints.
- `grep -cE "name=\"cognitive_os\\." backend/src/cognitive_os/workers/tasks.py` para Celery.
- `ls backend/alembic/versions/*.py | wc -l` para migraciones.
- `pytest --collect-only -q | tail -1` para tests.

Y actualiza marcadores `<!-- AUTO:endpoint_count -->`, `<!-- AUTO:celery_count -->`, etc. en `README.md` + `USER_GUIDE.md`.

**Prioridad:** 7.

#### AUDIT-2026-H — `docker compose config` sin `--env-file` no falla por variables vacías

**Fix:** wrapper script `scripts/dev_up.sh` con `set -u` + validación
previa de variables requeridas. Documentar el comando único correcto
en `RUNBOOK.md`.

**Prioridad:** 8.

#### AUDIT-2026-I — Archivos de bitácora viva trackeados: `findings.md` (3200 LOC), `progress.md` (2850 LOC), `task_plan.md` (1725 LOC), `conversacion_recuperada_codex_claude.md`, `sesion_14_15_mayo_completa.md`

7775+ LOC de notas tracked en `git`. El propio README los declara "no
son documentación permanente" pero siguen versionados.

**Fix:** mover a `docs/audits/archive/` o `.cognitive-os-notes/` (en
`.gitignore`). Mantener una versión consolidada en el repo.

**Prioridad:** 9.

#### AUDIT-2026-J — `cognitive-os-backup-20260511-224814/` y `cognitive-os-snapshot-2026-05-11/` son árboles paralelos en el workspace

`find` y `grep` recursivos pueden mezclar código de backup con código
vivo (verifiqué que mi propio inventario los detectó).

**Fix:** moverlos fuera del workspace (a `~/.cognitive-os-backups/`) o
añadir a `.gitignore` global del usuario / excludes del IDE. Actualizar
README líneas 275-280 con la nueva ubicación.

**Prioridad:** 10.

#### AUDIT-2026-K — Snapshots históricos en el README acumulan ruido

`README.md:18-90` mezcla snapshots de F82, F78-81, F74, F66, F65, F64,
F59-63, F50-58, F42, F41, F40, F39 — cada uno con sus conteos. Para una
persona nueva es ruido (la línea de tiempo no debería confundirse con el
estado actual).

**Fix:** mover historia detallada a `docs/audits/archive/PHASE_HISTORY.md`.
Dejar README con sólo el snapshot vigente (basado en `CURRENT_STATE.md`).

**Prioridad:** 11.

#### AUDIT-2026-L — JWT en `localStorage` (riesgo XSS asumido explícitamente)

`FRONTEND_ARCHITECTURE.md` §8 declara: *"JWT en localStorage bajo
cogos.token. Riesgo XSS asumido como aceptable en un cockpit local
single-operator sin third-party scripts"*.

**No es bug** — es decisión consciente. Informativo.

#### AUDIT-2026-M — Rate limit `memory` backend es single-replica

`core/rate_limit.py` documenta que `memory` (default) sólo funciona con
un solo proceso. `RUNBOOK.md` §"Riesgos residuales conocidos" lo
documenta.

**No es bug** — decisión documentada.

---

## 4. Subsistemas — clasificación final

| Subsistema | Estado | Notas |
|---|---|---|
| Arranque local | ✅ Comercial | Launchers con `flock` + preflight + rotación de logs. |
| Backend API | ✅ Sólido | 848 pytest, mypy 0 issues. |
| Frontend | ✅ Sólido | Lint+build verdes; Playwright 22 (doc); defensive `asArray`. |
| Auth JWT | ✅ OK para single-operator | HS256 hand-rolled, four-eyes opcional, admin role para LangSmith + Memory mutations. |
| **Health dashboard** | ⚠️ **AUDIT-2026-B** | Configured = ok engaña. |
| Postgres/Alembic | ✅ Sólido | head limpio, `alembic check` sin drift. |
| Redis/Celery | ✅ Sólido | dispatch_state atómico, 3 reapers, broker failure controlado. |
| Weaviate/RAG | ✅ Wiring sólido | RAG real no probado vivo (AUDIT-2026-E). |
| Neo4j | ✅ Wiring sólido | Idem. |
| LangGraph router | ✅ Sólido + fallback determinista | LLM real no probado (AUDIT-2026-E). |
| DeepAgents | ✅ Sólido (21 tools tipadas) | Idem. |
| Document ingest | ✅ Sólido | PDF corrupto no probado vivo (AUDIT-2026-E). |
| Document analysis legal | ✅ Sólido | Docs reales no probados (AUDIT-2026-E). |
| Research orchestrator | ✅ Sólido | LLM real no probado (AUDIT-2026-E). |
| **Memory + learning plan** | ⚠️ **AUDIT-2026-C** | Contradicción interna §1 vs §3.4. |
| Action Plane | ✅ Sólido | Idempotencia atómica, JobEvent broker-failure, reapers. |
| HumanApproval | ✅ Sólido | Four-eyes opcional, cascade Job/ActionRequest, AuditEvent. |
| AuditEvent / JobEvent | ✅ Sólido | Cobertura asimétrica en mail send (intencional, documentado). |
| Mail | ✅ Sólido | Contrato lectura-only verificado. UI sin botón Enviar. |
| Google Ops | ✅ Wiring sólido | Writes reales no probados (AUDIT-2026-E). |
| GoDaddy | ✅ Sólido | 2 flags duros + allow-list de dominios. |
| Browser (Kimi/headless) | ✅ Diseño correcto | No probado vivo (AUDIT-2026-E). |
| Computer actions | ✅ Sólido | Preview obligatorio, allow-list. |
| Office docs | ✅ Sólido | Render real no auditado (AUDIT-2026-E). |
| Code Director | ✅ Wiring sólido | Adapters CLI no ejercitados con LLM real (AUDIT-2026-E). |
| **Telegram** | ❌ **AUDIT-2026-A** + ⚠️ AUDIT-2026-D | Auth fail-open con allowlist vacía. |
| Tests backend | ✅ Hermético sólido | 848 passed, 0 mypy issues. |
| Tests frontend | ✅ E2E 31 passed | Lint+build verdes. |
| **Docs** | ⚠️ **AUDIT-2026-C** + 2026-G/K | Contradicción interna + drift de conteos viejos en README. |
| Configuración | ✅ Sólida (100+ vars) | `SETTINGS_REGISTRY_TABLE.md` autogenerado. |
| Seguridad operativa | ✅ Coherente con postura del producto | Excepción Mail bien cementada en docs y código. |

---

## 5. Plan de acción completo (5 oleadas, con estimaciones)

### OLEADA 0 — Safety freeze (5 min)

**Objetivo:** dejar el repo limpio para empezar reparaciones.

**Tareas:**

1. Decidir el incidente `tsconfig.json` modificado por mi sesión de build
   (§9). Recomendación: `git checkout cognitive-os/frontend/tsconfig.json`.
2. Crear branch `repair/audit-2026-wave1` desde
   `main`.
3. Confirmar que `.env` real está backupeado fuera del repo.
4. Confirmar `OPERATOR_PROFILE`, `LOCAL_AUTONOMY_MODE` y especialmente
   **`TELEGRAM_AUTHORIZED_USER_IDS`** (poblado o vacío).

**Criterio:** `git status --short` limpio (salvo el informe).

---

### OLEADA 1 — P0 (AUDIT-2026-A) — 30-45 min

**Objetivo:** cerrar el único hallazgo bloqueante.

**Cambios en orden:**

1. `backend/src/cognitive_os/integrations/telegram_bot.py:195` — quitar
   `self.allowed_user_ids and`.
2. `backend/src/cognitive_os/integrations/telegram_bot.py` bootstrap
   (línea ~1613) — `if not allowed: raise SystemExit(2)`.
3. `backend/src/cognitive_os/core/config.py` — `@model_validator(mode="after")`
   que rechace combinación `telegram_enabled=true + allowlist=[]` cuando
   `environment == "production"`.
4. `backend/tests/test_telegram_bot.py` — 3 tests nuevos (detallados en
   §3.1).
5. `cognitive-os/.env.example:187` — placeholder más explícito con
   comentario.

**Validación:**

- `cd backend && uv run pytest tests/test_telegram_bot.py -q` → +3 tests
  passed.
- `cd backend && uv run pytest -q` → 851 passed.
- `cd backend && uv run mypy src` → 0 issues.
- `cd backend && uv run ruff check . && uv run ruff format --check .` → verdes.
- Smoke manual (5 min): `TELEGRAM_AUTHORIZED_USER_IDS=` vacío +
  `TELEGRAM_ENABLED=true` + bot token de prueba → debe `SystemExit(2)` al
  arrancar.

**Commit:** `fix(audit): AUDIT-2026-A Telegram dispatch fail-closed with empty allowlist`.

**Pedir AUTORIZACIÓN antes de OLEADA 2.**

---

### OLEADA 2 — P1 (AUDIT-2026-B y AUDIT-2026-C) — 2-3 horas

**Objetivo:** cerrar los dos hallazgos que afectan "fallos visibles" y
coherencia documental.

#### Sub-oleada 2.1 — Health configured vs verified (~30 min)

1. `backend/src/cognitive_os/core/health.py:106-113` — recompute
   `overall` distinguiendo `VERIFIED_STATES` de `CONFIGURED_STATES`.
2. `frontend/app/views/HealthView.tsx` — badge "configured" ámbar.
3. `frontend/app/views/DashboardView.tsx` — mismo tratamiento.
4. Tests:
   - `test_overall_with_only_configured_returns_configured`.
   - `test_overall_with_one_degraded_returns_degraded`.
   - `test_overall_with_all_verified_returns_ok`.
5. Update `core/health.py` docstrings + `docs/RUNBOOK.md` §Health.

**Commit:** `fix(audit): AUDIT-2026-B health distinguishes configured from verified`.

#### Sub-oleada 2.2 — Learning plan contradiction (Opción B, ~30 min)

1. `docs/AGENT_LEARNING_PLAN.md` §1 — añadir excepción.
2. `docs/DEEPAGENTS_SKILLS_MEMORY.md` línea 47 — explicitar.
3. `cognitive-os/README.md` líneas 33-35 — matizar.
4. `backend/src/cognitive_os/core/config.py` — añadir flag
   `failure_postmortem_auto_promote_enabled` (default `true`).
5. `backend/src/cognitive_os/deepagents/failure_postmortem.py:280` —
   gate por flag.
6. `frontend/app/views/MemoryView.tsx` — badge "auto-promovido" distinto.
7. Tests:
   - `test_auto_promote_creates_active_when_flag_on`.
   - `test_auto_promote_creates_pending_proposal_when_flag_off`.

**Commit:** `fix(audit): AUDIT-2026-C document learning plan exception + kill switch`.

#### Sub-oleada 2.3 — Probe live opcional (~1.5 h, opcional pero recomendado)

- `HEALTH_LIVE_VERIFICATION_ENABLED` flag (default `false`).
- Endpoint `POST /health/verify` (admin) con caché 15 min.
- Beat opcional `health-verify` cada 15 min.

**Commit:** `feat(audit): AUDIT-2026-B add opt-in live verification`.

**Pedir AUTORIZACIÓN antes de OLEADA 3.**

---

### OLEADA 3 — P2 (AUDIT-2026-D, E, F) — 1 día

**Objetivo:** elevar calidad de tests y observabilidad operativa.

1. **AUDIT-2026-D** — matriz parametrizada de 37 commands × 3 condiciones
   = ~111 tests en `test_telegram_bot.py`.

2. **AUDIT-2026-E** — carril `pytest -m live_readonly`:
   - `tests/live/` con 8 smokes.
   - Marker en `pyproject.toml`.
   - `scripts/full-qa-live.sh` opt-in.
   - `RUNBOOK.md` §"Smokes live (opt-in)".

3. **AUDIT-2026-F** — `_check_operational_backlog` en `core/health.py`:
   - Cuenta approvals pendientes, jobs zombie, action_requests stuck,
     beat lag.
   - Tile nuevo en `/health/dashboard`.
   - `HealthView.tsx` + `DashboardView.tsx` con drill-down.

**Pedir AUTORIZACIÓN antes de OLEADA 4.**

---

### OLEADA 4 — P3 (AUDIT-2026-G, H, I, J, K) — 4-6 horas

**Objetivo:** pulido final / repo hygiene.

1. **AUDIT-2026-G/K** — `scripts/sync_doc_counts.py` con marcadores
   `<!-- AUTO:* -->` en README/USER_GUIDE. Mover historia detallada a
   `docs/audits/archive/PHASE_HISTORY.md`.

2. **AUDIT-2026-H** — `scripts/dev_up.sh` con `set -u` + validación
   previa.

3. **AUDIT-2026-I** — mover `findings.md`, `progress.md`,
   `task_plan.md`, `conversacion_recuperada_*.md`, `sesion_14_15_*.md` a
   `docs/audits/archive/`.

4. **AUDIT-2026-J** — mover `cognitive-os-backup-20260511-224814/` y
   `cognitive-os-snapshot-2026-05-11/` fuera del workspace.

**Validación final:** `bash scripts/full-qa.sh` verde + `bash scripts/stress-qa.sh 5`
verde + `npx playwright test` verde.

---

### OLEADA 5 (opcional, futura) — Live verification completa

- Implementar `POST /health/verify` con probes live + cache 15 min (parte
  2 de AUDIT-2026-B si no se hizo en Oleada 2).
- Beat opcional cada 15 min.
- UI con badge "verified Xm ago" por componente.

---

## 6. Criterios de aceptación (contra la propia definición del producto)

Marco los criterios contra
`ZERO_FRICTION_OPERATING_MODEL.md` §"Qué significa grado comercial en este PC":

| Criterio del producto | Pre-O1 | Post-O1 | Post-O2 | Post-O4 |
|---|---|---|---|---|
| Arranque reproducible | ✅ | ✅ | ✅ | ✅ |
| Stack local diagnosticable | ⚠️ | ⚠️ | ✅ | ✅ |
| Jobs no se pierden silenciosamente | ✅ | ✅ | ✅ | ✅ |
| UI no miente sobre lo que hace | ✅ | ✅ | ✅ | ✅ |
| Mail cumple contrato | ✅ | ✅ | ✅ | ✅ |
| Frontend no deshidratado tras QA | ✅ | ✅ | ✅ | ✅ |
| Tests/build/lint/mypy/Alembic/E2E verdes | ✅ | ✅ | ✅ | ✅ |
| Fallos de credenciales visibles | ⚠️ | ⚠️ | ✅ | ✅ |
| Operador no adivina qué está mal | ⚠️ | ⚠️ | ⚠️ (post-O2 health ok, post-O3 backlog visible) | ✅ |
| **Auth externa fail-closed** | ❌ | ✅ | ✅ | ✅ |
| **Docs internas coherentes** | ❌ | ❌ | ✅ | ✅ |

- **Post-Oleada 1:** aceptable para uso real con riesgo conocido y mitigado.
- **Post-Oleada 2:** cumple los 9 criterios declarados del producto.
- **Post-Oleada 4:** producto pulido al nivel "qué le dirías a un nuevo operador".

---

## 7. Prompt de reparación — NO EJECUTAR HASTA AUTORIZACIÓN DE DIEGO

```text
Actuá como REPAIR ENGINEER de Cognitive OS. Tu rol es ejecutar el plan
documentado en `docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md`
(versión 2026-05-22 reescrita) por oleadas, sin saltar ninguna.

REGLAS NO NEGOCIABLES:
1. NO empezar sin que Diego escriba literalmente "AUTORIZO OLEADA <N>".
2. Reparar SOLO Oleada 0 y Oleada 1 en el primer ciclo. NO mezclar oleadas.
3. Cambios pequeños y atómicos. Un commit por hallazgo, con mensaje
   `fix(audit): AUDIT-2026-<X> <descripcion corta>`.
4. Ejecutar `cd backend && uv run pytest -q` después de CADA edición.
   Si rojo, detenerse y reportar.
5. Mostrar diff antes de cada commit.
6. NO mezclar refactors con fixes. NO renombrar variables que no necesiten.
7. NO tocar docs antes de que el código esté verde para esa oleada
   (excepto Oleada 2.2 que es deliberadamente docs).
8. NO tocar integraciones externas reales (LLM, Google, GoDaddy, Telegram
   API). Sólo lectura de status/código.
9. NO modificar `.env` ni `.env.local` (sólo `.env.example` en Oleada 1).
10. Pedir AUTORIZACIÓN explícita antes de pasar de una oleada a la siguiente.
11. Si aparece un comportamiento inesperado (test que antes pasaba y
    ahora falla, archivo modificado que no estaba en el plan), detenerse
    y reportar antes de seguir.
12. NO ejecutar `npm install`, `uv sync --upgrade`, ni cambios de lockfile.

==== OLEADA 0 — Safety freeze ====

Tareas:
- Confirmar `git status --short` limpio (salvo el informe + tsconfig.json
  documentado como incidente §9).
- Decidir si revertís `tsconfig.json`: recomendación
  `git checkout cognitive-os/frontend/tsconfig.json`.
- Crear branch `repair/audit-2026-wave1`.
- Reportar a Diego el estado de:
  - OPERATOR_PROFILE
  - LOCAL_AUTONOMY_MODE
  - TELEGRAM_AUTHORIZED_USER_IDS (no su valor, sólo "vacío" o "poblado")
- Pedir "AUTORIZO OLEADA 1".

==== OLEADA 1 — AUDIT-2026-A (Telegram fail-closed) ====

Cambios en orden:

1) `backend/src/cognitive_os/integrations/telegram_bot.py` línea 195:
   Cambiar:
     if self.allowed_user_ids and user_id not in self.allowed_user_ids:
   a:
     if user_id not in self.allowed_user_ids:

2) En el bootstrap del main() o run_forever() del mismo archivo
   (línea ~1613):
   Después de `allowed = set(settings.telegram_authorized_user_ids)`
   reemplazar el bloque `if not allowed: logger.warning(...)` por:
     if not allowed:
         logger.error(
             "TELEGRAM_AUTHORIZED_USER_IDS vacío con bot configurado. "
             "Rehúso arrancar el bot — pegale tu user_id antes de habilitar."
         )
         raise SystemExit(2)

3) `backend/src/cognitive_os/core/config.py`:
   Añadir un `@model_validator(mode="after")` después de los validators
   existentes:
     def reject_telegram_bot_without_allowlist(self) -> Self:
         if self.environment == "production" and self.telegram_enabled:
             if not self.telegram_authorized_user_ids:
                 msg = "TELEGRAM_ENABLED=true requires TELEGRAM_AUTHORIZED_USER_IDS"
                 raise ValueError(msg)
         return self

4) `backend/tests/test_telegram_bot.py` — añadir 3 tests al final del archivo:
     def test_dispatch_rejects_with_empty_allowed_user_ids(monkeypatch): ...
     def test_dispatch_rejects_unknown_user_with_populated_allowlist(monkeypatch): ...
     def test_run_forever_refuses_to_start_with_token_and_empty_allowlist(monkeypatch): ...
   (cuerpos completos en §3.1 del informe)

5) `cognitive-os/.env.example` línea 187:
   Cambiar:
     TELEGRAM_AUTHORIZED_USER_IDS=
   a:
     TELEGRAM_AUTHORIZED_USER_IDS=  # obligatorio si TELEGRAM_ENABLED=true; obtenelo con @userinfobot

Validación obligatoria antes del commit:
- `cd backend && uv run pytest tests/test_telegram_bot.py -q` → +3 tests passed.
- `cd backend && uv run pytest -q` → 851 passed.
- `cd backend && uv run mypy src` → 0 issues.
- `cd backend && uv run ruff check .` → All checks passed.
- `cd backend && uv run ruff format --check .` → already formatted.

Commit con mensaje exacto:
  fix(audit): AUDIT-2026-A Telegram dispatch fail-closed with empty allowlist

Reportar a Diego:
- Diff aplicado (los 5 archivos cambiados).
- Resultados de pytest/mypy/ruff.
- Pedir "AUTORIZO OLEADA 2" si Diego quiere continuar.

NO seguir más allá sin autorización explícita.
```

---

## 8. Estimación de esfuerzo total

| Oleada | Esfuerzo | Riesgo | Resultado |
|---|---|---|---|
| 0 — Safety freeze | 5 min | 0 | Branch limpio para empezar |
| 1 — AUDIT-2026-A | 30-45 min | Bajo | Sistema firmable como responsable técnico |
| 2 — AUDIT-2026-B+C | 2-3 h | Bajo (Opción B mayormente docs) | Cumple los 9 criterios del producto |
| 3 — AUDIT-2026-D+E+F | 1 día | Medio (matriz Telegram grande) | Calidad operativa elevada |
| 4 — AUDIT-2026-G+H+I+J+K | 4-6 h | Bajo (mayormente docs/hygiene) | Pulido para hand-off |
| 5 (opcional) — Live verify completa | 1-2 días | Medio | Producto sobresaliente |

**Mínimo absoluto para "responsable técnico aceptaría":** Oleadas 0+1 = **~45 min**.
**Para "cumple su propia definición de grado comercial":** Oleadas 0-2 = **~3-4 h**.
**Para "pulido nivel hand-off":** Oleadas 0-4 = **~2-3 días**.

---

## 9. Incidente de auditoría

Durante el gate de build frontend ejecuté
`NEXT_DIST_DIR=.next-audit npm run build`. Next.js detectó el dist dir
custom y añadió 2 líneas a `cognitive-os/frontend/tsconfig.json`
automáticamente:

```diff
-    ".next-qa/dev/types/**/*.ts"
+    ".next-qa/dev/types/**/*.ts",
+    ".next-audit/types/**/*.ts",
+    ".next-audit/dev/types/**/*.ts"
```

**Estado actual:**
```
 M cognitive-os/docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md   <- este informe
 M cognitive-os/frontend/tsconfig.json                            <- incidente
```

**No revertí el cambio** conforme a la regla 25 del prompt de auditoría
original ("si aparece cualquier cambio tracked que no sea el informe de
auditoría, debes declararlo como incidente").

**Causa raíz:** elegí nombre custom `.next-audit` en vez de usar
`.next-qa` que ya estaba en el tsconfig (porque lo usa `full-qa.sh`).
Si hubiera usado `.next-qa` no habría side-effect.

**Decisión propuesta a Diego:**
- `git checkout cognitive-os/frontend/tsconfig.json` para revertir.
- En Oleada 4 añadir a `scripts/full-qa.sh`:
  ```bash
  if ! git diff --exit-code -- cognitive-os/frontend/tsconfig.json; then
      echo "FAIL: tsconfig.json fue modificado durante el build" >&2
      exit 1
  fi
  ```

---

## 10. Comparación con el audit anterior

| Hallazgo del audit anterior | Re-evaluación |
|---|---|
| OP47-001 Telegram empty allowlist accepts all (P0) | **MANTENIDO** → AUDIT-2026-A P0 |
| OP47-002 dedicated_local+full auto-aprueba irreversibles (P0) | **CERRADO** — feature declarada en ZERO_FRICTION_OPERATING_MODEL.md |
| OP47-003 Health configured=ok (P1) | **MANTENIDO** → AUDIT-2026-B P1 |
| OP47-004 Learning auto-promote (P1) | **REDUCIDO a docs drift interno** → AUDIT-2026-C P1 (Opción B recomendada) |
| OP47-005 Kimi/MCP scope amplio (P1) | **CERRADO** — feature del PC dedicado |
| OP47-006 E2E no verificado (P1) | **CERRADO** — CURRENT_STATE.md confirma 31 passed |
| OP47-007 Integraciones no verified live (P1) | **REDUCIDO** → AUDIT-2026-E P2 |
| OP47-008 Mail send paralelo (P2) | **CERRADO** — CURRENT_STATE.md formaliza el contrato actual; UI sin botón Enviar |
| OP47-009 Telegram paridad tests (P2) | **MANTENIDO** → AUDIT-2026-D P2 |
| OP47-010 Docs drift conteos (P2) | **REDUCIDO** → AUDIT-2026-G P3 (docs nuevos ya alineados) |
| OP47-011 Suite no real (P2) | Merged → AUDIT-2026-E P2 |
| OP47-012 OpenHarness FULL_AUTO (P2) | **CERRADO** — opt-in declarado, off por default |
| OP47-013 docker compose env-file (P2) | **REDUCIDO** → AUDIT-2026-H P3 |
| OP47-014 Backlog visibility (P2) | **MANTENIDO** → AUDIT-2026-F P2 |
| OP47-015 Conteos drift (P3) | Merged → AUDIT-2026-G |
| OP47-016 Archivos huérfanos (P4) | **MANTENIDO** → AUDIT-2026-I P3 |

**Resumen:** 5 hallazgos previos cerrados por ser features documentadas;
4 mantenidos con misma severidad; 4 reducidos a severidad más baja; 1
hallazgo nuevo (AUDIT-2026-C es contradicción interna de doc que no
había detectado antes).

---

## 11. Declaración del auditor

### 11.1 ¿Aceptaría ser responsable técnico de este sistema en su estado actual?

**Aún no, pero casi.** Aceptaría **inmediatamente después** de cerrar
AUDIT-2026-A (Oleada 1, ~45 min). Aceptaría con orgullo después de cerrar
AUDIT-2026-B y AUDIT-2026-C (Oleada 2, ~3 horas adicionales).

### 11.2 Bajo qué condiciones lo aceptaría

- Oleada 1 cerrada (Telegram fail-closed verificable por test + smoke
  manual).
- Oleada 2 cerrada (health no miente, docs internas coherentes).
- El operador (Diego) entiende y firma la postura zero-friction declarada
  en `ZERO_FRICTION_OPERATING_MODEL.md`, **porque esa postura define los
  límites de mi responsabilidad** como responsable técnico. Si en el
  futuro el sistema sale del PC dedicado o gana usuarios, hay que mover
  a `OPERATOR_PROFILE=strict` y reauditar todo.

### 11.3 Las 5 reparaciones más importantes

1. **AUDIT-2026-A** — Telegram fail-closed (P0 bloqueante; ~45 min).
2. **AUDIT-2026-B** — Health distingue `configured` de `verified` (P1; ~2 h).
3. **AUDIT-2026-C** — Resolver contradicción interna del learning plan
   (P1, ~30 min Opción B).
4. **AUDIT-2026-E** — Carril `live_readonly` opt-in (P2; calidad
   operativa real).
5. **AUDIT-2026-F** — Health expone backlog de approvals/jobs/dispatch
   zombies (P2).

### 11.4 Las 5 pruebas más importantes que faltan

1. `test_dispatch_rejects_with_empty_allowed_user_ids` (cubre AUDIT-2026-A).
2. Matriz parametrizada de 37 commands Telegram × 3 condiciones (cubre
   AUDIT-2026-D).
3. Live readonly suite (LLM minimal, Google OAuth status, SMTP EHLO,
   Telegram getMe, Kimi status, MCP list_tools, GoDaddy GET) — cubre
   AUDIT-2026-E.
4. Tests del `_check_operational_backlog` de health (cubre AUDIT-2026-F).
5. Tests del flag `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` on/off
   (cubre AUDIT-2026-C Opción B).

### 11.5 Qué parte del sistema me parece más peligrosa

El **bot de Telegram con allowlist vacía**. Es la única puerta externa
autenticada del sistema y la lógica falla abierta. Es el bug clásico de
"warning vs enforcement" donde el warning del log dice una cosa y el
código hace otra. La defensa-en-profundidad detrás (`AGENT_SELF.md`
declara "single-operator, bound to 127.0.0.1") asume que la única
excepción —Telegram— está bien auteniticada, pero en realidad falla
abierta cuando la allowlist está vacía. El plantilla `.env.example`
viene con el campo vacío, así que el escenario de fallo no es
hipotético: es lo que pasa si el operador olvida pegar su `user_id`.

### 11.6 Qué parte del sistema me parece más sólida

La capa **Postgres + Alembic + ActionRequest con dispatch idempotente**.
Las 20 migraciones limpias sin drift, el `dispatch_state=submitting|submitted|failed`
reservado atómicamente con `SELECT ... FOR UPDATE`, los `JobEvent
action_request_dispatch_submitted/failed`, los 3 reapers, el
short-circuit del worker si AR ya está `running`. Es ingeniería de
calidad poco común en sistemas hechos con velocidad alta. Y se sostiene
sola — no depende de approvals manuales para ser correcta.

### 11.7 Qué decisión debe tomar Diego antes de autorizar reparaciones

**Decisión 1 — Incidente `tsconfig.json` (§9).** Revertir o aceptar.
**Recomendación: revertir** (`git checkout`).

**Decisión 2 — AUDIT-2026-C, Opción A o B.**
- A = honrar §1 "cero auto-deploy", eliminar el auto-promote de Fase D.
- B = honrar §3.4 (la realidad), actualizar docs para reconocer la
  excepción + añadir kill switch.
**Recomendación: Opción B** (docs-mayor, mantiene comportamiento
estadísticamente defendible).

**Decisión 3 — Orden de las oleadas.** ¿De acuerdo con cerrar P0+P1
primero (Oleadas 1-2)? *Recomendación: orden propuesto.*

**Decisión 4 — Live readonly carril (AUDIT-2026-E).** ¿Implementarlo en
Oleada 3 o aceptarlo como gap reconocido pero no priorizable hoy?
*Recomendación: implementar después de Oleada 2 — sin esto, una rotación
de credenciales LLM/Google puede pasar inadvertida.*

**Decisión 5 — Repo hygiene (P3).** ¿Aceptás mover
`findings.md`/`progress.md`/`task_plan.md` y los backups paralelos fuera
de tracked? *Recomendación: sí; baja ruido para futuros operadores/agentes.*

---

**Recomendación final del auditor: autorizá Oleada 0 + Oleada 1 sin
demora.** Son 45 min para cerrar el único hallazgo P0 real. Después,
decidí entre seguir con Oleada 2 (cierra el resto de criterios del
producto en 2-3 h adicionales) o pausar.

Las Oleadas 3 y 4 son mejoras de calidad valiosas pero no bloqueantes.
La Oleada 5 (live verify completa) es opcional y subiría el producto
de "grado comercial según su propia definición" a "grado comercial
incluso bajo escrutinio externo".

---

*Fin del audit. Cualquier afirmación de este documento puede verificarse
en los paths/líneas citados o reejecutando los comandos indicados.
Versión 2026-05-22 reescrita con lectura profunda de los 22 markdowns
activos del proyecto y verificación de gates QA esta sesión.*
