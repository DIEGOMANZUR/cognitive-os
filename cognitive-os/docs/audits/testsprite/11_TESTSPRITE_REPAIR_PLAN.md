# 11 - TestSprite Repair Plan

> **Actualización 2026-05-26:** este archivo es evidencia histórica de auditoría. El flujo vigente ya no usa TopBar: la autenticación pública es por `#cogos_token` o `localStorage.cogos.token`, la API se resuelve automáticamente por host y el shell estable se valida con `<main data-cogos-active-tab="...">`. Las menciones a TopBar debajo se conservan solo como contexto histórico.

Fecha UTC: 2026-05-24

Fuente exclusiva de QA: reportes y artifacts TestSprite de
`test-results/testsprite/initial-full-audit/`, mas los PRD canonicos en
`/home/jgonz/Escritorio/testsprite`.

## Resumen

TestSprite no encontro P0. El unico fallo P1 accionable es el bootstrap publico
de UI/API: en algunas corridas el runner no aplico el pre-step de `localStorage`
y la UI dependio del auto-token. El frontend podia iniciar con el `apiBase`
local antes de leer `cogos.api`, dejando `Failed to fetch`, Health sin lecturas
y Settings sin estado MCP visible.

## A. Corregir ahora

### TS-001 / P1-TS-001

- ID: TS-001.
- Suite: UI / E2E.
- Severidad: P1.
- Reproduccion TestSprite: UI TC007 y E2E TC007 abren la UI publica, navegan a
  Health y pulsan `Verificar en vivo`.
- Expected segun PRD: en `dedicated_local/full`, la UI publica debe operar con
  baja friccion contra `https://cognitive-api.doctormanzur.com`, obtener JWT
  local automatico o usar el JWT sembrado, y mostrar health/readiness honesto.
- Actual: TopBar muestra API publica, pero aparece `No se pudo activar el JWT
  local automatico. Detalle: Failed to fetch`; Health queda con
  `Verificando...`, `Sin lecturas todavia` y 0 lecturas.
- Evidencia:
  `test-results/testsprite/initial-full-audit/e2e/raw_report.md` y
  `test-results/testsprite/initial-full-audit/ui/observed_results.md`.
- Bug real: si. Rompe el contrato zero-friction publico cuando TestSprite no
  logra sembrar `localStorage` antes del primer fetch.
- Causa raiz probable: `useLocalState` inicializa con el default en el primer
  render y lee `localStorage` recien en `useEffect`; el auto-token puede correr
  con `http://127.0.0.1:8000` antes de ver `cogos.api`. Ademas el dominio
  publico no tiene default publico propio.
- Archivos a tocar:
  - `frontend/app/lib/hooks.ts`
  - `frontend/app/page.tsx`
  - `frontend/app/lib/api.ts` y `frontend/app/views/HealthView.tsx` si hace
    falta evitar spinners indefinidos.
- Fix propuesto:
  - Leer `localStorage` sincronamente en el initializer client-side.
  - Elegir `https://cognitive-api.doctormanzur.com` como default cuando la UI
    se sirve desde `cognitive.doctormanzur.com`.
  - Mantener `http://127.0.0.1:8000` como default local-first en localhost.
  - Acotar el auto-token con timeout y error accionable.
- TestSprite rerun requerido:
  - UI focal: bootstrap + Health TC007.
  - E2E focal: UI publica -> API publica + Health live.
  - Critical smoke UI/E2E posterior.
- Criterio de cierre: TestSprite no observa fetch a localhost desde dominio
  publico; TopBar queda conectado o con error accionable; Health carga lecturas
  o devuelve degradacion controlada sin spinner infinito.

### TS-004 / P2-TS-004

- ID: TS-004.
- Suite: UI.
- Severidad: P2.
- Reproduccion TestSprite: UI TC017 abre Conexión/Sistema y busca estado de MCP.
- Expected segun PRD: el operador debe ver estado MCP o degradacion accionable,
  sin falsos verdes.
- Actual: cuando backend data no cargo por el mismo `Failed to fetch`, la seccion
  MCP no se renderizo.
- Evidencia:
  `test-results/testsprite/initial-full-audit/ui/observed_results.md`.
- Bug real: si, como degradacion UI derivada de TS-001. La UI no debe ocultar
  una zona critica solo porque el fetch fallo.
