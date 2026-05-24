# 03 Coverage Gaps

| ID | Severidad | Area | Brecha | Evidencia | Riesgo | Estado |
|---|---|---|---|---|---|---|
| GAP-001 | P1 | Live QA | `full-qa-live.sh` habilitaba `LIVE_TESTS_ENABLED=1` internamente | `scripts/full-qa-live.sh` tenia `export LIVE_TESTS_ENABLED=1` | contacto accidental con proveedores reales | corregido |
| GAP-002 | P1 | Playwright/zero-friction | `full-e2e.sh` podia mintar JWT directo con Python | `create_access_token` en script | falso verde si `/auth/local-token` se rompe | corregido |
| GAP-003 | P2 | Docs/frontend | `USER_GUIDE.md` prometia toggle claro/oscuro | texto "tema claro/oscuro" y "alterna tema" | docs contradicen dark-only y pueden reintroducir feature retirada | corregido |
| GAP-004 | P2 | Docs/QA | Guias secundarias mantenian conteos QA antiguos o incompletos | `COGNITIVE_OS_GUIDE.md`, `AGENT_LEARNING_PLAN.md`, `scripts/README.md` | snapshot confuso; falsos objetivos de gate | corregido |
| GAP-005 | P2 | Action Plane | Falta matriz exhaustiva de dispatch concurrente/broker failure para todas las acciones | inventario de tests | doble ejecucion teorica si una accion nueva no sigue patron | pendiente no bloqueante |
| GAP-006 | P2 | RAG/Document Analysis | Edge cases de "no evidence", PDF corrupto, budgets y cancelacion no estan todos en E2E | inventario de tests | degradacion oculta en flows largos | pendiente no bloqueante |
| GAP-007 | P2 | Learning | UI de learning no tiene todos los asserts E2E de proposal/evidence/rollback | inventario de tests | memoria/propuestas poco visibles | pendiente no bloqueante |
| GAP-008 | P3 | Frontend static | Hay restos inertes de tipos/CSS de tema antiguo | `frontend/app/lib/types.ts`, `globals.css` | confusion de mantenimiento | evaluado; no cambia runtime |

## Criterio de bloqueo

P0 y P1 detectados en esta pasada deben quedar corregidos antes del cierre. Los
P2/P3 pendientes se mantienen como riesgos residuales si no hay evidencia de
rotura funcional inmediata y si no contradicen el contrato canonico actual.
