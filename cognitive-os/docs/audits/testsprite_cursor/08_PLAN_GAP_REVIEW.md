# 08 — Plan Gap Review (pre-ejecución)

Fecha: **2026-05-26**  
Revisión: planes MCP + blueprint manual **antes** de Megaprompt 2

## Checklist PRD vs planes

| Pregunta | UI (40) | API (16) | E2E (15) | Guard (11) |
|---|:---:|:---:|:---:|:---:|
| ¿Incluye todas las tabs? | **Parcial** | n/a | **Sí** | n/a |
| ¿Respeta SPA (solo `/`)? | **Parcial** | n/a | **Sí** | n/a |
| ¿Siembra localStorage público? | **No explícito** | n/a | **Sí** | n/a |
| ¿Cubre no localhost? | **No** | n/a | **Sí** | n/a |
| ¿Cubre CORS/mixed-content? | **No** | **Sí** (TCAPI005) | **Sí** | n/a |
| ¿Cubre public/protected API? | n/a | **Sí** | **Sí** | **Sí** |
| ¿Cubre auth negative? | TC038 JWT inválido | **Sí** TCAPI003 | implícito | **Sí** |
| ¿Cubre health/readiness? | TC006–TC009 | TCAPI002/014 | TE2E002 | n/a |
| ¿Cubre mail read-only? | TC024–TC032 | TCAPI007/015 | TE2E009 | **Sí** |
| ¿Cubre Action Plane? | TC018, TC035 | TCAPI012 | TE2E010 | **Sí** |
| ¿Cubre jobs/approvals? | TC014, TC018 | TCAPI004 | TE2E003/004 | TG007–009 |
| ¿Cubre Document Analysis? | TC010, TC020 | TCAPI010 | TE2E007 | n/a |
| ¿Cubre Research? | TC011, TC021 | TCAPI011 | TE2E008 | n/a |
| ¿Cubre Code Director? | TC019, TC023 | TCAPI011 | TE2E012 | n/a |
| ¿Cubre MCP? | TC033 | TCAPI014 | TE2E011 | n/a |
| ¿Cubre forbidden guards? | TC034 parcial | TCAPI006–007,016 | n/a | **Sí** |
| ¿Cubre zero-friction dedicated_local/full? | TC013, TC018 | parcial | TE2E013 | n/a |
| ¿Evita endpoints peligrosos? | **Riesgo TC024 sync** | **Sí** | **Sí** | **Sí** |
| ¿Evita falsos positivos conocidos? | **Parcial** | **Fuerte** | **Sí** | **Sí** |

## Gaps concretos

### G1 — UI plan orientado a JWT local, no seed público (P1)

Casos TC001–TC003 hablan de "mint local JWT" / Settings local. Megaprompt 2 debe prepend:

- pre-step `localStorage` con JWT de `/tmp/cognitive_os_testsprite_cursor_jwt.txt`
- `cogos.api=https://cognitive-api.doctormanzur.com`

### G2 — Hotkeys 1–9 no explícitos (P2)

PRD_FRONTEND exige hotkeys. Plan UI usa palette/tabs pero no asserts por tecla `1`–`9`. Añadir 9 micro-casos o expandir TC005.

### G3 — LangSmith / Audit / Sandbox tabs (P2)

- LangSmith: no hay caso dedicado (solo LangSmith vía API TCAPI014).
- Audit: no explícito en UI plan (hotkey 8 en PRD).
- Sandbox: no explícito.

### G4 — Responsive / mobile (P2)

PRD pide responsive; ningún caso UI/E2E lo cubre.

### G5 — TC024 mail sync UI (P0 riesgo contrato)

"Sync mail in read-only mode" puede disparar POST `/mail/sync`. Mover sync a Suite D guard-only o reescribir como GET-only UI verification.

### G6 — Backend plan regen bloqueada (P1 operativo)

`testsprite_generate_backend_test_plan` falló con config `type: frontend`. Plan 16 casos es válido (ya apunta a URLs públicas) pero Megaprompt 2 necesita bootstrap backend separado para refrescar.

### G7 — Config `localEndpoint` = localhost (P1 infra)

`testsprite_tests/tmp/config.json` apunta a `http://localhost:3001/`. Para auditoría Cursor pública, Megaprompt 2 debe actualizar instrucciones/`localEndpoint` o usar runner con override público.

### G8 — Suites C/D no generadas por MCP (P2)

Documentadas manualmente; deben ejecutarse como instrucciones compuestas o casos ad-hoc en Megaprompt 2.

## Falsos positivos a blindar

| ID | Regla |
|---|---|
| FP-SPA-404 | `/dashboard`, `/health`, etc. → 404 OK |
| FP-AUTH-401 | Sin JWT → 401 OK |
| FP-PLACEHOLDER | Placeholder `127.0.0.1:8000` en UI antes de seed OK |
| FP-LLM-LATENCY | Chat/research >60s puede ser dependencia externa |
| FP-OPENAPI-NAME | Nombres `jwt_secret` en schema ≠ leak |
| FP-405 | 405 en métodos no soportados = guard OK |

## Acciones antes de ejecutar (Megaprompt 2)

1. Patch `additionalInstruction` global (blueprint §instrucciones).
2. Añadir casos G2–G4 al plan UI (dashboard editor o JSON edit).
3. Reclasificar TC024 → guard-only o read-only GET UI.
4. Bootstrap backend phase para refresh API plan si hace falta.
5. Smoke: TCAPI001 + TC001 con seed público.
6. Ejecutar serial — nunca MCP `testIds: []`.

## Veredicto revisión de planes

**PARTIAL** — suficiente para iniciar Megaprompt 2 con gaps documentados y mitigaciones. No ejecutar auditoría completa hasta aplicar G1, G5, G7 como mínimo.