- Causa raiz probable: `SettingsView` renderiza `MCP servers` solo cuando
  `mcpInventory.data && mcpInventory.data.enabled`.
- Archivos a tocar:
  - `frontend/app/views/SettingsView.tsx`
- Fix propuesto: renderizar siempre la seccion MCP con estados `loading`,
  `error`, `disabled`, `empty` o lista conectada, usando texto accionable.
- TestSprite rerun requerido:
  - UI focal TC017.
  - UI critical smoke posterior.
- Criterio de cierre: TestSprite puede encontrar `MCP servers` y un estado
  honesto aun cuando `/system/mcp` falle o este disabled.

## B. No bug segun PRD

### TS-002 / P2-TS-002

- ID: TS-002.
- Suite: API.
- Severidad TestSprite: P2.
- Reproduccion: API TC001 intento leer `/tmp/cognitive_os_testsprite_jwt.txt`
  desde el sandbox remoto `/var/task`.
- Expected segun PRD: los endpoints protegidos requieren `Authorization: Bearer
  <JWT>`. El JWT no debe imprimirse ni depender de rutas locales inaccesibles
  para un runner remoto.
- Actual: TestSprite fallo antes de llamar el backend por `FileNotFoundError`.
- Evidencia:
  `test-results/testsprite/initial-full-audit/api/raw_report.md`.
- Bug real: no confirmado en producto. Es una falla de instrumentacion del caso
  generado por TestSprite.
- Fix propuesto: ajustar los reruns API para usar token inyectado por variable o
  fixture TestSprite, sin leer archivos locales del host y sin exponer el valor
  completo en reportes.
- TestSprite rerun requerido: API critical con auth configurada en el propio
  contexto TestSprite.
- Criterio de cierre: la suite API no falla por no poder leer `/tmp`; si falla,
  debe ser por respuesta real del backend.

### TS-003 / P2-TS-003

- ID: TS-003.
- Suite: API.
- Severidad TestSprite: P2.
- Reproduccion: el plan backend generado tuvo 1 caso.
- Expected segun PRD: cubrir public/protected auth, J1-J10 y namespaces
  criticos.
- Actual: coverage insuficiente.
- Evidencia:
  `test-results/testsprite/initial-full-audit/api/testsprite_backend_test_plan.json`.
- Bug real: no es bug de runtime; es gap de cobertura TestSprite.
- Fix propuesto: documentar casos de regresion y pedir rerun API critico
  focalizado a TestSprite.
- Criterio de cierre: reporte post-repair distingue cobertura real de bloqueo
  MCP.

### TS-005 / P3-TS-005

- ID: TS-005.
- Suite: UI / E2E.
- Severidad: P3.
- Reproduccion: mail proposals/digest no inspeccionables por estado read-only,
  disabled o ausencia de datos.
- Expected segun PRD: durante auditoria no enviar mails, no crear drafts y no
  aprobar envios; mail normal debe ser read-only.
- Actual: no hubo propuestas reales, pero tampoco send/draft normal expuesto.
- Bug real: no.
- Criterio de cierre: mantener el contrato mail read-only en los reruns
  criticos.

### TS-006 / P3-TS-006

- ID: TS-006.
- Suite: artifacts TestSprite.
- Severidad: P3.
- Reproduccion: raw reports contienen placeholders `{{TODO:AI_ANALYSIS}}`.
- Expected segun PRD: consolidacion local con evidencia.
- Actual: artifact crudo incompleto; `09_TESTSPRITE_INITIAL_RESULTS.md` y
  `10_TESTSPRITE_TRIAGE.md` ya consolidan manualmente.
- Bug real: no es bug de Cognitive OS.
- Criterio de cierre: reportes 14-16 deben resumir outputs TestSprite sin
  inventar resultados.

## C. Bloqueado por infraestructura externa

Ningun hallazgo inicial queda clasificado como bloqueo externo permanente. En la
preparacion de reparacion se observo un runtime local escuchando en
`127.0.0.1:8000` pero sin responder a `/health`; se tratara como problema de
runtime para poder re-ejecutar TestSprite, usando los launchers canonicos si es
necesario. Si persiste, quedara documentado en los reportes 14-16.

## D. Necesita aclaracion

Nada requiere aclaracion antes de reparar. El mejor esfuerzo es corregir TS-001
y TS-004 sin tocar el contrato de mail, Action Plane ni seguridad de secretos.
