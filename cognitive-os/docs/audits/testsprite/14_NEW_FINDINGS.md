# 14 · New Findings — Re-Audit 2026-05-23

> Hallazgos descubiertos en esta segunda pasada. Todos corregidos en
> sitio salvo nota explícita.

---

## TS-ZF-20260523-006 · P1 · `_view()` lazy-load 500 MissingGreenlet

### Detalle

- **Superficie:** `backend/src/cognitive_os/actions/service.py::_view()` y
  todos los call-sites tras `await session.flush()` en
  `create_*_request` (browser_preview, computer_organize, drive_*,
  document_generate, calendar_create_event, etc.).
- **Contrato esperado:** `POST /actions/browser/preview/request` con
  payload válido debe devolver `200` y un `ActionRequestView` con
  `updated_at` poblado.
- **Comportamiento real (antes del fix):**

  ```
  POST /actions/browser/preview/request {"url":"http://localhost:3001/"}
  → HTTP 500 Internal Server Error
  ```

  Log de uvicorn:
  ```
  File ".../actions/service.py", line 1029, in create_browser_preview_request
    view = _view(action_request)
  File ".../actions/service.py", line 2267, in _view
    updated_at=action_request.updated_at,
  sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
  can't call await_only() here. Was IO attempted in an unexpected place?
  ```

- **Evidencia:** capturado en
  `/home/jgonz/.cognitive-os/logs/api.log` línea 3130 / 3281 (durante
  re-audit del 2026-05-23 05:09 UTC-4). Reproducido aislado con
  `/tmp/repro_bp.py`.

- **Reproducción exacta (antes del fix):**

  ```bash
  curl -m 10 -sw "\nHTTP=%{http_code}\n" \
       -X POST "http://127.0.0.1:8000/actions/browser/preview/request" \
       -H "Authorization: Bearer $JWT" \
       -H "Content-Type: application/json" \
       -d '{"url":"https://example.com"}'
  ```

- **Causa raíz:**

  - `ActionRequest.updated_at` está definido con `server_default=func.now()`
    en `TimestampMixin` (`db/models.py:36`).
  - Sin `eager_defaults=True` en el `Base` ORM, SQLAlchemy 2.x **no**
    incluye `RETURNING updated_at` en el INSERT.
  - Después de `await session.flush()`, leer `action_request.updated_at`
    desde Python dispara un lazy refresh via SQL síncrono → en un
    `AsyncSession` con `asyncpg` esto necesita un greenlet activo, que
    no existe porque el frame es código async normal sin
    `await session.execute(...)`. Resultado: `MissingGreenlet`.

- **Por qué pytest no lo cazó:**

  - El test único del endpoint
    (`test_browser_preview_request_endpoint_uses_action_service`)
    monkeypatchea `ActionRequestService` con `FakeActionRequestService` que
    retorna un `ActionRequestView` pre-construido — el code path real
    nunca corre contra DB en CI.
  - Los tests que sí usan el servicio real (`test_drive_*_request`)
    monkeypatchean `session_scope` con `_FakeActionRequestSession.flush()`
    que **manualmente popula `updated_at` después del add** (línea 87:
    `if getattr(obj, "updated_at", None) is None: obj.updated_at = now`).
    Eso oculta el bug en pytest pero no lo arregla en producción.

- **Impacto en cero fricción:** **alto**. El endpoint
  `/actions/browser/preview/request` es la entrada principal del Action
  Plane para previewing browser navigations. Estaba 100% roto en
  runtime real.

- **Fix aplicado:**

  ```python
  # backend/src/cognitive_os/core/db.py
  class Base(DeclarativeBase):
      metadata = MetaData(naming_convention=NAMING_CONVENTION)
      __mapper_args__ = {"eager_defaults": True}  # ← nuevo
  ```

  Con `eager_defaults=True` SQLAlchemy 2.x emite `RETURNING <cols>` para
  todas las columnas con `server_default` en INSERT y UPDATE, así
  `created_at` y `updated_at` quedan poblados inmediatamente tras
  `flush()` sin necesidad de lazy refresh. Esto es la guía oficial para
  async sessions con asyncpg.

- **Verificación post-fix:**

  ```bash
  curl -m 10 -sw "\nHTTP=%{http_code}\n" \
       -X POST "http://127.0.0.1:8000/actions/browser/preview/request" \
       -H "Authorization: Bearer $JWT" \
       -H "Content-Type: application/json" \
       -d '{"url":"http://localhost:3001/"}'
  # → HTTP 200, payload con id, status, updated_at, created_at populados.
  ```

  Idempotencia conservada: dos llamadas idénticas devuelven el mismo
  `id` (`a3b06a3f-c2eb-49dd-bbdd-5233191dc3b3` en ambas).

