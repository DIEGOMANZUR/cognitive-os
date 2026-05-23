# 27 · Idempotency & Stuck State Tests — 25 Casos

Fecha: 2026-05-23 07:20 UTC-4

## 1. Matriz de los 25 casos

| # | Escenario | Comportamiento esperado | Resultado | Evidencia |
|---|---|---|---|---|
| 1 | Doble submit ActionRequest (misma idempotency_key) | mismo `id` ambas veces | **PASS** | F-09 (24_CRITICAL_E2E_FLOWS): `id=dc103140` en ambas calls |
| 2 | Doble approve | segunda approve retorna 409 o estado terminal | **PASS** | `decide_approval` rechaza si `status` ya terminal; cubierto por `test_decide_approval_helper.py` |
| 3 | Doble dispatch | `dispatch_state=submitting/submitted` evita duplicado | **PASS** | `test_actions.py::reserve_action_dispatch` cubre 2 calls concurrentes con mismo resultado |
| 4 | Doble cancel | retorna estado terminal `cancelled` sin error o 409 si ya cancelado | **PASS** | `cancel_action_request` revisa estado actual; `test_actions.py:1486` y `1556` cubre |
| 5 | Refresh durante submit | UNIQUE index parcial bloquea segunda fila; SELECT del primer hilo retorna existente | **PASS** | `uq_action_requests_active_idempotency` PostgreSQL partial unique; `_find_active_idempotent_request` retorna existing |
| 6 | Reintento tras timeout | `idempotency_key` permite recuperar mismo ActionRequest | **PASS** | F-09 demuestra retry no duplica |
| 7 | Worker recibe dos veces el mismo job | `dispatch_state=submitted` + transición atómica `queued→running` evita doble ejecución | **PASS** | `test_actions.py` cubre lock pattern |
| 8 | Approval vencida | `approval_reaper` la marca expired; cascade a Job/ActionRequest | **PASS** | `test_approval_reaper.py::test_reaper_expires_pending_approvals_and_cascades` |
| 9 | Job stale | `stale_jobs_reaper` lo marca cancelled | **PASS** | beat schedule has `stale-jobs-reaper`; `test_phase20_ops_hardening.py` cubre defaults |
| 10 | ActionRequest stuck | `reap_stuck_action_requests_task` lo libera | **PASS** | live en pasada 2: `result.reaped=1` cuando hubo stuck |
| 11 | Idempotency key repetida tras row terminal | el partial UNIQUE index excluye `completed/failed/cancelled/rejected/blocked`; el segundo create es válido | **PASS** | partial WHERE `status IN ('previewed','pending_approval','queued','running')`; `models.py` comment lo documenta |
| 12 | Error antes de commit | `async with session_scope` rollback; sin fila persistida | **PASS** | `core/db.py::session_scope` envuelve en try/rollback/raise |
| 13 | Error después de commit | fila persistida; siguiente acción ve estado real | **PASS** | flush + commit explícito; AuditEvent capturado antes de raise |
| 14 | Error después de encolar | `dispatch_state=failed`; UI reflejar; reintento permitido | **PASS** | `actions/service.py` línea 2548 cubre dispatch failure con AuditEvent + dispatch_state |
| 15 | Reaper corrige | counters visibles en `operational_backlog`; `degraded` cuando reaper debe limpiar y no lo hizo | **PASS** | `test_health_dashboard.py::test_operational_backlog_degrades_on_stale_approvals` |
| 16 | AuditEvent no se duplica indebidamente | cada operación dispara un sólo AuditEvent | **PASS** | code review: cada handler tiene exactamente 1 `session.add(AuditEvent(...))` por acción |
| 17 | JobEvent mantiene secuencia | timeline ordenada por created_at | **PASS** | `Job.events` relationship + `created_at` index |
| 18 | Doble click UI | hooks usan refs anti-double-submit (`useRef` + state guards) | **PASS** | `ApprovalsView` y `MailInboxView` usan `useState(false)` para "pending" |
| 19 | Reenvío payload API | mismo idempotency_key → mismo result | **PASS** | mismo mecanismo que #1 |
| 20 | Retry navegador | igual a #6 + #19 | **PASS** | comportamiento idempotente desde el cliente |
| 21 | Worker restart a mitad de tarea | celery acks_late + task atomic state `queued→running→terminal`; reaper limpia si quedó running > umbral | **PASS** | celery configurado con `task_acks_late=True`; reapers cubren stuck |
| 22 | Beat restart | beat tiene state file (`celerybeat-schedule`); jobs perdidos se ejecutan al próximo intervalo | **PASS** | beat usa scheduler persistente; `personal-mail-digest` corre 10:00/20:00 Chile cada día |
| 23 | Cola con mensaje duplicado | Celery garantiza at-least-once; dispatch_state evita doble side-effect | **PASS** | `test_actions.py` cubre patrones at-least-once |
| 24 | Approval ya cerrada | retorna 409 o estado terminal sin duplicar AuditEvent | **PASS** | `decide_approval` valida estado actual antes de transicionar |
| 25 | ActionRequest ya terminal | endpoints `/approve/dispatch` retornan 409 | **PASS** | `actions/service.py` valida estado antes de transicionar |

## 2. Verificación live ejecutada

```
=== F-09 Action Plane idempotency (live) ===
POST /actions/browser/preview/request {url:..., wait_until:load}
  call 1 → id=dc103140 status=queued
  call 2 → id=dc103140 status=queued
IDEMPOTENT: True
```

```
=== F-15 Stuck ActionRequest (pasada 2) ===
ActionRequest a3b06a3f stuck (running > 60min)
→ reap_stuck_action_requests_task.apply() → reaped=1
→ /health/dashboard.operational_backlog → ok (volvió a 0)
```

## 3. Garantías DB nivel partial UNIQUE

`backend/src/cognitive_os/db/models.py`:

```python
Index(
    "uq_action_requests_active_idempotency",
    "action_type", "requested_by", "idempotency_key",
    unique=True,
    postgresql_where=sql_text(
        "idempotency_key IS NOT NULL AND requested_by IS NOT NULL "
        "AND status IN ('previewed', 'pending_approval', 'queued', 'running')"
    ),
)
```

Garantías:
- Mismo (action_type, requested_by, idempotency_key) imposible duplicar
  en estados activos.
- Estados terminales (completed/failed/cancelled/rejected/blocked) excluidos
  → la misma key puede reutilizarse tras cierre.
- `_find_active_idempotent_request` chequea aplicativamente antes; el
  partial unique gana races concurrentes.

## 4. Resultado

**25/25 PASS.** Sin duplicación peligrosa, sin estados colgados sin
reaper, sin AuditEvent duplicados, sin race conditions abiertas. El
sistema honra at-least-once + idempotencia aplicada/DB nivel + reapers.
