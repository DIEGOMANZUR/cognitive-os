# 20 - TestSprite Zero Defects Fix Loop

Fecha UTC: 2026-05-24

## Loop 1

### Suites ejecutadas

| Suite | Resultado |
|---|---|
| UI Total / E2E singles | PASS: `TC003`, `TC005`, `TC007`, `TC017`, `TC018`, `TC020`, `TC026`-`TC036` |
| API core | PASS con reruns focales: `TCAPI001`-`TCAPI005`, `TCAPI008`-`TCAPI016` |
| Regression | PASS: `TC007`, `TC017`, `TC020`, `TC034`, `TCAPI002`, `TCAPI015`, `TCAPI016` |

### Hallazgos

| ID | Suite | Severidad | Clasificacion | Evidencia | Root cause |
|---|---|---:|---|---|---|
| FP-API-001 | API | P3 | Falso positivo TestSprite | `TCAPI007` fallo por `/mail/sync` y `/mail/messages/{id}/ignore` en OpenAPI. | El generador trato endpoints locales/read-side como send/draft normal. |
| FP-API-002 | API | P3 | Falso positivo TestSprite | `TCAPI011` fallo por `POST /code-director/runs` 405. | El generador invento ruta/metodo no soportado y no acepto 405 como guard. |
| FP-API-003 | API | P3 | Falso positivo TestSprite | `TCAPI002` marco `jwt_secret`/`client_secret` como valor secreto. | Heuristica buscaba nombres de campos, no valores secretos. |
| FP-API-004 | API | P3 | Falso positivo TestSprite | `TCAPI009` espero campo `id` en `ThreadResponse`. | El contrato real y PRD usan `thread_id`. |
| FP-API-005 | API | P3 | Falso positivo TestSprite | `TCAPI016` marco contenido normal de mail como secret-like. | Heuristica de longitud sobre IDs/snippets/senders. |

### Fixes

| ID | Archivos | Cambio | PRD respetado |
|---|---|---|---|
| PLAN-001 | `testsprite_tests/testsprite_backend_test_plan.json` | Se reemplazaron casos inseguros/ambiguos con `TCAPI015` y `TCAPI016` GET-only. | No mail send/draft, no DNS write, no side effect. |
| PLAN-002 | `testsprite_tests/testsprite_frontend_test_plan.json` | Se agregaron `TC028`-`TC036` para tabs extendidas, no-localhost, guards y chat. | Cobertura total UI/E2E sin pseudo-routes. |

No hubo cambios de producto durante Prompt 3. Las correcciones de producto reales venian de Prompt 2 y ya estaban validadas.

### Reruns

| Suite | Test | Resultado | Artifacts |
|---|---|---|---|
| API | `TCAPI011` | PASS | `test-results/testsprite/zero-defects-loop-1/api-tcapi011-rerun/` |
| API | `TCAPI015` | PASS | `test-results/testsprite/zero-defects-loop-1/api-mail-tcapi015/` |
| API | `TCAPI016` | PASS | `test-results/testsprite/zero-defects-final-run-a/api-guard-tcapi016/` |
| API | `TCAPI002` | PASS | `test-results/testsprite/zero-defects-final-run-a/api-focal-tcapi002/` |
| API | `TCAPI009` | PASS | `test-results/testsprite/zero-defects-final-run-a/api-focal-tcapi009/` |
| API | `TCAPI016` | PASS | `test-results/testsprite/zero-defects-final-run-b/api-focal-tcapi016/` |
| UI/E2E | Final B critical singles | PASS | `test-results/testsprite/zero-defects-final-run-b/ui-e2e-*` |

### Estado del loop

Estado: candidato a cierre.

No quedan P0/P1/P2 reales. No quedan P3 corregibles con impacto comercial, zero-friction, health/readiness, mail, Action Plane o flujos criticos.
