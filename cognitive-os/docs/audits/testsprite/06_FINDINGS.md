# 06 · Findings — TestSprite Audit 2026-05-23

Branch: `codex/commercial-zero-friction-hardening`, HEAD `9b22f77`.

## Resumen ejecutivo

Tras leer los 22 markdowns canónicos, descubrir el código real (147
endpoints, 23 tareas Celery, 5 colas, 20 vistas, 37 commands Telegram, 18
componentes health, 5 MCP servers, 20 migraciones), correr baseline
`full-qa.sh` (944 passed) y `npx playwright test` (31 passed con JWT
exportado), y verificar TestSprite MCP operativo (Diego Manzur, Starter
plan, 520 credits):

- **0 hallazgos P0** que comprometan funcionamiento, datos o el contrato
  mail/Telegram.
- **0 hallazgos P1** funcionales adicionales a los ya cerrados en
  AUDIT-2026-A..K.
- Hallazgos **P2/P3** orientados a **reducir fricción operativa**
  (consistente con `ZERO_FRICTION_OPERATING_MODEL.md`).

El sistema cumple los 9 criterios de "grado comercial local-first" de
`ZERO_FRICTION_OPERATING_MODEL.md` ya marcados como verde en el audit
previo. Las mejoras propuestas eliminan **última milla de fricción** sin
romper trazabilidad, idempotencia ni el contrato mail.

---

## Hallazgos

### TS-ZF-20260523-001 · Playwright Runner Friction (P2)

- **Superficie:** `frontend/tests/e2e/_helpers.ts` + `docs/qa/RUNBOOK.md`
- **Contrato esperado (zero-friction):** ejecutar `npx playwright test` en
  `dedicated_local/full` sin pasos manuales debería funcionar.
- **Comportamiento real:** `_helpers.ts::readJwt()` lanza
  `Error: COGOS_JWT env var is missing` si la env var no está exportada.
  El operador (o un agente Claude) intenta `npx playwright test`, recibe
  19/31 fallos, y debe leer el runbook para descubrir el comando manual
  `uv run python -c "from cognitive_os.core.auth import create_access_token"`.
- **Evidencia:** primera corrida del baseline → 19 fallos con mensaje
  `COGOS_JWT env var is missing`. Segunda corrida con
  `export COGOS_JWT=$(curl POST /auth/local-token)` → 31 passed.
- **Reproducción:**
  ```bash
  cd cognitive-os/frontend
  unset COGOS_JWT
  COGOS_API_BASE=http://127.0.0.1:8000 COGOS_BASE_URL=http://localhost:3001 \
    npx playwright test
  # 19 failed, todos con readJwt() lanzando
  ```
- **Causa raíz:** comentario interno en `_helpers.ts` dice "deliberately do
  NOT mint the token from the test process" porque históricamente el mint
  requería Python interno. Pero en `dedicated_local/full` (postura
  actual), `POST /auth/local-token` mintea sin auth — el helper puede
  auto-mintear via HTTP fetch sin acoplar Python.
- **Impacto en cero fricción:** alto — el primer intento de cualquiera
  (operator, CI, agente nuevo) falla. El contrato `dedicated_local/full`
  garantiza que la mint sea sin fricción; la suite Playwright contradice
  ese contrato.
- **Fix recomendado:** en `readJwt()`, si `COGOS_JWT` no está y
  `COGOS_API_BASE` apunta a `localhost`/`127.0.0.1`, hacer
  `POST /auth/local-token` y reusar el token. Pruebas siguen hermeticas
  (el endpoint sólo existe en `dedicated_local/full`).
- **Test de regresión:** spec que ejecute `readJwt()` sin env var y
  verifique que devuelva un JWT decodificable; spec que valide que el JWT
  retornado es aceptado por `/system/info`.
- **Severidad:** **P2** — bloquea la "primera corrida" del runner local.
- **Estado:** abierto, fix en Fase 11.

### TS-ZF-20260523-002 · Runtime Binary Behind HEAD (P3)

- **Superficie:** `/system/info.git_commit` vs `git rev-parse HEAD`
- **Contrato esperado:** `/system/info.git_commit` debe coincidir con
  HEAD al momento de cualquier release o auditoría formal.
- **Comportamiento real:** `git_commit = 2c3cff6` (3 commits atrás de
  HEAD `9b22f77`). Los 3 commits intermedios incluyen:
  - `5953b40` — MCP parallel inventory + Ctrl/K capture phase.
  - `9b22f77` — sync doc state.
- **Evidencia:** `curl /system/info` → `"git_commit": "2c3cff6dfccf"`.
- **Causa raíz:** `uvicorn` (PID 106597) y `next-server` (PID 106787) se
  arrancaron antes del último merge. Python imports están en RAM; los
  cambios en `mcp_client.py`/`config.py` no están vigentes en el binario.
