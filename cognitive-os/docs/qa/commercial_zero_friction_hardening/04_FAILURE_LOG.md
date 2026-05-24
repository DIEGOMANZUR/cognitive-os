# 04 Failure Log

| ID | Severidad | Estado | Falla | Reproduccion/evidencia | Causa raiz | Fix | Validacion |
|---|---|---|---|---|---|---|---|
| FAIL-2026-05-23-001 | P1 | corregido | Live gate auto-consentia proveedores reales | `scripts/full-qa-live.sh` exportaba `LIVE_TESTS_ENABLED=1` | script confundia "gate live" con "consentimiento live" | exigir env externo y salir con diagnostico si falta | `test_full_qa_live_requires_external_opt_in`; ejecucion sin env debe salir 2 |
| FAIL-2026-05-23-002 | P1 | corregido | E2E podia ocultar rotura de `/auth/local-token` | `scripts/full-e2e.sh` mintaba JWT via `create_access_token` | bypass local del endpoint que el contrato queria probar | quitar mint directo; delegar en `_global-setup.ts` | `test_full_e2e_script_exists_for_playwright_gate` |
| FAIL-2026-05-23-003 | P2 | corregido | USER_GUIDE prometia theme toggle inexistente | "tema claro/oscuro" y "alterna tema" | doc secundaria quedo atrasada tras dark-only | actualizar texto a dark-only | `test_user_guide_matches_dark_only_frontend_contract` |
| FAIL-2026-05-23-004 | P2 | corregido | Conteos QA secundarios obsoletos | `COGNITIVE_OS_GUIDE.md`, `AGENT_LEARNING_PLAN.md`, `scripts/README.md` | drift documental post 958 tests | actualizar a 958 + 14 regresiones/guards | `sync_doc_counts --check` verde |
| FAIL-2026-05-23-005 | P1 | corregido | TestSprite full paralelo podia saturar el backend local y dejar backlog de sockets | tercera corrida all-at-once dejo `/health` sin respuesta y `LISTEN 2049/2048` en `:8000` | runner cloud ejecuta muchos casos en paralelo contra un uvicorn local dedicado | crear `scripts/full-testsprite.sh` serial por defecto, health entre lotes, idle timeout, reintentos, split adaptativo y redaccion de token | TestSprite micro-batched: health 200 entre lotes; sin procesos colgados |
| FAIL-2026-05-23-006 | P2 | corregido | Plan TestSprite exigia fixtures inexistentes y marcaba falso rojo | TC006/TC018/TC021/TC022 bloqueados/fallidos por aprobaciones vacias, mail digest deshabilitado o jobs poblados | expectativas no eran state-aware para un local-first vivo | corregir plan TestSprite generado para aceptar estados honestos: poblado/vacio/disabled con diagnostico | rerun focalizado 4/4 passed; batched completo 28/28 passed |
| FAIL-2026-05-23-007 | P2 | corregido | Fixture reset inicial violaba FK `ActionRequest.approval_id -> HumanApproval.id` | `uv run pytest tests/test_test_fixtures_api.py -q` fallo al borrar `human_approvals` antes de `action_requests` | orden de borrado no respetaba dependencias DB | borrar ActionRequest antes de HumanApproval y cubrirlo con test de reset final | `test_test_fixtures_seed_safe_borrable_state` passed |
| FAIL-2026-05-23-008 | P3 | corregido | Playwright critico tenia selector ambiguo para texto `retryable` | `getByText(/retryable/i)` matcheaba celda y metadata JSON | assert no estaba anclado a rol/celda visible | usar `getByRole("cell", { name: /Fixture failure is retryable/i })` | `npx playwright test tests/e2e/commercial-fixtures-critical.spec.ts` -> 10 passed |
| FAIL-2026-05-23-009 | P2 | corregido | Fixture coverage no recorria los 10 escenarios declarados | test backend solo sembraba 3 escenarios | contrato de fixtures podia degradar sin falla visible | agregar recorrido seed/reset por cada escenario soportado | `uv run pytest tests/test_test_fixtures_api.py -q` -> 4 passed |
| FAIL-2026-05-23-010 | P2 | corregido | Playwright critico no cubria explicitamente zero-friction, mail read-only positivo, failed job y running lifecycle en el spec critico | spec critico tenia 6 flows y dependia de specs separadas para parte del contrato | cobertura critica fragmentada | ampliar `commercial-fixtures-critical.spec.ts` a 10 flows deterministicos | `npx playwright test tests/e2e/commercial-fixtures-critical.spec.ts` -> 10 passed |

## Fallas historicas relevantes no reabiertas

Los reportes previos de `docs/audits/testsprite/` documentan correcciones ya
cerradas: Telegram fail-closed, health configured-vs-verified,
`operational_backlog`, Alembic hard gate, `.next-qa`, E2E comercial y bug
`eager_defaults`. Esta pasada no reabre esos items salvo que un gate falle.
