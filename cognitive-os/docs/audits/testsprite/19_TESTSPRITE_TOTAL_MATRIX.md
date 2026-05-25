# 19 - TestSprite Total Matrix

Fecha UTC: 2026-05-24

Fuente de verdad:

- `/home/jgonz/Escritorio/testsprite/PRD.md`
- `/home/jgonz/Escritorio/testsprite/PRD_FRONTEND.md`
- `/home/jgonz/Escritorio/testsprite/PRD_BACKEND.md`
- Reportes TestSprite `01` a `18`.

## A. UI Total

| Area | Casos TestSprite | Criterio |
|---|---|---|
| Bootstrap SPA | TC002, TC004, TC005 | La app carga en `/`, no navega a rutas inexistentes y conserva estado. |
| LocalStorage auth | TC002, TC004, TC007, TC037 | `cogos.token` y `cogos.api` se aplican antes de llamadas backend. `TC037` reemplaza `TC034`. |
| TopBar connected | TC007, TC037 | Sesion conectada contra API publica/local segun host. |
| Dashboard | TC005, TC006, TC015 | KPIs o estado terminal sin spinner infinito. |
| Chat | TC036 | Roundtrip corto o error controlado accionable. |
| DeepAgents | TC028 | Tab carga, catalogo/disabled state claro, sin iniciar agente largo. |
| Skills | TC028 | Catalogo o empty state util. |
| Memoria | TC028 | Propuestas/listado/empty state sin crash. |
| Asistente | TC028 | Superficie carga y valida formularios sin writes peligrosos. |
| Mail | TC001, TC003, TC013, TC021 | Read-only: no send normal, no draft normal, propuestas como texto. |
| Documentos | TC024, TC026 | Lista/detalle o empty state. |
| Document Analysis | TC029 | Carga modos, valida input vacio/invalido o muestra degradacion clara. |
| Jobs | TC018, TC019, TC025 | Lista/detail/events o empty state sin 500 visible. |
| Aprobaciones | TC020, TC022, TC023 | Cola poblada o vacia estable; no approval outbound mail. |
| Google Ops | TC038 | Read-only/preview; DNS real write no disponible. `TC038` reemplaza `TC035`. |
| Research | TC030 | Run controlado o degraded state accionable. |
| Code Director | TC031 | Plan/status/budget o adapter unavailable claro. |
| Sandbox | TC031 | Estado read-only; no exec destructivo. |
| LangSmith | TC031 | Metadata/status o degraded state. |
| Audit log | TC027 | Tabla o empty state seguro. |
| Health | TC007, TC010 | Health honesto; verify terminal. |
| Sistema | TC008, TC009, TC017 | Config/readiness/MCP visibles sin secretos. |
| Conexion | TC002, TC004 | API/token persistidos; no localhost efectivo tras seed. |
| Command Palette | TC014, TC032 | Ctrl/Cmd+K abre y navega tabs. |
| Hotkeys | TC005, TC032 | 1-9 cambian vistas sin cambiar URL. |
| Notifications | TC032 | Bell/panel abre o ausencia explicada sin crash. |
| Responsive | TC033 | Desktop y mobile alcanzan tabs criticas sin solapamientos bloqueantes. |
| Console/network | TC037 | No console critical, no CORS, no mixed content, no host drift. |
| Dead buttons/false success | TC028-TC036 | Botones criticos responden o explican disabled/degraded. |

## B. API Total

