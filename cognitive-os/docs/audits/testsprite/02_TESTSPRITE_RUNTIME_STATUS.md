# 02 - TestSprite Runtime Status

Fecha UTC: 2026-05-24T08:25:01Z
Auditoria: Cognitive OS - TestSprite initial full audit

## URLs bajo prueba

- Frontend publico: `https://cognitive.doctormanzur.com`
- Backend publico: `https://cognitive-api.doctormanzur.com`
- OpenAPI publico: `https://cognitive-api.doctormanzur.com/openapi.json`

## Launcher y stack

Se encontro launcher endurecido:

- `/home/jgonz/Escritorio/cognitive-os.sh`

Comandos ejecutados:

- `/home/jgonz/Escritorio/cognitive-os.sh status`
- `/home/jgonz/Escritorio/cognitive-os.sh doctor`

Resultado:

- Docker: running
- API local: running en `127.0.0.1:8000`
- Worker: running
- Beat: running
- Frontend local: running en `localhost:3001`
- Telegram: running
- Kimi WebBridge: running en `127.0.0.1:10086`

## Probes publicos

| Probe | Resultado |
| --- | --- |
| `GET https://cognitive.doctormanzur.com` | 200 |
| `GET https://cognitive-api.doctormanzur.com/health` | 200 |
| `GET https://cognitive-api.doctormanzur.com/openapi.json` | 200 |
| `GET https://cognitive-api.doctormanzur.com/docs` | 200 |
| `GET https://cognitive-api.doctormanzur.com/redoc` | 200 |
| `OPTIONS /system/info` con origin frontend publico | 200 |

`/health` devolvio:

```json
{"status":"ok","service":"cognitive-os"}
```

OpenAPI descargado en:

- `docs/audits/testsprite/cognitive-os-openapi.json`

Conteo observado:

- OpenAPI paths: 143
- Title: `Cognitive OS API`

## CORS

Preflight `OPTIONS /system/info` desde `https://cognitive.doctormanzur.com`:

- `access-control-allow-origin: https://cognitive.doctormanzur.com`
- `access-control-allow-credentials: true`
- methods incluyen `GET`, `POST`, `PATCH`, `PUT`, `DELETE`, `OPTIONS`

## JWT y auth

- JWT temporal disponible: si
- Archivo local: `/tmp/cognitive_os_testsprite_jwt.txt`
- Permisos: `0600`
- Valor completo: no incluido en reportes
- Mask: `eyJhbGciOiJI...188`

Backend protegido requiere:

```http
Authorization: Bearer <JWT>
```

## UI public API base

El HTML inicial publico contiene el placeholder/default `http://127.0.0.1:8000`
en el input `JWT local`/conexion antes de sembrar `localStorage`. Segun
`PRD_FRONTEND.md`, esto no es bug si despues del seed las requests reales usan:

```js
localStorage.setItem('cogos.api', 'https://cognitive-api.doctormanzur.com');
```

TestSprite debe validar durante E2E que, despues del seed:

- no haya fetch a `localhost:8000`;
- no haya fetch a `127.0.0.1:8000`;
- la UI use `https://cognitive-api.doctormanzur.com`.

## Cloudflare tunnel

`scripts/testsprite_web/status_testsprite_stack.sh` mostro:

- cloudflared running
- frontend publico 200
- backend publico `/health` 200

Ultimas lineas del log de tunnel incluyen requests canceladas a
`/health/dashboard` durante ejecuciones TestSprite previas. Esto es ruido de
cliente/tunnel si no se reproduce como fallo funcional con status final 5xx.

## Observacion posterior durante ejecucion

Durante las suites TestSprite, la UI publica mostro repetidamente:

```text
No se pudo activar el JWT local automatico. Detalle: Failed to fetch
```

Tambien se probo `POST https://cognitive-api.doctormanzur.com/auth/local-token`
como preparacion de runtime para evitar depender de filesystem local en el
sandbox de TestSprite. El request publico no devolvio respuesta antes de 12 s
(`curl --max-time 12`, status efectivo `000`). No se imprimio ningun token.

Interpretacion para triage: el endpoint publico `/health` y OpenAPI estan
disponibles, pero el flujo zero-friction de auto-token desde la UI publica no
quedo validado por TestSprite y aparece como causa probable de los fallos de
Health/MCP/metadata dinamica en UI/E2E.
