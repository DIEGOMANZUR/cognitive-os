# OpenChamber Cognitive OS

> **Estado V2.0 (2026-05-27, post cierre absoluto Prompt 7 V2.0).**
> Cognitive OS quedó certificado como **APTO COMERCIAL LOCAL-FIRST** para
> PC dedicado. Working tree limpio sobre commit V2.0 (`git log -1`). Gates V2.0:
> `full-qa.sh` **1232 passed**, `stress-qa.sh 5` **5/5 verde × 1232 × 2 ciclos**
> (flakiness 0%), `npx playwright test` **44 passed × 2 ciclos**,
> `full-qa-live.sh` **8 passed**, `openapi_readonly_smoke.py` **70/70**.
> Doc audit firmado: [`cognitive-os/docs/audits/FINAL_ABSOLUTE_V2_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md`](../audits/FINAL_ABSOLUTE_V2_COMMERCIAL_LOCAL_FIRST_CERTIFICATION.md).


> **Estado actual (2026-05-22):** OpenChamber sigue siendo acceso al cockpit
> de desarrollo, no al runtime productivo principal. Cognitive OS operativo
> corre en `cognitive-os/` y se documenta en `cognitive-os/docs/CURRENT_STATE.md`.
> La postura actual del proyecto es PC dedicado con baja fricción; este
> documento solo cubre el acceso web a OpenCode/OpenChamber.
>
> **Histórico (2026-05-15, 04:47 hora Chile):** acceso LAN para operar
> OpenCode sobre el workspace Cognitive OS. Sigue activo en
> `0.0.0.0:3000` por systemd de usuario (`openchamber-cognitive-os.service`)
> con OpenCode managed en `127.0.0.1:4095`. La contraseña de UI vive solo en
> configuración local/systemd o gestor de secretos; nunca en este Markdown.
> Verificado 2026-05-15: el servicio de usuario sigue habilitado y enabled
> con lingering, y el wrapper `~/.local/bin/openchamber-cognitive-os` carga
> el workspace correcto automáticamente.

OpenChamber is installed as `@openchamber/web` and exposed through the wrapper
`~/.local/bin/openchamber-cognitive-os`.

## Start

```bash
systemctl --user start openchamber-cognitive-os.service
```

The service is enabled for the user and user lingering is enabled, so it can
come back after login/session restarts.

Open from this machine:

```text
http://localhost:3000
```

Open from phone/tablet on the same LAN:

```text
http://192.168.1.28:3000
```

Tailscale/VPN address detected during setup:

```text
http://100.122.143.80:3000
```

Credencial UI: configurada localmente fuera de este documento. Si se pierde,
revisar el servicio de usuario o el archivo local ignorado que cargue
OpenChamber; no guardar la contraseña real en Markdown versionado.

## Behavior

- OpenChamber binds to `0.0.0.0:3000` for LAN access.
- OpenChamber launches OpenCode through `~/.local/bin/opencode`.
- The OpenCode wrapper forces the Cognitive OS workspace and exports the MCP
  credentials required by the configured servers.
- OpenCode is managed on localhost port `4095`.
- OpenChamber's active project is set to `Cognitive OS` pointing at the workspace
  root.

## Commands

```bash
systemctl --user status openchamber-cognitive-os.service
systemctl --user restart openchamber-cognitive-os.service
systemctl --user stop openchamber-cognitive-os.service
journalctl --user -u openchamber-cognitive-os.service -f
```

## Validation

```bash
opencode mcp list
curl -I http://127.0.0.1:3000
curl -fsS http://127.0.0.1:3000/health
```
