# 12 - TestSprite Fix Log

Fecha UTC: 2026-05-24

## Fix TS-001

- Hallazgo: la UI publica podia quedar sin JWT/API efectivo bajo TestSprite,
  mostrando `Failed to fetch`, Health sin lecturas y `Verificando...`.
- Suite: UI / E2E.
- Severidad: P1.
- Root cause: `useLocalState` leia `localStorage` en un `useEffect` posterior al
  primer render. Cuando TestSprite no aplicaba consistentemente el pre-step antes
  de navegar, el auto-token podia ejecutarse con el default local
  `http://127.0.0.1:8000` antes de que `cogos.api` publico estuviera en estado.
  Adicionalmente, el dominio publico no tenia fallback propio si faltaba
  localStorage/env.
- Archivos modificados:
  - `frontend/app/lib/hooks.ts`
  - `frontend/app/page.tsx`
  - `frontend/app/lib/api.ts`
  - `frontend/app/views/HealthView.tsx`
- Cambio aplicado:
  - `useLocalState` inicializa desde `window.localStorage` de forma sincrona
    cuando corre en navegador.
  - `defaultApiBase()` usa `https://cognitive-api.doctormanzur.com` cuando la UI
    se sirve desde `cognitive.doctormanzur.com`, conservando
    `http://127.0.0.1:8000` para uso local-first.
  - `POST /auth/local-token` en UI tiene timeout de 10 s y error accionable.
  - `ApiClient.post` acepta `AbortSignal`; `HealthView` evita spinner infinito
    de live verify con timeout y mensaje claro.
- Por que respeta PRD:
  - Mantiene `dedicated_local/full` como camino principal de baja friccion.
  - No cambia auth backend, roles, mail, Action Plane ni safety flags.
  - No convierte la SPA en multi-route y no relaja secretos.
- Riesgo:
  - Bajo. El cambio afecta bootstrap de API/JWT y el estado de timeout de
    Health; los endpoints y payloads no cambian.
- TestSprite rerun:
  - UI focal TS-001: `TC007` PASS en
    `test-results/testsprite/repair-reruns/ui-targeted/`.
  - UI/E2E critical: `TC005`, `TC007`, `TC017` PASS en
    `test-results/testsprite/post-repair-critical/ui-e2e-batch-a/`.
- Resultado:
  - FIX VERIFIED por TestSprite. Runtime preparado: build frontend realizado
    para servir el fix con `next start`; `/health` local/publico y
    `/auth/local-token` publico responden 200.

## Fix TS-004

- Hallazgo: TestSprite no encontro estado MCP cuando el fetch backend no cargo.
- Suite: UI.
- Severidad: P2.
- Root cause: `SettingsView` renderizaba la seccion `MCP servers` solo con
  `mcpInventory.data && mcpInventory.data.enabled`; en error/loading/disabled no
  habia superficie estable y accionable para el operador ni para TestSprite.
- Archivos modificados:
  - `frontend/app/views/SettingsView.tsx`
- Cambio aplicado:
  - La seccion `MCP servers` ahora se renderiza siempre.
  - Estados cubiertos: `cargando`, `sin datos`, error de `/system/mcp`,
    `ENABLE_MCP_CLIENT=false`, enabled sin servers, y lista de servers.
  - El error dice explicitamente que no se marca verde sin inventario real.
- Por que respeta PRD:
  - Refuerza health/readiness honesto y degradacion accionable.
  - No inventa conectividad MCP ni oculta fallos.
- Riesgo:
  - Bajo. Solo cambia rendering de Settings/Conexión.
- TestSprite rerun:
  - UI focal TS-004: `TC017` PASS en
    `test-results/testsprite/repair-reruns/ui-targeted/`.
  - UI/E2E critical: `TC017` PASS en
    `test-results/testsprite/post-repair-critical/ui-e2e-batch-a/`.
- Resultado:
  - FIX VERIFIED por TestSprite.

## Runtime preparation

- Accion: se reinicio el stack con `/home/jgonz/Escritorio/cognitive-os.sh`.
- Motivo: el API local escuchaba en `127.0.0.1:8000` pero no respondia a
  `/health`; los logs de API estaban stale. El launcher tuvo que escalar el API
  viejo a SIGKILL.
- Build: `npm run build` en `frontend/` para que `next start` sirva el bundle
  reparado. Esto fue preparacion de runtime para TestSprite, no suite QA.
- Smoke minimo de runtime:
  - `GET http://127.0.0.1:8000/health` -> 200.
  - `GET https://cognitive-api.doctormanzur.com/health` -> 200.
  - `POST https://cognitive-api.doctormanzur.com/auth/local-token` -> 200
    con token enmascarado.
  - `HEAD https://cognitive.doctormanzur.com` -> 200.