| Area | Casos TestSprite | Criterio |
|---|---|---|
| Public endpoints | TCAPI001 | `/health`, `/openapi.json`, `/docs`, `/redoc` publicos. |
| Protected auth | TCAPI002, TCAPI003 | Bearer admin funciona; missing/invalid/expired dan 401 esperado. |
| CORS preflight | TCAPI005 | Origin publico permitido sin wildcard inseguro. |
| System/readiness | TCAPI002, TCAPI014 | `/system/info`, `/system/readiness`, `/system/credentials-status`, `/system/mcp`. |
| Health | TCAPI001, TCAPI014 | `/health/dashboard`, `/health/verify` honestos. |
| Actions | TCAPI004, TCAPI012 | Catalogo/requests read-only, guards, no side effect real. |
| DeepAgents | TCAPI008 | Catalogo/listado sin arrancar agentes largos. |
| Mail | TCAPI007 | GET-only y OpenAPI guard inspection; no POST mail salvo `/auth/local-token`. |
| Document Analysis | TCAPI010 | Status/malformed/invalid id sin 500; no ingest destructivo. |
| Assist | TCAPI014 | Read-only/list endpoints o disabled accionable. |
| Jobs | TCAPI004, TCAPI013 | Lista, detail si existe, invalid id sin 500. |
| LangSmith | TCAPI014 | Metadata/status o disabled accionable. |
| Research | TCAPI011 | Status/list/start controlado o degraded state; no external write. |
| Code Director | TCAPI011 | Status/plan validation o adapter unavailable claro. |
| Threads/chat | TCAPI009 | Chat corto crea thread o error controlado; thread fetch coherente. |
| Documents | TCAPI010 | Lista/detalle si existe, invalid id sin 500. |
| Approvals | TCAPI004, TCAPI013 | Lista, invalid id/double-state sin 500; no outbound approval. |
| Voice | TCAPI014 | Status/disabled claro. |
| Sandbox | TCAPI011 | Status/read-only; no destructive exec. |
| Audit | TCAPI004 | `/audit?limit=5` o ruta real devuelve lista segura. |
| Knowledge/config/agents | TCAPI008, TCAPI014 | Catalogos/snapshots sin secretos. |
| Malformed/invalid/nonexistent | TCAPI013 | 4xx esperado, nunca 500 esperado. |
| No secrets | TCAPI002, TCAPI007, TCAPI014 | Credenciales y tokens no aparecen en respuestas. |

## C. E2E Total

| Flujo | Casos TestSprite | Criterio |
|---|---|---|
| UI usa API correcta | TC037, TC007 | Public host usa `https://cognitive-api.doctormanzur.com`; local host usa `http://127.0.0.1:8000`. |
| Health tab refleja backend | TC007, TC010 | Estado UI coincide con backend real o degradacion clara. |
| Jobs tab refleja backend | TC018, TC019 | Lista/empty/error controlado desde API publica. |
| Approvals tab refleja backend | TC020, TC022 | Cola real estable, poblada o vacia. |
| Chat roundtrip | TC036, TCAPI009 | Mensaje/thread o error controlado sin silent failure. |
| Documents list/detail | TC026, TCAPI010 | UI y API coherentes. |
| Document Analysis | TC029, TCAPI010 | Job o validation/degraded state. |
| Research | TC030, TCAPI011 | Run o degraded state accionable. |
| Mail read-only | TC003, TC013, TCAPI007 | No draft/send normal. |
| Action Plane guards | TC038, TCAPI012 | Preview/read-only/4xx esperado; no writes reales. |
| MCP status | TC017, TCAPI014 | Inventario o degradacion clara. |
| Code Director | TC031, TCAPI011 | Status/plan o adapter unavailable claro. |
| Dedicated local/full | TC028-TC036 | Baja friccion sin aprobaciones innecesarias para lectura/reversible. |

## D. Forbidden/Guard Tests

| Guard | Casos TestSprite | Metodo permitido |
|---|---|---|
| No mail send | TC003, TC007 | GET/OpenAPI inspection; no POST send/approve-send. |
| No draft | TC003, TC007 | Verificar ausencia/bloqueo; no draft creation. |
| No DNS real write | TC038, TCAPI012 | Preview/OpenAPI/read-only only. |
| No destructive filesystem | TC031, TCAPI011 | Sandbox status only; no destructive exec. |
| No safety flag toggles | TC009, TC038 | Read config only. |
| No dangerous tools | TCAPI012 | Read catalog/guards, expect 4xx/disabled if probed with dummy safe request. |
| No side effect | TCAPI007, TCAPI012 | Solo GET o dummy invalid request que no pueda ejecutar. |

## E. Regression Cases

| Regression | Casos TestSprite | Criterio |
|---|---|---|
| REG-TS-001 bootstrap publico/local | TC007, TC037 | Auto-token y API base correcta segun host. |
| REG-TS-002 health live terminal | TC007 | Verify termina con estado honesto. |
| REG-TS-003 MCP visible en degradacion | TC017 | Seccion `MCP servers` siempre visible. |
| REG-TS-004 API auth sin `/tmp` | TCAPI002 | Usa `/auth/local-token` y `access_token`. |
| REG-TS-005 mail read-only | TC003, TCAPI007 | No send/draft normal. |
| REG-TS-006 approvals populated queue | TC020 | Poblada o vacia ambas son validas. |

## Suites de cierre

- UI Total: `TC001`-`TC036`, ejecutados en batches seguros.
- API Total: `TCAPI001`-`TCAPI014`, evitando endpoints prohibidos.
- E2E Total: casos UI que ejercitan la API publica y casos API complementarios.
- Regression: subconjunto `TC007`, `TC017`, `TC020`, `TC037`, `TC038`, `TCAPI002`, `TCAPI007`.
