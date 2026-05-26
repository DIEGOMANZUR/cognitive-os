# 09 — Pre-Run Check

Fecha: **2026-05-26**  
Modo: **TestSprite MCP only**  
Nota: los comandos usados fueron **runtime availability checks**, no suites de QA.

## Contexto leído

- `PRD.md`
- `PRD_FRONTEND.md`
- `PRD_BACKEND.md`
- `docs/audits/testsprite_cursor/00_MCP_CAPABILITY_CHECK.md`
- `docs/audits/testsprite_cursor/01_RUNTIME_READINESS_FOR_TESTSPRITE.md`
- `docs/audits/testsprite_cursor/02_TESTSPRITE_AUTH_AND_SECRETS.md`
- `docs/audits/testsprite_cursor/03_TESTSPRITE_MASTER_BLUEPRINT.md`
- `docs/audits/testsprite_cursor/04_UI_PLAN.md`
- `docs/audits/testsprite_cursor/05_API_PLAN.md`
- `docs/audits/testsprite_cursor/06_E2E_PLAN.md`
- `docs/audits/testsprite_cursor/07_GUARD_PLAN.md`
- `docs/audits/testsprite_cursor/08_PLAN_GAP_REVIEW.md`

## TestSprite MCP

| Item | Estado |
|---|---|
| Server | `user-TestSprite` |
| Tool account check | OK |
| Plan | Starter |
| Créditos antes de ejecución | 522 |
| Tool execution schema read | `testsprite_generate_code_and_execute.json` |

## Runtime público

| Check | Resultado |
|---|---|
| `https://cognitive.doctormanzur.com/` | HTTP 200 |
| `https://cognitive-api.doctormanzur.com/health` | HTTP 200 |
| `https://cognitive-api.doctormanzur.com/openapi.json` | HTTP 200, ~189 KB |
| `GET /system/info` con Bearer JWT | HTTP 200 |
| `GET /system/info` sin auth | HTTP 401 esperado |

## Auth

| Superficie | Estado |
|---|---|
| JWT file | `/tmp/cognitive_os_testsprite_cursor_jwt.txt` |
| Permisos esperados | `600` |
| JWT en reportes | Enmascarar; no imprimir completo |
| UI seed requerido | `cogos.token=<JWT>`, `cogos.api=https://cognitive-api.doctormanzur.com` |
| API auth requerido | `Authorization: Bearer <JWT>` |

## Prohibiciones activas

- No enviar correos.
- No crear drafts.
- No aprobar envío outbound.
- No DNS write real.
- No filesystem/sandbox destructivo.
- No safety flag mutation.
- No JWT secret rotation.
- No admin user mutation.

## Gaps pre-run y mitigación

| Gap | Riesgo | Mitigación para ejecución |
|---|---|---|
| G1: plan UI usa JWT local/Settings | 401 falsos o login inexistente | Instrucción MCP obliga seed localStorage antes de navegación |
| G5: TC024 menciona mail sync | Posible side effect | No ejecutar TC024 como UI normal; cubrir mail con TC027/TC032/TC040 y guards GET-only |
| G7: config local endpoint | Puede ejecutar local en vez de público | Instrucción MCP exige origen público; si TestSprite ignora esto, clasificar BLOCKED/no PASS público |

## Decisión pre-run

**READY WITH GUARDS.** Se puede ejecutar TestSprite MCP en batches explícitos, sin `testIds: []`, y sin ejecutar los casos peligrosos como UI normal.
