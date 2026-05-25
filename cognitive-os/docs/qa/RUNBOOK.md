# QA · RUNBOOK — cómo correr la app y la suite Playwright

> **Actualización vigente (2026-05-25 post-activación funcional, base
> `0f8232a` — APTO COMERCIAL LOCAL-FIRST · FUNCTIONAL WITH WARNINGS):**
> 16 fases funcionales ejecutadas con stack vivo. Reporte:
> `tmp/full_functional_activation_20260525_073134/reports/`. Hallazgo P1
> runtime: F-RUNTIME-001 `browser_preview` Playwright sync/async (no
> regresión, preexistente). QA oficial del proyecto:
>
> - `bash scripts/full-qa.sh` con **1192 passed**, 1 skipped, 28
>   deselected (1190 base + 2 regresión `test_clean_slate_fixture_covers_all_fks.py`).
> - `bash scripts/stress-qa.sh 5` -> **5/5 verde × 1192 passed**,
>   flakiness post-fix = 0% (cerró F-P0-001 — root cause: orden FK del
>   fixture `clean_slate`, fix en 3 archivos de test sin tocar producto).
> - Playwright **43 passed** sin necesidad de exportar `COGOS_JWT`: el
>   `tests/e2e/_global-setup.ts` mintea el JWT via
>   `POST /auth/local-token` cuando el perfil es `dedicated_local/full`.
>   Incluye `audit-commercial-mail-no-send-button.spec.ts`.
> - Build frontend dentro de `full-qa.sh` usa `NEXT_DIST_DIR=.next-qa`
>   para no invalidar un frontend vivo.
> - Carril opt-in `bash scripts/full-qa-live.sh` (`LIVE_TESTS_ENABLED=1`)
>   para smokes read-only contra proveedores reales, último gate
>   documentado **8 passed**.
> - `/system/mcp` quedó verificado **6/6 servers** y **69 tools** tras
>   el inventario paralelo con timeout 30s (`5953b40`) y el alta local
>   del MCP `time` (`ce72dc2`).
> - **Audit-commercial hardening matrix:** 16 archivos
>   `test_audit_commercial_*` (15 backend + 1 Playwright) con ~230
>   asserciones cubren los 4 P0-críticos (Mail SMTP gate, GoDaddy DNS
>   gate, Code Director STDIN-only, Mail UI sin botón Enviar) y 12
>   GAPs P1 (eager_defaults full, auth matrix, path-traversal corpus,
>   operational_backlog reactivo, workflow.v1 hardening,
>   calendar/drive directo `dry_run=false`→409, health overall honest,
>   reapers dedicados, DB isolation guard, secrets redaction, fixtures
>   gating, MCP fail-open).
> - TestSprite MCP re-audit histórico: **10/10 passed** sobre dos
>   batches acotados (TC001/002/003/004/006/007/008/009/010/014).
>
> El objetivo del QA actual no es seguridad SaaS; es operación local de
> baja fricción sin fallos silenciosos: arranque reproducible, UI que no
> engaña, jobs trazables, workers vivos, mail read-only/digest y errores
> visibles.

Auditoría Fase 76. Todo verificado en este host (Linux 6.17,
`/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/`).

## 1. Levantar / detener / estado del stack

Cuatro launchers de escritorio en `~/Escritorio/`:

```bash
~/Escritorio/Levantar\ Cognitive\ OS.sh   # arranca todo (docker, api, worker, beat, frontend, telegram, kimi)
~/Escritorio/Reiniciar\ Cognitive\ OS.sh  # stop + start
~/Escritorio/Detener\ Cognitive\ OS.sh    # apaga todo
~/Escritorio/Estado\ Cognitive\ OS.sh     # snapshot estado actual
```

Logs por componente: `~/.cognitive-os/logs/{api,worker,beat,frontend,telegram,kimi}.log`.

Stack esperado tras `Levantar`:

```
docker     : running  (postgres + redis + weaviate + neo4j)
api        : running  http://127.0.0.1:8000
worker     : running
beat       : running
frontend   : running  http://localhost:3001
telegram   : running  (si TELEGRAM_ENABLED=true)
kimi       : running  http://127.0.0.1:10086
```

