# 07 - TestSprite E2E Plan

Fecha UTC: 2026-05-24T08:25:01Z
Suite: Cognitive OS - TestSprite Full E2E Integrated Audit

## Objetivo

Verificar que la UI publica opera contra la API publica y que el perfil
`dedicated_local/full` funciona con baja friccion sin romper mail read-only,
health honesty, trazabilidad ni idempotencia.

## Runtime

- UI: `https://cognitive.doctormanzur.com`
- API: `https://cognitive-api.doctormanzur.com`
- Auth UI: `localStorage.cogos.token`
- API base UI: `localStorage.cogos.api`
- Auth API: `Authorization: Bearer <JWT>`

## Validaciones E2E obligatorias

- UI carga desde dominio publico.
- UI usa `cogos.api=https://cognitive-api.doctormanzur.com`.
- No hay fetch a `localhost`.
- No hay fetch a `127.0.0.1`.
- Backend `/health` responde.
- Auth funciona.
- Health tab refleja backend real.
- Jobs tab refleja backend real.
- Approvals tab refleja backend real.
- Audit lee backend real.
- Chat crea thread o devuelve error controlado.
- Mail no permite send/draft normal.
- Action Plane no ejecuta writes reales.
- Document Analysis crea job o error controlado.
- Research crea run o error controlado.
- Code Director muestra plan/status o error controlado.
- MCP status se muestra o degrada claro.
- Estados disabled/degraded son accionables.

## Journeys E2E

E2E-01 Bootstrap publico:

- seed JWT/API en localStorage;
- reload;
- TopBar conectado;
- capturar network y confirmar API publica.

E2E-02 Health honesty:

- abrir Health;
- leer cards;
- disparar verificacion live solo si TestSprite confirma que no ejecuta side
  effect externo irreversible;
- verificar que `configured` no sea falso verde.

E2E-03 Jobs/Audit:

- abrir Jobs;
- abrir Audit;
- confirmar tablas/empty states;
- no 5xx silenciosos.

E2E-04 Approvals:

- abrir Aprobaciones;
- si hay items, no aprobar mail/DNS/write real;
- empty state claro es pass.

E2E-05 Mail contract:

- abrir Mail;
- sync/digest preview permitido;
- no send;
- no draft;
- propuestas como texto.

E2E-06 Action Plane guards:

- preview/dry-run permitido;
- request seguro permitido;
- no dispatch de DNS/write real;
- guards 4xx no son bug.

E2E-07 Agent lanes:

- Chat, Document Analysis, Research, Code Director;
- exito o error controlado;
- job/event/audit visible si se crea trabajo.

## Evidencia esperada

Por failure:

- TestSprite ID;
- suite UI/API/E2E;
- tab o endpoint;
- pasos;
- screenshot/video/trace si TestSprite lo exporta;
- request/response si aplica;
- console/network error;
- probable causa;
- clasificacion bug real vs comportamiento esperado.
