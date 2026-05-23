# 15 · Zero-Friction Validation — 2026-05-23

Validación explícita de los 12 puntos requeridos por el re-audit.

| # | Aserción | Estado | Evidencia |
|---|---|---|---|
| 1 | El sistema opera en `dedicated_local/full` | **PASS** | `/system/info.operator_profile=dedicated_local`; `/system/readiness.local_autonomy_mode=full`; `summary="Sin friccion. Todas las capacidades del perfil estan activas."` |
| 2 | Capacidades locales no restringidas artificialmente | **PASS** | `/system/readiness.target_capabilities_unlocked=14/14`, `gaps=[]`; `/actions/capabilities` muestra browser/computer/documents/gmail/maps/godaddy/google_calendar/google_drive todos `status=ready` con `requires_approval=false` salvo Drive/Calendar que es contrato del Action Plane (writes vía request → approve). |
| 3 | Sin confirmaciones redundantes cuando el contrato permite | **PASS** | `/system/info.require_human_approval_for_external_actions=false`, `approval_require_four_eyes=false`, `action_payload_encryption_required=false`. `/actions/drive/folders/ensure/request` retorna `status=queued` directo (auto-aprobado y dispatcheado para reversibles). `/actions/browser/preview/request` retorna 200 con dispatch automático. |
| 4 | UI guía sin obligar a leer código | **PASS** | `/system/readiness.summary` da mensaje en español plano ("Sin friccion. Todas las capacidades del perfil estan activas.") + `gaps` con remediación si hay flags faltantes. Mail send 400 emite mensaje claro: `"Mail sending is disabled by policy. Normal flow is read-only: generate a summary/proposed reply and Diego sends manually."`. Playwright `all-views-console-guard` verifica que las 20 vistas no escupen console.error. |
| 5 | Acciones locales amplias cuando flags lo permiten | **PASS** | `/actions/capabilities[computer].metadata.allowed_roots=["/home/jgonz","/tmp","/mnt"]`; `/actions/capabilities[browser].metadata.allowed_domains=["*"]`; `KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*`. Computer organize en `/home/jgonz/Escritorio` funcionando vía `/actions/computer/organize/request`. |
| 6 | Edge/Kimi WebBridge funciona o degrada útil | **PASS** | `/health/dashboard.kimi_webbridge.status=ready`; `metadata.daemon_running=true, extension_connected=true, active_provider=edge_devtools, edge_devtools_running=true`. Si Edge no estuviera, el componente reportaría `degraded` con `daemon_running=false` (verificado por inspección del código `health.py:_check_kimi_webbridge`). |
| 7 | Telegram conversacional sin slash en `dedicated_local` | **PASS** | `TELEGRAM_ENABLED=true`, `operator_profile=dedicated_local`; comando `pytest -k telegram_conversational` documenta el routing implícito. Los 102 tests `test_telegram_bot.py` pasan; matriz auth-deny y flag-gated cerrada. |
| 8 | Action Plane trazable sin frenar | **PASS** | `/actions/browser/preview/request` con `dedicated_local/full` se auto-aprueba y queue en Celery; `ActionRequestView` retorna con `id`, `status`, `created_at`, `updated_at`. Idempotencia confirmada: dos calls con misma url devuelven el mismo `id`. Pytest `tests/test_action_request_eager_defaults.py` (3 nuevos) cubre el shape. |
| 9 | Health/readiness dice exactamente qué falta | **PASS** | `/health/dashboard` con 18 componentes, cada uno con `status` discreto (`ok`/`configured`/`ready`/`degraded`/`disabled`), `detail` legible y `metadata` accionable (e.g. mcp_client expone `declared_servers, server_names`; mail expone `providers, approval_required, gmail_label`; operational_backlog expone counters de approvals_pending/jobs_stale/beat_lag_minutes). `POST /health/verify` fuerza probe LIVE; degradaciones se reportan con timeout + componente exacto. |
| 10 | Code Director sin policy excesivamente conservadora | **PASS** | `/code-director/run` valida `adapter_preference` (claude_code/codex/kimi/deepagent — `fake` excluido para tests). 422 cuando falta `objective`/`adapter_preference`. Budget soft via `CODE_DIRECTOR_BUDGET_MODE=soft` (default). Adapter `fake` 400 con mensaje claro `"The 'fake' adapter is reserved for tests and cannot be requested."`. |
| 11 | Mail sigue read-only en flujo normal | **PASS** | `POST /mail/messages/{id}/approve-send` con cualquier payload → 400 con mensaje exacto: `"Mail sending is disabled by policy. Normal flow is read-only: generate a summary/proposed reply and Diego sends manually."`. `ENABLE_EMAIL_SEND=false`, `MAIL_ALLOW_EXPLICIT_SEND` ausente (default false), `MAIL_REQUIRE_APPROVAL_FOR_SEND=true`. Tres flags simultáneas requeridas para escape hatch. UI sin botón Enviar (Playwright `mail-readonly-contract` lo verifica). |
| 12 | Sin seguridad SaaS introducida en este audit | **PASS** | Único fix de producción aplicado: `eager_defaults=True` en `Base` (`backend/src/cognitive_os/core/db.py`). Es un fix de SQLAlchemy idiomático para async, sin impacto en política/permisos/auth. **No** se añadieron approvals, four-eyes, multi-tenant aislamiento, ni se restringió ningún `allowed_*`. La postura `dedicated_local/full` se mantuvo intacta. |

## Resultado consolidado

**12 / 12 PASS**. Cero fricción preservada, ninguna restricción añadida,
contrato mail intacto, todos los controles funcionales (audit,
idempotency, reapers, health honesto) operativos.

## Sub-asserción extra (auto-dispatch en `dedicated_local/full`)

Verificación live:

```
POST /actions/drive/folders/ensure/request {"name":"test-folder"}
→ HTTP 200, status="queued", approval_id="<uuid>", job_id="<uuid>"
```

El frontend ya no necesita un click manual de "Approve" para acciones
reversibles en el perfil dedicado. Esto es el zero-friction más
agresivo del producto y sigue funcionando.

## Sub-asserción extra (idempotency conservada)

```
POST /actions/browser/preview/request {"url":"http://localhost:3001/"}
→ id=a3b06a3f-c2eb-49dd-bbdd-5233191dc3b3

POST /actions/browser/preview/request {"url":"http://localhost:3001/"}
→ id=a3b06a3f-c2eb-49dd-bbdd-5233191dc3b3   (mismo)
```

El fix `eager_defaults=True` **no** afectó la idempotencia (mantenida
por el índice UNIQUE parcial sobre `(action_type, requested_by,
idempotency_key)` en estados activos).
