# 00 — TestSprite MCP Capability Check (Cursor)

Fecha: **2026-05-26**  
Alcance: preparación blueprint Cursor — **sin ejecución de tests en este prompt**

## Servidor MCP encontrado

| Item | Valor |
|---|---|
| Servidor Cursor | `user-TestSprite` |
| Descriptors | `/mcps/user-TestSprite/tools/*.json` (8 tools) |
| Cuenta verificada | `testsprite_check_account_info` → Starter, créditos **522**, email enmascarado |

## Tools reales (no inventadas)

| Tool | Propósito real | Parámetros clave |
|---|---|---|
| `testsprite_check_account_info` | Cuenta, plan, créditos | _(vacío)_ |
| `testsprite_bootstrap` | Init first-time: `localPort`, `type` frontend/backend, `projectPath`, `testScope` | Requerido si no hay config válida |
| `testsprite_generate_standardized_prd` | PRD estructurado desde repo | `projectPath` |
| `testsprite_generate_frontend_test_plan` | Plan UI | `projectPath`, `needLogin` |
| `testsprite_generate_backend_test_plan` | Plan API | `projectPath` — **solo si config.type=backend** |
| `testsprite_generate_code_summary` | Resumen codebase | `projectRootPath` |
| `testsprite_generate_code_and_execute` | Generar + ejecutar tests cloud | `projectPath`, `testIds[]`, `serverMode`, `additionalInstruction` |
| `testsprite_open_test_result_dashboard` | Dashboard web post-ejecución | `projectPath`, `modificationContext?` |

## Capacidades vs requisitos del blueprint

| Requisito blueprint | ¿Soportado por MCP? | Evidencia |
|---|---|---|
| Crear sesión/proyecto | **Parcial** | `testsprite_bootstrap` + `testsprite_tests/tmp/config.json` |
| Cargar PRD/spec | **Parcial** | PRD copiados a `testsprite_tests/tmp/prd_files/`; `testsprite_generate_standardized_prd` generó `standard_prd.json` |
| Cargar OpenAPI | **Indirecto** | No hay tool dedicada; casos API referencian `GET /openapi.json` en plan backend |
| Configurar URL frontend | **Parcial** | `localEndpoint` en config (hoy `http://localhost:3001/`); **no hay campo first-class para URL pública** — requiere `additionalInstruction` |
| Configurar URL backend | **Parcial** | Casos backend ya apuntan a `https://cognitive-api.doctormanzur.com` en descripciones |
| Configurar auth | **Parcial** | JWT vía instrucciones / pre-steps; no hay tool `setLocalStorage` |
| Seed localStorage | **No nativo** | Debe ir en `additionalInstruction` o steps del plan |
| Generar plan UI | **Sí** | `testsprite_generate_frontend_test_plan` → 40 casos |
| Generar plan API | **Condicional** | Falló regen con config frontend; plan existente 16 casos (`TCAPI001–016`) |
| Plan E2E dedicado | **No** | Suite C manual en `06_E2E_PLAN.md` |
| Plan Guard dedicado | **No** | Suite D compuesta (`07_GUARD_PLAN.md`) |
| Ejecutar UI/API/E2E | **Sí (una tool)** | `testsprite_generate_code_and_execute` — **no ejecutado en este prompt** |
| Exportar artifacts | **Post-run** | `testsprite_tests/tmp/*`, reportes markdown generados por runner |
| Screenshots/traces | **Post-run** | URLs en resultados TestSprite (sanitizar en reports) |
| Listar fallos | **Post-run** | `batched_results.json`, dashboard tool |

## Limitaciones críticas (Cursor + TestSprite)

1. **Un solo `type` en config** (`frontend` **o** `backend`) — regenerar plan API requiere bootstrap backend (sobrescribe config frontend).
2. **Tunnel default** — bootstrap usa `localPort`; auditoría **pública** depende de instrucciones explícitas (`https://cognitive.doctormanzur.com`) y no del túnel local.
3. **Texto MCP engañoso** — `generate_code_and_execute` sugiere saltarse bootstrap; en Cognitive OS usar skill `testsprite-cognitive-os` antes de ejecutar.
4. **`testIds: []` peligroso** — dispara bug túnel (`health:80`); Megaprompt 2 debe usar runner repo o IDs explícitos.
5. **No editor de plan MCP** — ampliar gaps requiere editar JSON exportado o dashboard post-run.

## Acciones realizadas en esta fase

- `testsprite_check_account_info` → OK  
- `testsprite_generate_standardized_prd` → OK (`standard_prd.json`)  
- `testsprite_generate_frontend_test_plan` (`needLogin: false`) → OK (40 casos)  
- `testsprite_generate_backend_test_plan` → **BLOCKED** (`This tool only supports backend tests. Please set testType to "backend"`)

## ¿Se puede continuar?

**Sí — PARTIAL.** MCP operativo, planes UI+API disponibles (API desde artefacto previo), suites E2E/Guard documentadas manualmente. Megaprompt 2 debe:

1. Bootstrap/config separados o fases serializadas para frontend vs backend público.  
2. Inyectar pre-step localStorage + `cogos.api` público en `additionalInstruction`.  
3. Ejecutar con `testIds` explícitos — nunca `[]` vía MCP crudo.
