# TestSprite Web Portal Tunnel Setup — Cognitive OS

**Date:** 2026-05-23
**Operator:** Diego Manzur
**Branch:** codex/commercial-zero-friction-hardening
**HEAD:** d25af91a2256662df36a4e675d2ad1e771b5f936

## Estado final

**PASS** — stack local levantado, Cloudflare Tunnel activo, ambos hostnames
públicos responden 200, JWT admin probado contra el endpoint público, safety
flags peligrosos en estado seguro (no-send / dry-run).

## URLs públicas

| Tipo      | URL                                            | Local backing            |
|-----------|-----------------------------------------------|--------------------------|
| Frontend  | `https://cognitive.doctormanzur.com`           | `http://127.0.0.1:3001`  |
| Backend   | `https://cognitive-api.doctormanzur.com`       | `http://127.0.0.1:8000`  |

## Servicios locales

| Servicio    | Puerto / proceso                                                |
|-------------|------------------------------------------------------------------|
| Postgres    | Docker `cognitive_os_postgres` :5432                             |
| Redis       | Docker `cognitive_os_redis` :6379                                |
| Weaviate    | Docker `cognitive_os_weaviate` :8081                             |
| Neo4j       | Docker `cognitive_os_neo4j` :7475/:7688                          |
| Backend     | `uvicorn cognitive_os.api.app:app` 127.0.0.1:8000                |
| Worker      | `celery worker` (default,ingestion,agent_longrun,maintenance,mail)|
| Beat        | `celery beat`                                                    |
| Frontend    | `next start -p 3001`                                             |
| Cloudflared | `cloudflared tunnel run cognitive-os-testsprite`                 |

## Cloudflare Tunnel

- **Nombre:** `cognitive-os-testsprite`
- **Tunnel UUID:** `e6f9038c-460d-4a4a-bbfc-5c6fe8f2b572`
- **Config:** `~/.cloudflared/cognitive-os-testsprite.yml`
- **Credentials JSON:** `~/.cloudflared/e6f9038c-460d-4a4a-bbfc-5c6fe8f2b572.json` (no leído por este reporte)
- **Hostnames publicados:**
  - `cognitive.doctormanzur.com` → `http://localhost:3001`
  - `cognitive-api.doctormanzur.com` → `http://localhost:8000`
- **Conexiones registradas:** 4 (gru13, gru07, scl06×2) protocolo `quic`.
- **Catch-all:** `http_status:404` (un host no listado responde 404, no expone otros servicios locales).

## DNS routes

Las dos rutas CNAME fueron **creadas** durante este setup. La primera invocación
quedó apuntando al túnel `vibeasus-rc` (porque `~/.cloudflared/config.yml`
forzaba ese tunnel por defecto); se corrigió con `cloudflared tunnel route dns
-f <UUID> <hostname>` para sobre-escribir al tunnel correcto. Estado final:
ambos CNAMEs apuntan a `e6f9038c-460d-4a4a-bbfc-5c6fe8f2b572`.

## Variables frontend

La variable que el frontend lee en runtime es `NEXT_PUBLIC_API_BASE_URL`
(consumida en `frontend/app/page.tsx:130`). Se materializó así:

- Build-time: `NEXT_PUBLIC_API_BASE_URL=https://cognitive-api.doctormanzur.com` (el
  script de start la inyecta).
- Persistido en `frontend/.env.local`.
- El `useEffect` del componente raíz pisa el valor de `localStorage` `cogos.api`
  al cargar la página, de modo que cualquier usuario nuevo termina apuntando al
  backend público sin tocar el TopBar.

**Detalle conocido (no bloqueante):** el bundle JS sigue conteniendo el literal
`http://127.0.0.1:8000` en dos lugares — el placeholder del input del
TopBar y el valor inicial del estado de `useLocalState` — antes de que el
`useEffect` lo sobre-escriba. Esto NO produce llamadas a localhost en
runtime para la sesión pública (el efecto corre en el primer render y
fija la URL pública); es estético en la UI de Settings.

## CORS

Se añadió `https://cognitive.doctormanzur.com` a `CORS_ALLOW_ORIGINS` en `.env`
(backup `.env.bak.testsprite_tunnel.<ts>` antes del cambio). Lista actual:

```
http://localhost:3001,
http://127.0.0.1:3001,
http://localhost:3000,
http://127.0.0.1:3000,
https://cognitive.doctormanzur.com
```

`allow_credentials=True`. No se introduce el wildcard `*` (rechazado por el
validator `validate_cors_allow_origins`).

## Safety flags (QA window)

Verificadas en `.env`:

| Flag                              | Valor    | Default si ausente |
|----------------------------------|----------|--------------------|
| `ENABLE_EMAIL_SEND`              | `false`  | —                  |
| `MAIL_ALLOW_EXPLICIT_SEND`       | (ausente) | `false`           |
| `GODADDY_DNS_DRY_RUN_ONLY`       | `true`   | —                  |
| `GODADDY_ALLOW_PRODUCTION_WRITES`| `false`  | —                  |
| `TOOLS_READONLY_MODE`            | `true`   | —                  |
| `ENABLE_BROWSER_AUTOMATION`      | `false`  | —                  |
| `ALLOW_DANGEROUS_TOOLS`          | `false`  | —                  |

→ ninguna acción destructiva externa puede dispararse durante la ventana QA.
No se enviarán correos ni se modificará DNS en GoDaddy aunque TestSprite intente
disparar esos flujos.

## JWT temporal

