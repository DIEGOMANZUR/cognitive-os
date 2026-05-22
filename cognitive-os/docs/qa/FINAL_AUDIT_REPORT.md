# QA · FINAL_AUDIT_REPORT — estado vigente y auditoría histórica

> **Actualización vigente (2026-05-22):** este reporte conserva abajo la
> auditoría Fase 76 como histórico, pero el gate actual del proyecto es más
> amplio:
>
> - `bash scripts/full-qa.sh` → **941 passed, 1 skipped, 28 deselected**,
>   ruff/format/mypy/Alembic/frontend lint/frontend build/`sync_doc_counts
>   --check`/`git diff --check` OK.
> - `npx playwright test --reporter=list` → **22 passed**.
> - `bash scripts/stress-qa.sh` → 3 pasadas de **941 passed**.
> - Carril opt-in `tests/live/` (`LIVE_TESTS_ENABLED=1`) → smokes read-only
>   contra proveedores reales.
> - Build frontend de QA aislado con `NEXT_DIST_DIR=.next-qa`, sin romper
>   un `next start` vivo servido desde `.next`.
>
> La auditoría comercial más reciente (`docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md`)
> cerró 8 hallazgos accionables (AUDIT-2026-A..H). La prioridad operacional
> actual es fricción casi nula en PC dedicado, no hardening SaaS. Aun así,
> los gates QA deben seguir probando arranque, UI honesta, workers, mail
> read-only/digest, errores visibles e idempotencia.

# QA · FINAL_AUDIT_REPORT — Fase 76 (auditoría E2E full-stack histórica)

Fecha: 2026-05-20. Auditor: agente senior. Alcance: panel web Next.js
+ API FastAPI + integraciones del Action Plane. Foco: **funcionamiento
perfecto**, no seguridad. Herramienta: **Playwright** como fuente de
verdad.

## 1. Resumen ejecutivo

- **Build:** verde (`npm run lint` 0 warnings, `npm run build` static
  prerender OK).
- **Backend:** suite pytest **712 passed** sin tocar (verificado pre-
  auditoría; la auditoría web no introdujo regresiones en Python).
- **E2E Playwright:** **16 tests, 16 pasan**, runtime ~18s.
- **Bugs encontrados:** 1 — `tsconfig` incluía `tests/e2e/` en el build
  de Next.js, lo cual causaba "Duplicate identifier 'Page'" después de
  agregar el helper de Playwright. Corregido.
- **Bugs latentes detectados:** ninguno crítico. Los tests cubren los
  flujos críticos sin necesidad de reescrituras.
- **Console.error inesperados:** 0 en flujos críticos.
- **Respuestas 5xx:** 0 en flujos críticos.

## 2. Inventario y flujos cubiertos

Detalle en `docs/qa/MAP.md`. La app es una **SPA Next.js 16** con 20
tabs intercambiables vía state local (no rutas separadas). Los 6 archivos
de la suite cubren:

### `smoke.spec.ts` (2 tests)

- `home renderiza Sidebar + TopBar sin errores 5xx ni console.error`
- `Dashboard muestra métricas vivas (no spinner infinito)`

### `navigation.spec.ts` (2 tests)

- `recorrido completo del Sidebar` — itera las **20 tabs**, verifica que
  cada `<button>` toma la clase `active` tras el click, falla si hay
  console.error inesperado o respuesta 5xx en cualquiera.
- `la tab elegida persiste tras refresh (cogos.tab en localStorage)`.

### `auth.spec.ts` (3 tests)

- `sin JWT el panel monta y muestra la TopBar pidiendo token`
- `pegar un JWT inválido NO rompe el SPA — la API responde 401 pero el UI sigue`
- `con JWT válido las llamadas autenticadas resuelven 200`

### `forms.spec.ts` (2 tests)

- `Guardar API base + JWT actualiza localStorage`
- `Settings rechaza un JWT vacío sin romper la UI`

### `responsive.spec.ts` (1 test, viewport Pixel 5)