- **Test de regresión:**
  `backend/tests/test_action_request_eager_defaults.py` — **3 tests
  nuevos** que corren contra la DB real `cognitive_os_test`:

  1. `test_action_request_updated_at_is_eager_loaded_after_flush` —
     valida directamente sobre `session_scope()` que `updated_at` se
     pueda leer post-flush sin raise.
  2. `test_browser_preview_request_endpoint_returns_200_against_real_db`
     — hits el endpoint a través del `ActionRequestService` real (no
     mock).
  3. `test_service_create_browser_preview_request_returns_view_with_updated_at`
     — invoca el servicio directo y valida el shape devuelto.

  Los 3 corren en el carril hermético (no `pytest.mark.integration`)
  y suben el total backend de 944 → **947 passed**.

- **Severidad final:** **P1**.
- **Estado:** ✅ **Resuelto y verificado**.

### Otros endpoints potencialmente afectados (auditados)

Todos los `create_*_request` que llaman `_view(action_request)` tras
flush quedan automáticamente arreglados por la misma mutación
`eager_defaults=True`. Verificación live durante el re-audit:

| Endpoint | Antes (esperado) | Después (live) |
|---|---|---|
| `/actions/browser/preview/request` | 500 ✗ | **200** ✓ |
| `/actions/browser/interactive/request` | 500 (posible) | **200** ✓ |
| `/actions/computer/organize/request` | 500 (posible) | **200** ✓ |
| `/actions/drive/folders/ensure/request` | 500 (posible) | **200** ✓ |
| `/actions/documents/request` | 500 (posible) | **200** ✓ |

---

## Otras observaciones (no son hallazgos por contrato)

### A. `auth.spec.ts:18` — auto-provision UI

El frontend ya autoprovisiona JWT desde `/auth/local-token` cuando no
hay token en `localStorage`. Esto es **producto**, no un bug — es el
contrato `dedicated_local/full`. Documentado en `auth.spec.ts:18`.

### B. `/code-director/run` exige `adapter_preference`

422 cuando se omite. Es validación correcta de Pydantic. No es bug.

### C. `/code-director/run` rechaza `fake` adapter en producción

HTTP 400 con mensaje `"The 'fake' adapter is reserved for tests and
cannot be requested."`. Es contrato. No es bug.

### D. `health/verify` → `degraded` por timeout LLM 3s

El componente `primary_llm` reportó `degraded` porque su probe
sintético del LLM excedió 3s (probable cold start del gateway local
`gpt-5.5`). El operador puede reintentar `POST /health/verify` o
ajustar `HEALTH_LLM_PROBE_TIMEOUT_SECONDS`. No es bug funcional —
mail GoDaddy IMAP login OK, embeddings live OK.

### E. Idempotency confirmada

`/actions/browser/preview/request` con misma `url` devuelve el mismo
`id` en llamadas sucesivas. El índice parcial UNIQUE
`(action_type, requested_by, idempotency_key)` sigue funcionando.

### F. Mail send sigue bloqueado

`POST /mail/messages/{id}/approve-send` sin flags → 400 con detalle:
`"Mail sending is disabled by policy. Normal flow is read-only:
generate a summary/proposed reply and Diego sends manually."`. ✓

### G. `KIMI_WEBBRIDGE_ALLOW_MUTATIONS=false`

Mantiene mutaciones bloqueadas pese a `KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*`.
✓ — combinación correcta para zero-friction sin daño accidental.

### H. Operational backlog

`/health/dashboard.components[operational_backlog]` = `ok` con
`approvals_pending=311, approvals_stale=0, jobs_stale=0,
action_requests_stuck=0, beat_lag_minutes=0.0`. Los reapers están
trabajando.

---

## Conteo final

| Severidad | Hallazgos nuevos | Estado |
|---|---|---|
| P0 | 0 | — |
| P1 | **1** (TS-ZF-20260523-006) | ✅ Resuelto + 3 tests de regresión |
| P2 | 0 | — |
| P3 | 0 | — |
| Info | 8 observaciones | n/a |

Tests agregados: 3 (`test_action_request_eager_defaults.py`).
Tests modificados: 0.
Archivos de producción modificados: 1
(`backend/src/cognitive_os/core/db.py` → `eager_defaults=True` en `Base`).
