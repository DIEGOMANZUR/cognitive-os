# 02 — Zero Friction Runtime Profile

Fecha: **2026-05-25** | Commit: `6891d5c`

## Variables esperadas (canónico)

```env
OPERATOR_PROFILE=dedicated_local
LOCAL_AUTONOMY_MODE=full
CODE_DIRECTOR_BUDGET_MODE=soft
MAIL_ALLOW_EXPLICIT_SEND=false
ENABLE_EMAIL_SEND=false
```

## Variables reales (.env + runtime)

| Variable | Esperado | Real | Fuente |
|---|---|---|---|
| OPERATOR_PROFILE | dedicated_local | dedicated_local | `.env`, `/system/info` |
| LOCAL_AUTONOMY_MODE | full | full | `.env` |
| CODE_DIRECTOR_BUDGET_MODE | soft | soft | `.env` |
| require_human_approval_for_external_actions | false | false | `/system/info` |
| approval_require_four_eyes | false | false | `/system/info` |

## Readiness vivo

```
GET /system/readiness → target_capabilities_unlocked: 14/14, gaps: []
```

## Flujos que cambian vs `strict`

| Flujo | dedicated_local/full | strict |
|---|---|---|
| JWT Playwright | auto-mint `_global-setup.ts` | COGOS_JWT manual |
| browser_preview request | auto-approve + dispatch | pending approval |
| computer_organize | auto-approve en full | approval manual |
| Telegram sin slash | conversacional | solo slash |
| Filesystem PC | amplio `/home/jgonz` | restringido |

## Aprobaciones auto-resueltas (contrato)

Reversibles en full: browser_preview, browser_interactive, computer_organize, document_generate, drive_ensure_folder, drive_organize_files (cuando servicio ready).

**No auto-send mail.** SMTP sigue triple gate.

## Controles que siguen vivos

- ActionRequest + JobEvent + AuditEvent
- Idempotency keys
- Reapers cada 10–15 min
- Health honesto configured vs verified
- operational_backlog degraded cuando reaper falla

## Gaps operativos (no código)

- Google Calendar/Drive pueden mostrar `blocked` si OAuth scope drift → operador re-corre `scripts/auth_google.py`
- ~310 approvals pending acumuladas → triage operador (reaper OK, ninguna stale >48h)

## Evidencia runtime Prompt 1

- `POST /auth/local-token` → OK
- `POST /actions/browser/preview/request` example.com → `status=completed`, `title=Example Domain`
- Frontend :3001 HTTP 200, API :8000 UP
