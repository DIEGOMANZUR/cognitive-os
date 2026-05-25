# 06 - TestSprite API Plan

Fecha UTC: 2026-05-24T08:25:01Z
Suite: Cognitive OS - TestSprite API Full Contract Audit

## Fuente

Fuente principal:

- `/home/jgonz/Escritorio/testsprite/PRD_BACKEND.md`

OpenAPI:

- URL: `https://cognitive-api.doctormanzur.com/openapi.json`
- Copia local: `docs/audits/testsprite/cognitive-os-openapi.json`
- Paths observados: 143

Plan MCP generado:

- `testsprite_tests/testsprite_backend_test_plan.json`
- Casos generados: 1

El plan MCP backend es insuficiente para el PRD completo. La auditoria API debe
usar el siguiente backbone como instrucciones de ejecucion TestSprite.

## Auth

Header para protegidos:

```http
Authorization: Bearer <JWT>
```

## Public endpoints

- `GET /health`
- `GET /openapi.json`
- `GET /docs`
- `GET /redoc`

## Protected namespaces obligatorios

- `/actions`
- `/deepagents`
- `/mail`
- `/document-analysis`
- `/assist`
- `/system`
- `/jobs`
- `/langsmith`
- `/research`
- `/code-director`
- `/health`
- `/threads`
- `/documents`
- `/approvals`
- `/voice`
- `/chat`
- `/sandbox`
- `/auth`
- `/audit`
- `/knowledge`
- `/config`
- `/agents`

## Journeys API

J1 Liveness:

- `GET /health` sin auth -> 200.

J2 Readiness + system info:

- `GET /system/info`;
- `GET /system/readiness`;
- `GET /system/credentials-status`;
- no secretos.

J3 Catalog discovery:

- `GET /actions`;
- `GET /agents`;
- `GET /skills` si existe.

J4 Chat round trip:

- `POST /chat` con mensaje corto;
- `GET /threads/{thread_id}` si aplica.

J5 Document index:

- `GET /documents`;
- `GET /documents/{id}` si hay items.

J6 Approvals + audit:

- `GET /approvals`;
- `GET /audit?limit=5` o endpoint real equivalente.

J7 Jobs:

- `GET /jobs?limit=10`;
- `GET /jobs/{id}` si hay items.

J8 DeepAgents catalog:

- `GET /deepagents` o ruta real equivalente.

J9 Auth negative:

- missing token -> 401;
- invalid token -> 401;
- expired token -> 401 si puede fabricarse;
- insufficient role -> 403 si puede fabricarse.

J10 CORS:

- `OPTIONS /system/info`;
- Origin `https://cognitive.doctormanzur.com`;
- validar `Access-Control-Allow-Origin` y credentials.

## Negative contract

Probar malformed payloads, invalid UUIDs y nonexistent resources cuando sea
seguro. Resultado esperado: 4xx claro, no 5xx.

## Endpoints prohibidos

No llamar:

- `POST /mail/messages/{id}/approve-send`;
- `POST /mail/messages/{id}/send`;
- dispatch DNS real;
- sandbox exec destructivo;
- endpoints dangerous/destructive;
- rotacion de JWT secret/admin users.

Si se prueban guards, deben terminar en 400/403/409 y sin side effect.
