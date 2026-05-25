# 10 - TestSprite Triage

Fecha UTC: 2026-05-24

## P0

Ninguno.

No se confirmo app down, API down, mail send/draft normal, DNS write real,
secreto expuesto, efecto destructivo, duplicacion peligrosa de acciones ni
health falso verde critico.

## P1

### P1-TS-001 - Health publico no logra verificacion live por fallo de auth/fetch

- Fuente: TestSprite E2E TC007 y UI TC007.
- Evidencia: `test-results/testsprite/initial-full-audit/e2e/raw_report.md`.
- Sintoma: Health muestra `Verificando...`, `Sin lecturas todavia`, 0 lecturas y
  mensaje de backend/JWT/API; TopBar reporta `Failed to fetch`.
- Impacto: rompe experiencia zero-friction `dedicated_local/full` en UI publica
  y deja readiness/health no accionable desde TestSprite.
- Clasificacion: bug probable de integracion publica o auth auto-token. Requiere
  fix/re-audit en Prompt 2.

## P2

### P2-TS-002 - TestSprite API auth injection bloqueada

- Fuente: API TC001.
- Evidencia: `test-results/testsprite/initial-full-audit/api/raw_report.md`.
- Sintoma: sandbox `/var/task` no ve `/tmp/cognitive_os_testsprite_jwt.txt`; la
  suite falla antes de llamar endpoints protegidos.
- Impacto: TestSprite no pudo auditar contrato API completo.
- Clasificacion: gap de instrumentacion TestSprite, no bug confirmado del backend.

### P2-TS-003 - Plan backend TestSprite insuficiente

- Fuente: `testsprite_generate_backend_test_plan`.
- Evidencia: `test-results/testsprite/initial-full-audit/api/testsprite_backend_test_plan.json`.
- Sintoma: solo 1 caso generado para backend.
- Impacto: no cubre PRD_BACKEND J1-J10 ni namespaces protegidos.
- Clasificacion: coverage gap de MCP.

### P2-TS-004 - MCP status no visible cuando backend data no carga

- Fuente: UI selective rerun TC017.
- Evidencia: `test-results/testsprite/initial-full-audit/ui/observed_results.md`.
- Sintoma: TestSprite no encontro tile/texto MCP; la misma pantalla mostraba
  `Failed to fetch`.
- Impacto: Conexión no demuestra estado MCP accionable bajo fallo de auth/fetch.
- Clasificacion: probablemente derivado de P1-TS-001.

## P3

### P3-TS-005 - Mail proposals/digest no cubiertos por ausencia de datos

- Fuente: UI TC001/TC013/TC021, E2E TC013.
- Evidencia: `test-results/testsprite/initial-full-audit/e2e/raw_report.md` y
  `test-results/testsprite/initial-full-audit/ui/observed_results.md`.
- Sintoma: mail disabled/read-only, sin propuestas seleccionables ni digest.
- Impacto: no se valida lectura de propuesta real, pero si se valida que no hay
  send/draft normal expuesto.
- Clasificacion: expected constrained state / coverage gap, no bug si ese estado
  es intencional.

### P3-TS-006 - Raw reports TestSprite incompletos

- Fuente: raw reports API/E2E.
- Sintoma: placeholders `{{TODO:AI_ANALYSIS}}`.
- Impacto: requiere consolidacion manual en `09_TESTSPRITE_INITIAL_RESULTS.md`.
- Clasificacion: artifact quality gap de TestSprite MCP.

## P4

Ninguno.

## No bugs segun PRD

No se marcaron como bug:

- 401 sin JWT o con token invalido.
- Bloqueo de endpoints peligrosos.
- Mail disabled/read-only con labels claros.
- Ausencia de propuestas mail durante auditoria.
- No navegar a pseudo-rutas SPA.
- Limitaciones del sandbox TestSprite para leer `/tmp`.

## Prioridad de Prompt 2

1. Confirmar y corregir flujo publico `POST /auth/local-token` / auto-token UI.
2. Revalidar Health live desde UI publica contra backend publico.
3. Exponer estado MCP/Conexión de forma accionable aun cuando backend falle.
4. Preparar mecanismo TestSprite-safe para auth API sin secretos en reportes.
5. Re-ejecutar TestSprite UI/API/E2E y preservar artifacts por suite antes de
   cada nueva corrida.
