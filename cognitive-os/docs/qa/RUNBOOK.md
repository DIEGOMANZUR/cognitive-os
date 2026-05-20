# QA · RUNBOOK — cómo correr la app y la suite Playwright

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

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/backend"
uv run python -c "from cognitive_os.core.auth import create_access_token; print(create_access_token(user_id='auditor', roles=['admin']))"
```

Pegar el output en el campo JWT del panel (`http://localhost:3001` →
TopBar) o exportarlo como `COGOS_JWT` para Playwright.

## 3. Verificación rápida (sin Playwright)

```bash
JWT=$(cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/backend" && \
  uv run python -c "from cognitive_os.core.auth import create_access_token; print(create_access_token(user_id='auditor', roles=['admin']))" 2>/dev/null | tail -1)

curl -fsS http://127.0.0.1:8000/health                                 # public
curl -fsS -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/health/dashboard
curl -fsS -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/system/readiness
curl -fsS -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/system/mcp
curl -fsSI http://localhost:3001/                                       # frontend
```

Esperado: `/health` → `200 {"status":"ok",...}`; `/health/dashboard`
overall=ok, 17 componentes; `localhost:3001/` HTTP 200.

## 4. Instalar Playwright

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/frontend"
npm i -D @playwright/test
npx playwright install --with-deps chromium
```

(El proyecto NO necesita los otros browsers; `chromium` es suficiente
para auditar la SPA Next.js).

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
uv run pytest -q          # 712 passed esperado
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

## 8. Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| `localhost:3001` retorna 502/connection refused | Frontend caído | `Reiniciar Cognitive OS.sh` |
| `/health/dashboard` → 401 | JWT vencido o mal copiado | re-mintar (paso 2) |
| Playwright timeout en `page.goto` | Stack no levantado | paso 1 |
| `npx playwright install` falla | falta `--with-deps` para libs del SO | `sudo npx playwright install-deps chromium` o usar `--with-deps` desde root del proyecto |
| `console.error` ruidoso | inspeccionar trace en `test-results/` | reproducir manual con DevTools |