- **Impacto en cero fricción:** bajo — el efecto observable (5/5 MCP
  servers, 67 tools, `Ctrl+K` desde inputs) ya funciona en runtime; los
  fixes son optimización/test coverage. Pero declarar verdes los gates
  contra un binario que NO es HEAD es contrario a la disciplina del
  RUNBOOK.
- **Fix recomendado:** reiniciar `uvicorn` y `next start` antes del cierre
  del audit. Documentar en el FINAL_REMEDIATION_REPORT que el binario
  post-reinicio sí matchea HEAD.
- **Test de regresión:** ya existe la verificación visual
  `/system/info` en `regression-critical.spec.ts`; agregar assertion
  opcional `git_commit === git rev-parse HEAD` para CI.
- **Severidad:** **P3** — higiene de release, no funcional.
- **Estado:** abierto, fix en Fase 11.

### TS-ZF-20260523-003 · Doc Drift Histórico (P3)

- **Superficie:** `docs/qa/MAP.md`, `docs/qa/FINAL_AUDIT_REPORT.md`.
- **Contrato esperado:** referencias al snapshot canónico actual no deben
  contradecir números vigentes.
- **Comportamiento real:** ambos archivos contienen párrafos históricos
  con "17 componentes" y "16 Playwright tests" (fase 76), bajo un
  disclaimer "histórico". El snapshot vigente al inicio del archivo dice
  18 / 31. No es contradicción material pero puede confundir.
- **Fix recomendado:** en cada párrafo histórico, añadir nota:
  `> (Histórico Fase 76; el snapshot vigente arriba manda.)`. O extraer
  las secciones históricas a `docs/qa/history/`.
- **Severidad:** **P3** — cosmético.
- **Estado:** abierto, fix en Fase 11 si hay margen.

### TS-ZF-20260523-004 · Runbook Mintea con Python pero `/auth/local-token` es Más Simple (P3)

- **Superficie:** `docs/qa/RUNBOOK.md §2`, `docs/RUNBOOK.md`.
- **Contrato esperado:** la forma documentada de obtener JWT debe ser la
  más simple disponible para `dedicated_local/full`.
- **Comportamiento real:** RUNBOOK §2 documenta `uv run python -c "..."`,
  que requiere venv backend. Pero existe `POST /auth/local-token` que es
  un curl trivial sin Python.
- **Fix recomendado:** actualizar `docs/qa/RUNBOOK.md §2` con:
  ```bash
  JWT=$(curl -sX POST http://127.0.0.1:8000/auth/local-token \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
  ```
  Dejar el método Python como fallback para `strict`/`guarded`.
- **Severidad:** **P3** — documental, reduce fricción.
- **Estado:** abierto, fix en Fase 11.

### TS-ZF-20260523-005 · TestSprite Smoke Subset (P3 — observación)

- **Superficie:** TestSprite MCP plan generado.
- **Observación:** TestSprite generó **28 TC** que cubren navegación,
  Settings, mail read-only contract, command palette, JWT persistence,
  approval lifecycle, jobs empty-state. Los asserts son LLM-driven; no
  reemplazan Playwright pero validan UX desde un ángulo distinto.
- **Resultado de ejecución:** en curso al cierre del audit; se
  consolidará en `09_FINAL_REMEDIATION_REPORT.md`.
- **Severidad:** **N/A** — informativo.

---

## Severidades NO encontradas

- **P0:** ninguno. Mail respeta contract, Telegram fail-closed,
  dispatch idempotente, reapers operacionales, alembic check sin drift.
- **P1 funcional:** ninguno. Health honesto, MCP funcional, Action Plane
  con audit/idempotencia, Code Director bajo budget soft, learning con
  kill switch.
- **P2 funcional adicional al ya cerrado:** ninguno. Solo el de runner
  arriba.

---

## Falsos hallazgos descartados (no son bugs)

Los siguientes se considerarían "hallazgos" bajo una postura SaaS pero NO
lo son bajo `dedicated_local/full`:

- `/auth/local-token` mintea JWT de 10 años sin auth → contrato del perfil.
- `approval_require_four_eyes=false`, `require_human_approval_for_external_actions=false` → contrato del perfil.
- `KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*` → contrato del perfil local.
- `MAIL_GODADDY_PASSWORD` plaintext en `.env` → decisión documentada del operador.
- `/health/dashboard.status="configured"` no `ok` → contrato AUDIT-2026-B.
- 14/14 capacidades unlocked → contrato del perfil.

---

## Conteo final

| Severidad | Cantidad | Estado |
|---|---|---|
| P0 | 0 | — |
| P1 | 0 | — |
| P2 | 1 | TS-ZF-20260523-001 |
| P3 | 3 | TS-ZF-20260523-002/003/004 |
| Informativo | 1 | TS-ZF-20260523-005 |

Plan de remediación en `07_REMEDIATION_PLAN.md`.
