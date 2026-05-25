# 18 - TestSprite Zero Defects Runtime Check

Fecha UTC: 2026-05-24

## TestSprite MCP

- Tool discovery: `mcp__testsprite_agent__` disponible.
- Cuenta: TestSprite Starter, 439 credits al inicio del loop final.
- Herramientas usadas/permitidas:
  - `testsprite_check_account_info`
  - `testsprite_generate_code_and_execute` / CLI MCP indicado por la tool

## Launcher/runtime

Comandos canonicos ejecutados:

- `/home/jgonz/Escritorio/cognitive-os.sh doctor`
- `/home/jgonz/Escritorio/cognitive-os.sh status`

Resultado:

- Docker: running.
- API: running en `http://127.0.0.1:8000/health`.
- Worker: running.
- Beat: running.
- Frontend: running en `http://localhost:3001`.
- Telegram: running.
- Kimi WebBridge: running.

## URLs publicas

- Frontend: `https://cognitive.doctormanzur.com`
  - HEAD: 200.
- Backend: `https://cognitive-api.doctormanzur.com`
  - `GET /health`: 200, `{"status":"ok","service":"cognitive-os"}`.
- OpenAPI:
  - `GET /openapi.json`: 200, OpenAPI 3.1.0.

## Auth

- UI:
  - `localStorage.cogos.api = https://cognitive-api.doctormanzur.com`.
  - `localStorage.cogos.token = <JWT>` cuando TestSprite necesita Bearer.
  - El frontend tambien puede auto-mint via `POST /auth/local-token` en
    `dedicated_local/full`.
- API:
  - `POST /auth/local-token`: 200.
  - Token en reportes: siempre enmascarado.
  - Headers protegidos: `Authorization: Bearer <JWT>`.

## CORS

Preflight verificado:

- `OPTIONS /system/info`
- `Origin: https://cognitive.doctormanzur.com`
- Resultado: 200.
- `Access-Control-Allow-Origin: https://cognitive.doctormanzur.com`
- `Access-Control-Allow-Credentials: true`

## Localhost/public UI

- El HTML publico se sirve desde `https://cognitive.doctormanzur.com`.
- El contrato TestSprite sigue siendo: no requests reales desde UI publica a
  `localhost:8000` ni `127.0.0.1:8000`.
- El default publico agregado en Prompt 2 fuerza API publica cuando
  `window.location.hostname === cognitive.doctormanzur.com`.

## Forbidden actions

- No se ejecutaron writes reales en este runtime check.
- Validaciones previas TestSprite:
  - Mail UI read-only: PASS.
  - Mail API GET-only: PASS.
  - Dummy draft/send/DNS paths bloqueados/ausentes en reruns previos.
- En este prompt final, todo caso forbidden debe usar preview, GET-only, dummy
  blocked checks o OpenAPI inspection, nunca send/draft/DNS real.

## Estado

Runtime apto para TestSprite zero-defects loop.
