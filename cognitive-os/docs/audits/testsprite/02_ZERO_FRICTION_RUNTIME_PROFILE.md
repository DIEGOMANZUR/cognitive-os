# 02 · Zero-Friction Runtime Profile

Fecha: 2026-05-23
Target: `dedicated_local/full`, mail read-only, MCP habilitado, Kimi require-approval (mutaciones), GoDaddy dry-run forzado.

## 1. Variables esperadas vs reales

| Variable | Esperado | Real (`.env`) | Estado |
|---|---|---|---|
| `OPERATOR_PROFILE` | `dedicated_local` | `dedicated_local` | ✅ |
| `LOCAL_AUTONOMY_MODE` | `full` | (default `full`) | ✅ |
| `CODE_DIRECTOR_BUDGET_MODE` | `soft` | (default `soft`) | ✅ |
| `MAIL_BACKGROUND_SYNC_ENABLED` | `false` (no auto-sync) | (default `false`) | ✅ |
| `MAIL_ALLOW_EXPLICIT_SEND` | `false` | (no presente → `false`) | ✅ |
| `MAIL_REQUIRE_APPROVAL_FOR_SEND` | `true` | `true` | ✅ |
| `ENABLE_EMAIL_SEND` | `false` | (no presente → `false`) | ✅ |
| `GODADDY_DNS_DRY_RUN_ONLY` | `true` | `true` | ✅ |
| `GODADDY_ALLOW_PRODUCTION_WRITES` | `false` | (no presente → `false`) | ✅ |
| `TELEGRAM_ENABLED` | `true` | `true` | ✅ |
| `KIMI_WEBBRIDGE_REQUIRE_APPROVAL` | `true` (mutaciones) | `true` | ✅ |
| `KIMI_WEBBRIDGE_ALLOW_MUTATIONS` | `false` | `false` | ✅ |
| `KIMI_WEBBRIDGE_ALLOWED_DOMAINS` | `*` (local) | `*` | ✅ |
| `ENABLE_MCP_CLIENT` | `true` | `true` | ✅ |
| `MCP_INVENTORY_TIMEOUT_SECONDS` | `30` | (default 30 en HEAD) | ✅ (binario en runtime aún tiene 10 — ver §4) |
| `LIVE_TESTS_ENABLED` | opt-in | (no presente) | ✅ (no se ejecutarán live tests por defecto) |

## 2. Endpoints verificados en vivo

```
GET  /health                  → {"status":"ok","service":"cognitive-os"}
POST /auth/local-token        → JWT con roles=[admin, operator], TTL 10 años
GET  /system/info             → operator_profile="dedicated_local", git_commit="2c3cff6dfccf"
GET  /system/readiness        → operator_profile=dedicated_local, local_autonomy_mode=full,
                                 target_capabilities_unlocked=14/14, gaps=[]
GET  /system/mcp              → enabled=true, 5 servers (mem/gh/fs/cc/gem), 67 tools totales
GET  /health/dashboard        → 18 componentes, overall=configured (LLM/embeddings/mail/mcp_client
                                 cableados-pero-no-probados; resto ok/ready)
```

## 3. Cómo cambia respecto de `strict`

En `dedicated_local/full` (observado en endpoints):

- `require_human_approval_for_external_actions: false`
- `approval_require_four_eyes: false`
- `approval_pending_max_hours: 168`
- `action_payload_encryption_required: false`
- `/auth/local-token` disponible (en `strict` retorna 403).

Los reapers, idempotencia, audit y `operational_backlog` siguen iguales en
los dos perfiles — no son negociables.

## 4. Drift runtime vs HEAD

`/system/info.git_commit = 2c3cff6` y HEAD = `9b22f77`. Cambios de código
relevantes que **no** están en el binario en RAM:

- `core/config.py` — `MCP_INVENTORY_TIMEOUT_SECONDS` default 10 → 30s.
- `mcp_client.py` — inventario paralelo.
- `frontend/.next` reconstruido el 2026-05-22 22:26 (incluye `hooks.ts`
  capture-phase fix → SI está cargado, porque `BUILD_ID` es posterior al
  commit `5953b40`).

**Acción tomada en este audit:** los gates pytest/Playwright leen del
filesystem, así que prueban HEAD. El TestSprite contra `:3001` y `:8000`
prueba el binario en RAM (uvicorn). Confirmado en runtime: el efecto
observable de los fixes (MCP 5/5 paralelo, command palette `Ctrl/K`) sigue
funcionando — el binario antiguo ya soportaba el comportamiento; las
mejoras son adicionales/de performance.

**Recomendación de cierre:** reiniciar `uvicorn`/`next start` antes de la
auditoría final SOLO si se quiere capturar `git_commit=9b22f77` en
`/system/info`. No es un blocker funcional.

## 5. Controles que siguen vivos

- `AuditEvent`, `JobEvent`, `ActionRequest` activos.
- Idempotencia DB + aplicativa.
- Reapers en beat schedule (always-on).
- `operational_backlog` health component activo (status `ok`).
- Tests herméticos (DB `cognitive_os_test` aislada).
- Telegram fail-closed (allowlist no vacía).
- `.next-qa` build aislado para QA.

## 6. Aprobaciones que se auto-resuelven

- Browser preview/interactive (en allow-list de dominios).
- Computer organize/inventory (en `COMPUTER_ALLOWED_ROOTS`).
- Document generate (DOCX/XLSX/PPTX con guardrails OK).
- Gmail digest (sólo lectura, sin send).
- Google Maps geocode/route (read-only).
- Google Calendar freebusy (read-only); create event sigue siendo
  preview-first + request.
- Google Drive search/folder/upload/organize/request (con allow-list).
- Code Director sub-acciones bajo budget soft.

## 7. Aprobaciones que SIGUEN explícitas (no negociables)

- Mail `approve-send` (4 condiciones simultáneas).
- GoDaddy DNS real (`GODADDY_DNS_DRY_RUN_ONLY=false` + dominio allow-listed +
  approval + `GODADDY_ALLOW_PRODUCTION_WRITES=true`).
- Kimi WebBridge mutaciones (`click/fill/evaluate/close`) bajo
  `KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true`.
- Skill promotion (proposal del aprendizaje autónomo).

## 8. Conclusión

Runtime alineado con `ZERO_FRICTION_OPERATING_MODEL.md`. No se detectan
fricciones residuales en `.env` ni en `/system/readiness`. Mail respeta el
contrato. La auditoría procede con esta postura.