## 2. Mintar un JWT de admin para el panel/Playwright

**Forma corta (zero-friction, perfil `dedicated_local/full`).** El backend
expone `POST /auth/local-token` sin auth (sólo bajo ese perfil; otros
perfiles devuelven `403`). Para Playwright esto es **automático**:
`tests/e2e/_global-setup.ts` mintea el JWT y lo expone como `COGOS_JWT`
al worker antes de que arranquen los specs. Para uso manual:

```bash
JWT=$(curl -sX POST http://127.0.0.1:8000/auth/local-token | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
echo "$JWT"
```

Pegar el output en el campo JWT del panel (`http://localhost:3001` →
TopBar) o exportarlo como `COGOS_JWT` si se quiere fijar manualmente.

**Forma larga (`strict`/`guarded` o entornos sin endpoint de mint).**
Sólo cuando el perfil bloquea `/auth/local-token`:

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/backend"
uv run python -c "from cognitive_os.core.auth import create_access_token; print(create_access_token(user_id='auditor', roles=['admin']))"
```

## 3. Verificación rápida (sin Playwright)

```bash
JWT=$(curl -sX POST http://127.0.0.1:8000/auth/local-token | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl -fsS http://127.0.0.1:8000/health                                 # public
curl -fsS -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/health/dashboard
curl -fsS -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/system/readiness
curl -fsS -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/system/mcp
curl -fsSI http://localhost:3001/                                       # frontend
```

Esperado: `/health` → `200 {"status":"ok",...}`; `/health/dashboard`
con 18 componentes y overall `ok` o `configured` (este último si algún
componente está cableado pero sin probe en vivo — usar `POST /health/verify`
para verificarlo); `localhost:3001/` HTTP 200.

## 4. Preparar Playwright

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/frontend"
npm ci
npx playwright install --with-deps chromium
```

(No usar `npm install` o `npm update` como parte de QA normal. Si falta
una dependencia, tratarlo como incidente de entorno/lockfile.)

## 5. Correr la suite E2E

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/frontend"

# Suite completa (asume stack levantado en :3001 + :8000):
COGOS_JWT="$JWT" npx playwright test

# Una sola spec:
COGOS_JWT="$JWT" npx playwright test tests/e2e/smoke.spec.ts

# Modo UI interactivo:
COGOS_JWT="$JWT" npx playwright test --ui

# Generar reporte HTML:
npx playwright show-report
```

Salidas:

- Test reports → `frontend/playwright-report/`
- Traces, screenshots, videos en fallos → `frontend/test-results/`

## 6. Lint + typecheck + build del frontend

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/frontend"
npm run lint    # eslint --max-warnings 0
npm run build   # next build
```

## 7. Suite backend (referencia)

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/backend"
uv run pytest -q          # 1192 passed esperado post-remediación (1190 base + 2 regresión FK order)
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

**Aislamiento de DB:** `pytest` **nunca** toca la base de producción.
`tests/conftest.py` redirige `DATABASE_URL` a una base `_test` dedicada
(`cognitive_os_test` por defecto), que se **dropea + recrea + migra a
head** al inicio de cada corrida. El header de pytest lo confirma:
`test database: cognitive_os_test (isolated — production DB is never
touched)`. Para apuntar a otra base, exportá `TEST_DATABASE_URL` (su
nombre debe contener `test`; el conftest se niega a correr si no, o si
la URL coincide con la de producción).

## 8. Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| `localhost:3001` retorna 502/connection refused | Frontend caído | `Reiniciar Cognitive OS.sh` |
| `/health/dashboard` → 401 | JWT vencido o mal copiado | re-mintar (paso 2) |
| Playwright timeout en `page.goto` | Stack no levantado | paso 1 |
| `npx playwright install` falla | falta `--with-deps` para libs del SO | `sudo npx playwright install-deps chromium` o usar `--with-deps` desde root del proyecto |
| `console.error` ruidoso | inspeccionar trace en `test-results/` | reproducir manual con DevTools |