- `Sidebar colapsa y reabre con el hamburger` + verifica que no haya
  overflow horizontal.

### `regression-critical.spec.ts` (6 tests)

Contratos clave de las últimas fases:

- `GET /health` público responde 200.
- `GET /health/dashboard` lista **17 componentes** incluido `mcp_client`
  (Fase 74).
- `GET /system/readiness` devuelve un report válido (Fase 72).
- `GET /system/mcp` respeta `enable_mcp_client` + lista servers (Fase 73).
- `GET /config/public` expone `operator_profile` + flags Fase 71-72.
- **CRUD:** `PersonalTask` end-to-end (crear → listar) con skip elegante
  si la capacidad de assistant no está cableada en el host.

## 3. Bugs encontrados y corregidos

| ID | Severidad | Bug | Causa raíz | Fix |
|---|---|---|---|---|
| QA-1 | medium | `npm run build` rompía con `Duplicate identifier 'Page'` después de instalar Playwright | El `tsconfig.json` original incluía `**/*.ts` sin excluir `tests/` ni `playwright.config.ts`. El compilador de Next.js intentaba typear los archivos de test y chocaba con los imports duplicados de tipos de `@playwright/test`. | Agregado `"tests"` y `"playwright.config.ts"` al campo `exclude` de `tsconfig.json` + consolidados los imports de tipos en `_helpers.ts`. |

Ningún bug funcional adicional: el frontend renderiza las 20 tabs, el
JWT persiste, los endpoints Fase 71-74 (`/system/readiness`, `/system/
mcp`, `mcp_client` en health) responden con el shape esperado, y la
versión mobile colapsa el sidebar correctamente.

## 4. Bugs latentes considerados / descartados

- **Pantallas blancas en alguna tab:** no detectadas. El recorrido
  completo de 20 tabs no produjo excepciones uncaught ni respuestas 5xx.
- **Polling agresivo con JWT inválido:** el sistema responde 401 (no
  5xx), el UI permanece estable, el sentinel del test no captura
  `console.error` por encima del umbral tolerado.
- **CRUD de Personal Assistant:** funciona en este host (test pasó); en
  hosts sin `TELEGRAM_ASSIST_USER_MAP` la spec se autoskippea con un
  `test.skip` explícito en lugar de fallar (decisión consciente).
- **Cliente MCP:** los 3 servers declarados (Supermemory, GitHub,
  filesystem) están `connected=true`. El test verifica la forma de la
  respuesta y la presencia del componente `mcp_client` en
  `/health/dashboard`.

## 5. Tests creados (estructura)

```
frontend/
├── playwright.config.ts           # 2 projects (chromium-desktop + chromium-mobile)
└── tests/e2e/
    ├── _helpers.ts                # auth seed, watchers, tabButton locator
    ├── smoke.spec.ts              # 2 tests
    ├── navigation.spec.ts         # 2 tests (las 20 tabs + refresh)
    ├── auth.spec.ts               # 3 tests
    ├── forms.spec.ts              # 2 tests
    ├── responsive.spec.ts         # 1 test (Pixel 5)
    └── regression-critical.spec.ts # 6 tests (6 contratos Fase 72-74 + CRUD)
```

### Calidad de los locators

- Cero `data-testid` en el frontend → los locators usan `getByRole` con
  regex sobre nombres compuestos del Sidebar (`◧ Dashboard 1`).
- Helper `tabButton(page, label)` centraliza la lógica para no repetir
  regex en cada spec.
- Cero `page.waitForTimeout(arbitrary_ms)` salvo un `500ms` puntual en
  `auth.spec` que es razonable (esperar que un polling dispare al
  cambiar el JWT). Donde se requiere "esperar a que pase algo" se usa
  `expect.poll(...)` con timeout explícito.

### Garantías por test

- `trace: "on-first-retry"` — el primer fallo guarda trace completo.
- `screenshot: "only-on-failure"`.
- `video: "retain-on-failure"`.
- `watchPageHealth(page)` captura `console.error`, `pageerror`,
  `requestfailed` y respuestas ≥500; los tests assertan sobre estos
  arrays.