- **Archivo local:** `/tmp/cognitive_os_testsprite_jwt.txt`
- **Permisos:** `600`
- **Roles:** `["admin"]`, `sub="1"` (coincide con `ADMIN_USER_IDS=1`).
- **Vencimiento:** 8 horas desde su emisión.
- **Validado contra:** `https://cognitive-api.doctormanzur.com/system/info` → HTTP 200, `/system/readiness` → HTTP 200.

Para regenerarlo:

```bash
cd backend
uv run python -c "
from datetime import timedelta
from cognitive_os.core.auth import create_access_token
print(create_access_token(user_id='1', roles=['admin'], expires_delta=timedelta(hours=8)))
" > /tmp/cognitive_os_testsprite_jwt.txt
chmod 600 /tmp/cognitive_os_testsprite_jwt.txt
```

## OpenAPI

Snapshot público guardado:
- `docs/audits/testsprite/cognitive-os-openapi.json` (≈ 183 KB, 140 paths)

## Scripts creados

- `scripts/testsprite_web/start_testsprite_stack.sh`
- `scripts/testsprite_web/stop_testsprite_stack.sh`
- `scripts/testsprite_web/status_testsprite_stack.sh`
- `scripts/testsprite_web/README.md`

## Comandos para usar

```bash
# Levantar todo (idempotente, mata orphans de runs anteriores):
bash scripts/testsprite_web/start_testsprite_stack.sh

# Ver estado:
bash scripts/testsprite_web/status_testsprite_stack.sh

# Detener (deja Docker arriba):
bash scripts/testsprite_web/stop_testsprite_stack.sh
```

## Qué poner en TestSprite Web Portal

**UI project:**
- URL: `https://cognitive.doctormanzur.com`
- Auth: pegar el JWT de `/tmp/cognitive_os_testsprite_jwt.txt` en el TopBar
  (campo "Token") cuando el portal abra la app.
- PRD: `docs/audits/testsprite/COGNITIVE_OS_TESTSPRITE_PRD.md`

**API project:**
- Base URL: `https://cognitive-api.doctormanzur.com`
- Auth header: `Authorization: Bearer <JWT>` desde
  `/tmp/cognitive_os_testsprite_jwt.txt`
- OpenAPI: `docs/audits/testsprite/cognitive-os-openapi.json`

## Validaciones realizadas

| Validación                                                     | Resultado |
|----------------------------------------------------------------|-----------|
| `cloudflared --version` (instalado, autenticado)               | OK        |
| `cloudflared tunnel ingress validate`                          | OK        |
| `cloudflared tunnel route dns` (frontend hostname)             | OK (force-overwrite) |
| `cloudflared tunnel route dns` (api hostname)                  | OK (force-overwrite) |
| `curl http://127.0.0.1:8000/health`                            | 200       |
| `curl http://127.0.0.1:3001/`                                  | 200       |
| `curl https://cognitive-api.doctormanzur.com/health`           | 200       |
| `curl https://cognitive.doctormanzur.com/`                     | 200       |
| `curl https://cognitive-api.doctormanzur.com/openapi.json`     | 200, 140 paths |
| `curl -H "Authorization: Bearer …" /system/info` (público)     | 200       |
| `curl -H "Authorization: Bearer …" /system/readiness` (público)| 200       |
| Frontend HTML servido por túnel hace fetch a localhost?        | NO (en runtime; sólo aparece en placeholder estático del TopBar) |
| CORS_ALLOW_ORIGINS incluye `https://cognitive.doctormanzur.com`| YES       |
| Safety flags peligrosos                                        | OFF/dry-run |

## Problemas encontrados durante el setup

1. **DNS route apuntó al túnel equivocado al primer intento.** `~/.cloudflared/config.yml`
   declara `tunnel: c2b0b7a3-…` (vibeasus-rc) y eso ganaba sobre el argumento
   posicional. Corregido con `route dns -f <UUID-correcto>`.
2. **Beat lockfile residual.** Un beat de una sesión previa había dejado
   `backend/celerybeat-schedule` bloqueado; el start script ahora lo borra
   antes de relanzar.
3. **Tracking de PIDs frágil.** `nohup bash -c "..."` deja el wrapper bash
   como PID registrado, pero éste sale apenas el child arranca y `next-server`
   reparenta a init. El script `stop` ahora usa grupos de procesos
   (`setsid` + `kill -- -<pgid>`) y, para el frontend, identifica el proceso
   por el puerto :3001 vía `ss -tlnp`. El `status` reporta por pgrep / por
   puerto, no por pidfile.

## Correcciones aplicadas

- Añadido `https://cognitive.doctormanzur.com` a `CORS_ALLOW_ORIGINS` en `.env`.
- `frontend/.env.local` creado con `NEXT_PUBLIC_API_BASE_URL=https://cognitive-api.doctormanzur.com`.
- Frontend re-construido (`next build`) con la URL pública embebida.
- Scripts hardenizados con `setsid` + identificación por puerto.

## Pendientes

- (Cosmético) Eliminar literal `http://127.0.0.1:8000` del placeholder y del
  default inicial de `useLocalState("cogos.api", …)` en `frontend/app/page.tsx`
  para que el bundle público no contenga referencias estáticas a localhost.
  Funcionalmente no bloquea TestSprite porque el `useEffect` pisa el valor en
  el primer render.
- Apagar el túnel cuando termine la ventana QA:
  `bash scripts/testsprite_web/stop_testsprite_stack.sh`.
