# QA · RUNBOOK — cómo correr la app y la suite Playwright

<!-- V2_ABSOLUTE_CLOSURE_STATUS_START -->

> **Cierre V2.0 absoluto local-first (2026-05-27, Prompt 7):** esta rama `codex/commercial-zero-friction-hardening` en base `8a33475d0502` queda sincronizada para el cierre comercial local-first. La evidencia viva se concentra en `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/tmp/v2_07_absolute_release_closure_20260527_050231`. Estado de producto verificado durante Prompt 7: backend FastAPI local, frontend Next.js, Docker services, Postgres, Redis, Weaviate, Neo4j, Alembic head, worker, beat, health/readiness, LangGraph/chat, DeepAgents, MCP, RAG/documentos, Document Analysis, Action Plane sandbox, mail read-only, Telegram, Google read-only, GoDaddy dry-run, Kimi WebBridge y Code Director toy/guard rails.
>
> **Gates V2.0 ejecutados antes de los dos ciclos verdes finales:** `bash scripts/full-qa.sh` **1221 passed, 1 skipped, 28 deselected**; `bash scripts/stress-qa.sh 5` **5/5 verde x 1221 passed**; `cd frontend && npx playwright test` **44 passed**; `LIVE_TESTS_ENABLED=1 bash scripts/full-qa-live.sh` **8 passed**; `python3 scripts/sync_doc_counts.py --check` OK; `bash scripts/verify_desktop_launchers.sh` OK; OpenAPI read-only smoke **70 GET / 0 failures**; security read-only scan sin secretos críticos; CDP/Playwright forense **10 ciclos x 20 vistas** sin console/page errors ni 5xx, con un aborto `POST /auth/local-token` adjudicado como cierre de contexto del harness y no defecto de producto; Lighthouse local: accessibility 96, best-practices 100, SEO 100.
>
> **Criterio de verdad:** no se declara envio de correo, draft real ni escritura DNS. Mail queda normalizado como read-only: sync/list/classify/digest/proposed replies como texto, sin drafts ni sends. GoDaddy queda preview/dry-run; Action Plane mantiene sandbox/approval/audit/idempotencia segun riesgo. El tunnel publico `cognitive.doctormanzur.com` se valida con `scripts/testsprite_web/deploy_and_verify.sh` cuando Diego vaya a correr TestSprite web; Prompt 7 no lo expone permanentemente porque su propia regla prohibe exponer servicios a internet.

<!-- V2_ABSOLUTE_CLOSURE_STATUS_END -->


> **Actualización vigente (2026-05-26, HEAD `8a33475`):** además del gate
> local-first 2026-05-25, el cockpit público/TestSprite web quedó endurecido con
> hash auth `#cogos_token`, API pública automática, shell sin TopBar,
> `data-cogos-active-tab`, hotkey `3 DeepAgents`, estados comerciales
> loading/empty/error, responsive 920px y SW `cogos-v2026-05-26e-status-cards`.
> Para preparar el portal web de TestSprite se usa un solo comando:
>
> ```bash
> bash scripts/testsprite_web/deploy_and_verify.sh
> ```
>
> Ese script reconstruye producción, levanta backend/worker/beat/frontend/tunnel,
> valida frontend público, backend `/health`, marker SW y shell antes del rerun
> humano. No declarar doble verde web hasta recibir reportes/PDFs del portal.
>
> QA oficial local del proyecto:
>
> - `bash scripts/full-qa.sh` con **1200 passed**, 1 skipped, 28
>   deselected (1190 base + 2 regresión `test_clean_slate_fixture_covers_all_fks.py`).
> - `bash scripts/stress-qa.sh 5` -> **5/5 verde × 1200 passed**,
>   flakiness post-fix = 0%.
> - Playwright **43 passed** sin necesidad de exportar `COGOS_JWT`: el
>   `tests/e2e/_global-setup.ts` mintea el JWT via
>   `POST /auth/local-token` cuando el perfil es `dedicated_local/full`.
> - Carril opt-in `bash scripts/full-qa-live.sh` (`LIVE_TESTS_ENABLED=1`)
>   para smokes read-only contra proveedores reales, último gate documentado
>   **8 passed**.
> - `/system/mcp` verificado **6/6 servers** y **69 tools**.
> - TestSprite local/MCP histórico: **10/10** re-audit acotado y batched local
>   **28/28 passed**; distinto del rerun web público vigente.
>
> El objetivo del QA actual no es seguridad SaaS; es operación local de baja
> fricción sin fallos silenciosos: arranque reproducible, UI que no engaña, jobs
> trazables, workers vivos, mail read-only/digest y errores visibles.

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

Pegar el output en la pestaña *Conexión* / *Settings* del panel (`http://localhost:3001`), abrir con `#cogos_token=<JWT_SIN_BEARER>` o exportarlo como `COGOS_JWT` si se quiere fijar manualmente.

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
uv run pytest -q          # 1200 passed esperado post-remediación (1190 base + 2 regresión FK order)
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