## 6. Comandos de verificación

```bash
# Backend pytest (referencia):
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/backend"
uv run pytest -q                                   # 941 passed esperado en snapshot vigente

# Frontend lint + build:
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os/frontend"
npm run lint                                       # 0 warnings
npm run build                                      # static prerender OK

# E2E Playwright (stack levantado en :3001 + :8000):
JWT=$(cd ../backend && uv run python -c "from cognitive_os.core.auth import create_access_token; print(create_access_token(user_id='auditor', roles=['admin']))" 2>/dev/null | tail -1)
COGOS_JWT="$JWT" npx playwright test               # 22 passed esperado en snapshot vigente
COGOS_JWT="$JWT" npx playwright test --ui          # modo interactivo
npx playwright show-report                          # HTML report
```

## 7. Evidencia disponible

- **Reporte HTML:** `frontend/playwright-report/` (ignorado en git;
  generado en cada corrida).
- **Traces/screenshots/videos de fallos:** `frontend/test-results/`
  (también ignorado; sólo se llena cuando hay fallos).
- **Logs del stack:** `~/.cognitive-os/logs/{api,worker,beat,frontend,
  telegram,kimi}.log`.
- **Commits relevantes:** ver `git log --oneline -3` después de Fase 76.

## 8. Riesgos pendientes (no bloquean el criterio de aceptación)

1. **Ningún test del Chat con LLM real.** Probar el `POST /chat` real
   gastaría tokens del operador. Decisión consciente: lo dejamos fuera
   de la suite automatizada. La regresión más cercana son los tests
   pytest del orquestador (cubren `route_request`, `comm`, `social`,
   `research`, `legal` con LLM mockeado).
2. **Cero `data-testid` en componentes.** Los locators por role son
   robustos hoy pero un rebrand del sidebar (renombrar "Dashboard" → "Inicio")
   rompería los tests. Si el frontend crece, agregar `data-testid` a los
   botones de tab daría locators inmunes a cambios de copy.
3. **El test del Chat de Telegram NO se cubre por Playwright** — eso es
   un flujo bot-side. Los tests pytest del telegram_bot (20 unit tests)
   son la fuente de verdad ahí.
4. **Pruebas multi-navegador (Firefox/WebKit) no incluidas.** Sólo
   chromium. Si el operador necesita certificar otros browsers, los
   `projects` de `playwright.config.ts` están listos para agregarlos.

## 9. Recomendaciones siguientes

- **Cuando se agregue `data-testid`:** migrar `tabButton()` y los
  locators de inputs a `getByTestId(...)` para eliminar el
  acoplamiento al copy.
- **Tests de Code Director con planner Heurístico** (sin LLM real):
  podría cubrir el flow plan → approval → dispatch usando un FakeAdapter
  registrado vía `playwright.config.ts` globalSetup que mocke el
  endpoint.
- **CI:** integrar `COGOS_JWT` como secret (test-only token con
  expiración corta) y correr la suite en cada push a la rama
  `codex/fase-34-baseline-hardening`. Hoy se corre manual.
- **Monitor de polling intervals:** la suite no mide ancho de banda; si
  el operador percibe lag, vale revisar los `usePolledFetch` intervals
  (algunos en 10s podrían subir a 30s sin pérdida funcional).

## 10. Criterio de aceptación

| Criterio | Estado |
|---|---|
| Build pasa | ✅ `npm run build` |
| Lint pasa | ✅ `npm run lint` (0 warnings) |
| Typecheck pasa | ✅ implícito en `npm run build` (Next.js typechek) |
| Playwright E2E pasa completo | ✅ 16/16 |
| No hay console.error inesperado en flujos críticos | ✅ verificado |
| No hay requests 500 en flujos críticos | ✅ verificado |
| Existe reporte final reproducible | ✅ este documento |

**Auditoría cerrada.**
