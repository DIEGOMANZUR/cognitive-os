# 08 - TestSprite Plan Review

Fecha UTC: 2026-05-24T08:25:01Z

## Planes creados

| Plan | Origen | Artifact |
| --- | --- | --- |
| UI | TestSprite MCP + PRD expansion | `testsprite_tests/testsprite_frontend_test_plan.json`, `docs/audits/testsprite/05_TESTSPRITE_UI_PLAN.md` |
| API | TestSprite MCP limitado + PRD expansion | `testsprite_tests/testsprite_backend_test_plan.json`, `docs/audits/testsprite/06_TESTSPRITE_API_PLAN.md` |
| E2E | PRD-driven execution instructions for TestSprite MCP | `docs/audits/testsprite/07_TESTSPRITE_E2E_PLAN.md` |

## Revision del plan UI

TestSprite MCP genero 27 casos. Cobertura presente:

- mail read-only;
- persistencia de tabs/configuracion;
- health verification;
- settings/configuration readiness;
- approvals;
- suggested replies;
- command palette;
- MCP status;
- jobs;
- documents;
- audit malformed handling.

Faltaba o estaba subrepresentado:

- lista explicita de las 20 tabs del PRD;
- no-localhost en cada journey;
- CORS/mixed-content por origen publico;
- chat round trip;
- document-analysis/research/code-director;
- responsive/mobile.

Agregado en plan 05 y en instrucciones de ejecucion:

- disciplina SPA;
- seed localStorage;
- public API base;
- all tabs;
- no localhost;
- no mixed content/CORS;
- mail no-send/no-draft;
- disabled/degraded actionable states.

## Revision del plan API

TestSprite MCP genero solo 1 caso backend:

- `TC001 test_health_dashboard_live_verification`

Esto no cubre `PRD_BACKEND.md`. Faltaba:

- public/protected auth;
- J1-J10 completos;
- namespaces 21/22;
- invalid payloads;
- invalid UUIDs;
- 401/403 expected shapes;
- no secrets;
- no dangerous endpoints.

Agregado en plan 06:

- endpoints publicos;
- namespaces obligatorios;
- J1-J10;
- negative contract;
- prohibiciones de mail/DNS/sandbox/destructive.

## Revision del plan E2E

No hay tool TestSprite MCP separada para crear plan E2E integrado. La suite E2E
se define como instrucciones PRD-driven para `testsprite_generate_code_and_execute`
usando el runtime publico.

Areas obligatorias incluidas:

- UI -> API public URL;
- health honesty;
- readiness clarity;
- jobs/events;
- approvals;
- action plane guards;
- mail no-send/no-draft;
- degraded states.

## Que no se puede probar directamente con las tools MCP expuestas

- Editar plan TestSprite con tool estructurada.
- Cargar OpenAPI por parametro directo.
- Configurar URL frontend/backend por parametro directo.
- Exportar screenshots/traces por tool estructurada.
- Listar failures por tool estructurada.

Compensacion:

- runtime config local de TestSprite;
- planes Markdown PRD-driven;
- `additionalInstruction` estricto en ejecucion;
- artefactos TestSprite locales bajo `testsprite_tests/`;
- reportes sanitizados bajo `docs/audits/testsprite/`.

## Resultado de la revision previa a ejecucion

Se expandieron instrucciones antes de ejecutar para incluir:

- no mail send/draft ni approve-send;
- no DNS write real;
- no destructive sandbox/filesystem;
- no navegacion a pseudo-rutas de la SPA;
- seed de `localStorage`/Bearer JWT;
- backend publico obligatorio;
- no localhost/mixed content/CORS;
- clasificacion de estados disabled/degraded como esperados si son claros.

Limitaciones no resueltas antes de correr:

- TestSprite MCP no expone tool para editar plan de forma estructurada.
- TestSprite MCP no expone tool para inyectar JWT secreto como auth config
  separada; se intento via filesystem local e instruccion al generador.
- La suite backend quedo limitada por el plan de 1 caso generado por MCP.
