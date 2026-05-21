# CODEX COMMERCIAL READINESS AUDIT — Cognitive OS

Fecha de auditoria: 2026-05-20
Auditor: Codex, responsable tecnico entrante / release gatekeeper
Modo: solo lectura salvo este informe. No se aplicaron reparaciones.

## 0. Veredicto ejecutivo

- Estado global: funcional amplio, pero no liberable como "grado comercial" en el estado auditado.
- ¿Grado comercial real?: No. Parcial para backend core e infraestructura local; no para release comercial serio.
- Riesgo global: Alto.
- Principal fortaleza: arquitectura amplia con FastAPI, Postgres/Alembic, Redis/Celery, Action Plane, tests hermeticos, aislamiento de DB de test, worker real registrado y migraciones limpias.
- Principal debilidad: el contrato documental declara readiness y QA verde, pero las compuertas actuales fallan y varias integraciones criticas estan "configuradas" sin verificacion viva.
- Principal zona endeble: acciones externas/irreversibles y acceso local amplio: mail SMTP, Kimi WebBridge, MCP filesystem, OpenHarness y auto-approval de acciones reversibles.
- Principal bloqueo antes de uso real: release gates rojos (`full-qa`, `ruff format --check`, Playwright) y envio de mail sin pasar por el flujo central `HumanApproval`/`ActionRequest`/`JobEvent`/`AuditEvent` que la documentacion promete.
- Confianza del auditor: Alta para los bloqueantes encontrados; media para integraciones externas no ejercitadas en vivo por seguridad.
- Qué no pude verificar: writes reales de Google/Drive/Calendar/GoDaddy/Mail, envio SMTP real, DNS real, browser real mutante, Code Director real con Claude/Codex/Kimi, Telegram contra Telegram API, LLM/tool-calling real, document analysis legal con documentos reales y citas de produccion. No los ejecute por la regla de no mutar ni tocar produccion.

## 1. Alcance revisado

- Archivos revisados: `README.md`, `docs/USER_GUIDE.md`, `docs/COGNITIVE_OS_GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/RUNBOOK.md`, `docs/ACTION_PLANE.md`, `docs/DOCUMENT_ANALYSIS_AGENT.md`, `docs/DEEPAGENTS_INTEGRATION.md`, `docs/DEEPAGENTS_SKILLS_MEMORY.md`, `docs/AGENT_LEARNING_PLAN.md`, `docs/SECURITY.md`, `docs/OPERATOR_VARIABLE_CHECKLIST.md`, `docs/OPENHARNESS_FUSION.md`, `docs/OPENSHELL_SANDBOX.md`, `docs/AGENT_SELF.md`, `docs/qa/*`, backend `api/app.py`, `core/*`, `actions/*`, `mail/*`, `deepagents/*`, `workers/*`, tests relevantes, frontend `app/*`, `views/*`, Playwright.
- Directorios revisados: `backend/src/cognitive_os`, `backend/tests`, `backend/alembic`, `frontend/app`, `frontend/tests/e2e`, `frontend/public`, `infra`, `scripts`, `docs`.
- Comandos ejecutados: inventario git/find/rg; `bash scripts/full-qa.sh`; `uv run pytest` via full QA; `uv run ruff check .`; `uv run ruff format --check .`; `uv run ruff format --check --diff tests/conftest.py`; `uv run mypy src`; `uv run alembic heads/current/check`; `npm run lint`; `npm run build`; `npx playwright test --reporter=list`; `docker compose ... config`; `curl` read-only a `/health`, `/health/dashboard`, `/system/readiness`, `/system/info`, `/system/credentials-status`, `/system/mcp`, `/openapi.json`, `/jobs`, `/approvals`, `/mail/status`, `/mail/messages?limit=3`; `celery inspect registered/active_queues`; `git diff --check`; `git status --short`.
- Comandos omitidos y razón: no ejecute writes reales, DNS, approvals, SMTP send, OAuth flows, GoDaddy writes, Drive/Calendar writes, browser click/fill/evaluate real, Code Director build real ni Telegram API interactiva.
- Runtime disponible: Parcial. Backend, Postgres, Redis, Weaviate, Neo4j, Celery worker/beat, Kimi WebBridge y Telegram process estaban levantados. Frontend correcto no estaba inicialmente en `:3001`; `:3000` servia otra app ("OpenChamber"). Levante temporalmente Next en `:3001` para E2E y lo apague.
- Frontend disponible: Parcial. Build/lint pasan; E2E falla.
- Telegram disponible: Parcial. Proceso corriendo y codigo auditado; no verifique contra Telegram real.
- Credenciales reales disponibles: Parcial. `/system/credentials-status` reporta 18/21 configuradas; no valide secretos contra proveedores salvo endpoints read-only.

## 2. Matriz documentación vs realidad

| Capacidad declarada | Estado declarado | Fuente documental | Implementación encontrada | Pruebas encontradas | Estado real | Coincide | Riesgo |
|---|---|---|---|---|---|---|---|
| QA verde F82 | lint/build/tsc/E2E full-walk verde | `README.md:18-20`, `README.md:360-367` | Tests y config existen | `full-qa` y Playwright fallan | Roto para release | No | P0 |
| Backend API | 143 endpoints REST | `README.md:37-38`, docs | OpenAPI runtime expone 136 paths; codigo tiene ~144 decorators | Pytest amplio | Funcional pero con drift de conteo | Parcial | P2 |
| Celery | 22 tareas, 5 colas, beat | docs | Worker registra 22 tareas y consume 5 colas | `celery inspect` OK | Solido en registro runtime | Si | P3 |
| Mail | Click Enviar crea `HumanApproval`, worker `mail` envia y deja `AuditEvent` | `docs/USER_GUIDE.md:506-508`, `915-920` | UI llama `/mail/messages/{id}/approve-send`; API llama SMTP en proceso | Tests mockean servicio | Implementado distinto al contrato | No | P0 |
| Health dashboard | readiness util de 17 componentes | docs | Dashboard trata `configured` como OK | Runtime OK con LLM/mail/MCP no live | Falsa certeza parcial | Parcial | P1 |
| MCP | conectado y live en `/system/mcp` | docs | Endpoint live responde en 10.77s; filesystem apunta a `/home/jgonz` | E2E regression solo status | Operativo pero amplio/lento | Parcial | P1 |
| Telegram | 37 comandos con paridad UI/REST | `USER_GUIDE.md:750-785` | 37 decorators `@command` | 21 tests unitarios, pocos happy paths reales | Parcial/no verificado vivo | Parcial | P2 |
| Learning plan | todo pasa por approval gate, cero auto-deploy | `README.md:33-35` | failure postmortem auto-promueve warning tras threshold | Test lo confirma | Contrato falso para warnings | No | P1 |
| Frontend PWA cockpit | 20 vistas, anclajes E2E intactos | docs | 20 views existen, build OK | E2E falla 10/17 en app correcta | Parcial | No | P1 |
| Document analysis legal | doc_ids, citas, quality, exports | `DOCUMENT_ANALYSIS_AGENT.md` | Servicio valida doc_ids/no web, eventos, AuditEvent, HumanApproval para drafts | Tests dedicados | Funcional por tests, no verificado con documentos reales | Parcial | P2 |
| Google Ops/GoDaddy | operables con approval | docs | Endpoints/status/request existen | Tests no prueban writes reales | No verificado para proveedor real | Parcial | P1 |
| Code Director | delega con approval/budget | docs | Endpoints/worker existen | No se ejecuto build real | No verificado | Parcial | P2 |

## 3. Matriz de preparación comercial por subsistema

| Subsistema | Estado | Evidencia | Principal fragilidad | Bloquea comercial |
|---|---|---|---|---|
| 1. Arranque local | Funcional pero frágil | Backend/infra estaban arriba; frontend correcto no estaba en puerto esperado | Puerto `:3000` servia app equivocada | Parcial |
| 2. Backend API | Funcional pero frágil | `/health`, `/openapi.json`, endpoints read-only OK | health configured != live verified | Parcial |
| 3. Frontend | Parcial | `npm lint/build` OK; Playwright 10/17 fail | E2E roto y contrato de localStorage/UI drift | Si |
| 4. Auth/JWT | Parcial | token helper funciona; E2E auth falla | JWT seeded no aparece en TopBar en E2E | Parcial |
| 5. Health dashboard | Funcional pero frágil | 17 componentes, status ok | LLM/mail/MCP no live | Parcial |
| 6. Postgres/Alembic | Comercialmente listo local | heads/current/check OK `202605200003` | depende de Postgres local | No |
| 7. Redis/Celery | Solido en registro | worker ping, 22 tasks, 5 queues | beat/runtime no probado con fallos broker | Parcial |
| 8. Weaviate/RAG | Parcial | health OK | RAG real con embeddings no probado | Parcial |
| 9. Neo4j/Graph | Parcial | health OK | GraphRAG real no verificado | Parcial |
| 10. LangGraph router | Parcial | tests hermeticos | LLM real deshabilitado en unit tests | Parcial |
| 11. DeepAgents | Parcial | tests y workers | real tool-calling/LLM no verificado | Parcial |
| 12. Document ingest | Parcial | endpoints/worker/tests | no se probo PDF corrupto en runtime real | Parcial |
| 13. Document analysis | Parcial | servicio/tests fuertes | no verificado con documentos reales/citas reales | Parcial |
| 14. Research | Parcial | endpoints/tests | OpenHarness/LLM real no verificado | Parcial |
| 15. Memory | Funcional pero frágil | 100 approvals pendientes runtime | backlog y auto-promote warning | Parcial |
| 16. Skills | Parcial | registry/tests | promotion no verificada end-to-end real | Parcial |
| 17. Learning plan | Frágil | auto-promotion confirmada | contradice approval total | Si parcial |
| 18. Action Plane | Funcional pero frágil | endpoints, service, dispatch audit | auto-approval y broad access | Parcial |
| 19. HumanApproval | Parcial | `/approvals` 100 pending | backlog y mail fuera del gate central | Parcial |
| 20. AuditEvent | Parcial | audit endpoint existe | mail send no usa AuditEvent central | Parcial |
| 21. Mail | Alto riesgo | `/mail/status` enabled, send-capable account | direct SMTP path sin central approval | Si |
| 22. Google Ops | No verificado | status endpoints | no writes reales probados | Parcial |
| 23. GoDaddy | No verificado | status/preview/request code | no DNS real probado | Parcial |
| 24. Browser | Frágil | Kimi real browser ready; headless endpoints | real browser navigation sin approval central | Parcial |
| 25. Computer actions | Frágil | auto-approvable `computer_organize` | mover/renombrar no es inocuo | Parcial |
| 26. Office docs | Parcial | exporters/actions | no render/QA de DOCX/XLSX/PPTX real | Parcial |
| 27. Code Director | No verificado | worker registered | adapters externos no ejercitados | Parcial |
| 28. Telegram | Parcial | process + 37 commands | runtime/API real no probado; tests limitados | Parcial |
| 29. Tests backend | Frágiles para release | 799 pass pero 1 fail | hermeticos, no prueban proveedores reales | Si parcial |
| 30. Tests frontend | Rotos | Playwright 10/17 fail | selectors/state drift | Si |
| 31. E2E | Roto | 10/17 fail en app correcta | no hay full-walk verde actual | Si |
| 32. Docs | Sobreoptimizadas | contradicciones y conteos drift | docs prometen mas que runtime | Parcial |
| 33. Configuración | Frágil | readiness 2/9; compose warns blanks | defaults/profiles complejos | Parcial |
| 34. Seguridad operativa | Parcial | guards en production validator | dedicated_local/MCP/Kimi/OpenHarness amplios | Si parcial |

## 4. Resultados de QA

| Comando | Resultado | Error principal | Interpretación | Acción recomendada |
|---|---|---|---|---|
| `bash scripts/full-qa.sh` | FAIL | `1 failed, 799 passed, 1 skipped, 20 deselected`; `test_service_worker_keeps_api_like_routes_network_only` espera `cogos-v2026-05-15-32`, SW actual `cogos-v2026-05-20-glass-2` | Gate oficial roto | Actualizar test o versioning SW, luego correr suite completa |
| `uv run ruff check .` | PASS | - | lint logico backend limpio | Mantener |
| `uv run ruff format --check .` | FAIL | `tests/conftest.py` seria reformateado | Gate oficial roto | Formatear en reparacion aprobada |
| `uv run mypy src` | PASS | - | tipos backend OK | Mantener |
| `uv run alembic heads/current/check` | PASS | head/current `202605200003`, no drift | DB schema coherente | Mantener |
| `npm run lint` | PASS | - | frontend lint OK | Mantener |
| `npm run build` | PASS | Next 16.2.6 build OK | build productivo compila | Mantener |
| `npx playwright test` contra `:3000` | FAIL | `11 failed, 6 passed`; app servida era "Unlock OpenChamber" | puerto real detectado no era Cognitive OS | Runbook debe validar proceso/puerto |
| `npx playwright test` contra `:3001` local | FAIL | `10 failed, 7 passed`; auth/nav/forms/recipe/mobile | E2E actual no respalda cockpit | Reparar E2E o UI contract, no declarar verde |
| `docker compose ... config` | PASS con warnings | variables env no cargadas default a blanco | invocacion sin env-file puede ocultar config invalida | Documentar/comandar siempre con env-file |
| `/health/dashboard` | PASS parcial | status `ok`, pero LLM/mail/MCP `configured` | health no prueba flujos reales | Separar health de readiness live |
| `/system/readiness` | PASS parcial | `2/9 capacidades habilitadas` | runtime actual no esta listo para capacidades externas | Usar como gate visible |
| `/system/mcp` | PASS lento | 200 en 10.77s | live MCP conectado pero lento/amplio | timeout, caching, least privilege |
| `celery inspect registered/active_queues` | PASS | 22 tareas, 5 colas, 1 node online | worker registrado | Agregar verificacion beat y lag |
| `git diff --check` | PASS | - | whitespace diff OK | Mantener |

## 5. Hallazgos P0 Critical

ID: AUDIT-001
Título: Las compuertas oficiales de release estan rojas aunque la documentacion declara QA verde
Severidad: P0 Critical
Categoría: Runtime risk / Missing test / Docs drift
Área: QA / Frontend / Backend
Estado: Confirmado
Evidencia:
- Archivo(s): `backend/tests/test_frontend_static_assets.py:23-34`, `frontend/public/sw.js:13`, `README.md:18-20`, `README.md:360-367`, `frontend/tests/e2e/*`.
- Línea(s): test espera `CACHE_VERSION = "cogos-v2026-05-15-32"`; SW actual declara `cogos-v2026-05-20-glass-2`.
- Comando ejecutado: `bash scripts/full-qa.sh`; `npx playwright test --reporter=list`.
- Resultado: full QA falla con `1 failed, 799 passed`; `ruff format --check` falla; Playwright falla `10 failed, 7 passed` contra app correcta en `:3001`.
- Observación: el repositorio afirma E2E full-walk verde y anclajes intactos, pero la corrida actual no lo sostiene.
Impacto comercial: no se puede cortar release ni prometer estabilidad de cockpit.
Impacto técnico: test contract y frontend actual estan desincronizados; ademas el script oficial se corta antes de lint/build por el fallo de pytest.
Escenario real de fallo: operador cree que QA esta verde, despliega PWA/SW con cache/version drift y pierde navegacion o actualizaciones.
Causa probable: cambios F82 no sincronizaron tests estaticos/E2E con el nuevo cockpit.
Por qué esto es una zona débil/endeble: convierte la documentacion en falsa certeza y rompe el criterio minimo de release.
Cómo lo resolvería: primero congelar cambios, actualizar contrato SW y E2E segun UI real o corregir UI si los anclajes son obligatorios; correr `full-qa` completo hasta verde.
Archivos que probablemente habría que tocar: `backend/tests/test_frontend_static_assets.py`, `frontend/tests/e2e/*`, posiblemente `frontend/app/lib/hooks.ts`, `frontend/app/components/Sidebar.tsx`, `frontend/app/views/SettingsView.tsx`, `frontend/public/sw.js`.
Tests que habría que agregar: E2E que valide localStorage/JWT sin carreras, puerto correcto, version SW, mobile hamburger, MemoryView recipes.
Criterio de aceptación: `bash scripts/full-qa.sh` verde; `npx playwright test --reporter=list` verde contra `:3001`; README actualizado solo despues.
Riesgo de reparación: Medio, porque puede exigir decidir si tests o UI son la fuente de verdad.
Bloquea uso comercial: Sí.
Prioridad de reparación: 1.

ID: AUDIT-002
Título: El envio de mail irreversible no pasa por el approval/audit central prometido
Severidad: P0 Critical
Categoría: Security-operational / Bug / Docs drift
Área: Mail / Backend / Frontend / Audit
Estado: Confirmado
Evidencia:
- Archivo(s): `docs/USER_GUIDE.md:506-508`, `docs/USER_GUIDE.md:915-920`, `frontend/app/views/MailInboxView.tsx:66-75`, `backend/src/cognitive_os/api/app.py:2976-2989`, `backend/src/cognitive_os/mail/service.py:183-279`, `backend/src/cognitive_os/mail/service.py:340-364`.
- Línea(s): docs prometen `HumanApproval` + worker `mail` + `AuditEvent`; UI llama directamente `/mail/messages/{id}/approve-send`; API llama `PersonalMailService().approve_and_send`; servicio ejecuta `_send_with_account` via SMTP y solo escribe `MailSendLog`.
- Comando ejecutado: inspeccion de archivos; `curl /mail/status` read-only.
- Resultado: runtime mail enabled, default sender send-capable, `MAIL_REQUIRE_APPROVAL_FOR_SEND=true`; no central `HumanApproval` en el path de send.
- Observación: "approved_by" en `MailSendLog` no equivale al flujo `HumanApproval` auditable ni a dispatch Celery.
Impacto comercial: un click autenticado puede disparar un correo real irreversible sin la mesa central de aprobaciones que el usuario espera.
Impacto técnico: bypass de `ActionRequest`, `HumanApproval`, `JobEvent`, worker `mail` y `AuditEvent` simetrico panel/Telegram.
Escenario real de fallo: borrador equivocado se envia por SMTP; no existe approval pendiente que revisar ni JobEvent que diagnosticar como flujo Action Plane.
Causa probable: endpoint historico llamado `approve-send` implemento aprobacion local como envio directo.
Por qué esto es una zona débil/endeble: es exactamente el tipo de accion irreversible que define grado comercial.
Cómo lo resolvería: convertir "Enviar" en creacion de `HumanApproval`/`ActionRequest` de mail, despachar por queue `mail` tras aprobacion, emitir `AuditEvent` y `JobEvent`, y dejar `/approve-send` como deprecated/blocked o solo test fixture.
Archivos que probablemente habría que tocar: `mail/service.py`, `api/app.py`, `actions/service.py`, `workers/tasks.py`, `MailInboxView.tsx`, tests mail/API/Telegram approvals.
Tests que habría que agregar: UI click no envia SMTP; crea approval; approval dispatch worker envia una vez; retry no duplica; Telegram `/approve` usa mismo path; AuditEvent actor correcto.
Criterio de aceptación: ningun SMTP se llama sin `HumanApproval approved`; todo envio tiene `mail_send_logs`, `AuditEvent`, `JobEvent`, idempotencia y UI estado visible.
Riesgo de reparación: Alto por migrar flujo en uso y evitar duplicados.
Bloquea uso comercial: Sí.
Prioridad de reparación: 2.

## 6. Hallazgos P1 High

ID: AUDIT-003
Título: `/health/dashboard` da falsa confianza al tratar integraciones no verificadas como OK
Severidad: P1 High
Categoría: Fake readiness / Runtime risk
Área: Backend / Observabilidad / LLM / MCP / Mail
Estado: Confirmado
Evidencia:
- Archivo(s): `backend/src/cognitive_os/core/health.py:55-60`, `137-155`, `158-183`, `299-339`, `343-375`.
- Línea(s): `configured` cuenta como `ok`; LLM/embeddings/mail/MCP saltan llamadas vivas.
- Comando ejecutado: `curl /health/dashboard`, `curl /system/readiness`, `curl /system/mcp`.
- Resultado: dashboard `status=ok`; `primary_llm`, `embeddings`, `mail`, `mcp_client` solo `configured`; readiness `2/9 capacidades habilitadas`; `/system/mcp` tardo 10.77s.
- Observación: la propia UI puede reportar verde aunque chat/embeddings/mail/MCP fallen en uso real.
Impacto comercial: operador diagnostica mal incidentes; "ok" no significa servicio usable.
Impacto técnico: health mezcla liveness con capability readiness.
Escenario real de fallo: cliente reporta que chat/mail no funciona; dashboard sigue verde porque solo hay claves configuradas.
Causa probable: optimizacion para evitar latencia/gasto en `/health`.
Por qué esto es una zona débil/endeble: health que no prueba los flujos criticos causa falsa seguridad.
Cómo lo resolvería: mantener liveness barato, pero agregar readiness live opcional con estado separado, ultimo probe, edad, error redactado y SLA por componente.
Archivos que probablemente habría que tocar: `core/health.py`, `api/app.py`, `HealthView.tsx`, `DashboardView.tsx`, docs/runbook.
Tests que habría que agregar: health no marca `ok` comercial si componente esta solo `configured`; readiness live detecta proveedor caido; UI distingue `configured` vs `verified`.
Criterio de aceptación: release gate exige readiness live para capacidades prometidas o las etiqueta "NO VERIFICADO".
Riesgo de reparación: Medio por latencia/coste de probes.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 3.

ID: AUDIT-004
Título: El plan de aprendizaje auto-promueve warnings sin aprobacion humana pese al contrato "todo pasa por approval gate"
Severidad: P1 High
Categoría: Docs drift / Architecture risk
Área: Memory / Learning plan / DeepAgents
Estado: Confirmado
Evidencia:
- Archivo(s): `README.md:33-35`, `backend/src/cognitive_os/deepagents/failure_postmortem.py:10-18`, `279-347`, `backend/tests/test_failure_postmortem.py`.
- Línea(s): `requires_approval=not auto_promote`; cuando `auto_promote`, crea memoria activa con `approved_by="auto_promotion"`.
- Comando ejecutado: inspeccion estatica y pytest via full QA.
- Resultado: comportamiento implementado y probado.
- Observación: puede ser intencional, pero contradice "cero auto-deploy de comportamiento".
Impacto comercial: comportamiento de agentes puede cambiar sin decision explicita del operador.
Impacto técnico: memoria activa altera prompts futuros; rollback/visibilidad deben ser mas fuertes.
Escenario real de fallo: tres fallos recuperados por coincidencia generan warning activo incorrecto y sesgan futuras ejecuciones.
Causa probable: se acepto "silent acceptance" como aprobacion.
Por qué esto es una zona débil/endeble: aprendizaje autonomo afecta el sistema productivo.
Cómo lo resolvería: eliminar auto-promote o convertirlo en "auto-proposal high confidence" pendiente; si se conserva, documentarlo como excepcion y meter kill switch.
Archivos que probablemente habría que tocar: `failure_postmortem.py`, settings, tests, `AGENT_LEARNING_PLAN.md`, `README.md`, Memory UI.
Tests que habría que agregar: threshold crea propuesta pendiente, no activa; rollback visible; operator decision requerida.
Criterio de aceptación: ninguna memoria que altere prompts se activa sin actor humano identificable.
Riesgo de reparación: Medio.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 4.

ID: AUDIT-005
Título: Kimi WebBridge y MCP exponen superficie local amplia con diagnostico lento y sin approval central para navegacion
Severidad: P1 High
Categoría: Security-operational / Runtime risk
Área: Browser / MCP / Configuración
Estado: Confirmado
Evidencia:
- Archivo(s): `backend/src/cognitive_os/actions/kimi_webbridge.py:1-18`, `41-47`, `67-70`, `backend/src/cognitive_os/api/app.py:2775-2782`, `backend/src/cognitive_os/core/config.py:1424-1430`.
- Línea(s): WebBridge opera browser real con logins; `navigate` esta en read-only; endpoint POST llama servicio directo; dedicated_local habilita WebBridge por defecto si no se explicita.
- Comando ejecutado: `/health/dashboard`, `/system/mcp`.
- Resultado: Kimi WebBridge `ready`, daemon running; MCP live 200 en 10.77s con `fs` target `npx ... /home/jgonz`, Supermemory/GitHub remotos conectados.
- Observación: navegar una sesion real no es puramente inocuo; MCP filesystem a `/home/jgonz` es demasiado amplio para grado comercial sin policy visible.
Impacto comercial: riesgo de exfiltracion accidental, side effects via browser real, latencia diagnostica.
Impacto técnico: superficie fuera del Action Plane normal y lejos de least privilege.
Escenario real de fallo: agente navega una URL allow-listed en sesion logueada y dispara estado externo o expone datos; MCP lee mas del workspace esperado.
Causa probable: perfil `dedicated_local` optimizado para operador unico.
Por qué esto es una zona débil/endeble: local-first no equivale a sin riesgo; `/home` entero y browser real son activos sensibles.
Cómo lo resolvería: reducir MCP filesystem al workspace, requerir approval para navigate real en dominios sensibles, separar snapshot/list_tabs read-only de navegación, timeouts y caching para `/system/mcp`.
Archivos que probablemente habría que tocar: config MCP/env, `kimi_webbridge.py`, `api/app.py`, Settings/Health UI, docs.
Tests que habría que agregar: navigate requiere policy/approval segun dominio; MCP root no puede ser `/home` en strict/commercial; `/system/mcp` timeout controlado.
Criterio de aceptación: superficie local minima, visible, testeada y con modo degradado claro.
Riesgo de reparación: Medio/alto por afectar flujos del operador.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 5.

ID: AUDIT-006
Título: `dedicated_local` suaviza aprobaciones y auto-aprueba operaciones que pueden dañar datos del operador
Severidad: P1 High
Categoría: Security-operational / Config fragility
Área: Action Plane / Computer / Drive / Configuración
Estado: Confirmado
Evidencia:
- Archivo(s): `backend/src/cognitive_os/core/config.py:1382-1431`, `backend/src/cognitive_os/actions/service.py:62-78`, `docs/USER_GUIDE.md:1077-1079`.
- Línea(s): `approval_require_four_eyes=False`, `require_human_approval_for_external_actions=False`, `auto_approve_reversible_actions=True`; whitelist incluye `drive_upload`, `drive_ensure_folder`, `computer_organize`.
- Comando ejecutado: `/system/info`, `/system/readiness`.
- Resultado: runtime `operator_profile=dedicated_local`, four-eyes false, approval TTL 168h, readiness recomienda aflojar flags.
- Observación: mover/renombrar archivos locales no es irreversible en teoria, pero para un usuario real puede romper paths, proyectos o evidencia.
Impacto comercial: daño accidental local sin confirmacion fresca.
Impacto técnico: perfil local mezcla productividad con politica comercial.
Escenario real de fallo: `computer_organize` mueve archivos de trabajo o evidencia; rollback manual incierto.
Causa probable: se considero "PC dedicado" como equivalencia de confianza total.
Por qué esto es una zona débil/endeble: las acciones reversibles tambien pueden romper operaciones reales.
Cómo lo resolvería: crear perfil `commercial_local` mas estricto, exigir preview+approval para filesystem fuera de sandbox, y bloquear auto-approval sobre datos de usuario sensibles.
Archivos que probablemente habría que tocar: `config.py`, `actions/service.py`, `actions/computer.py`, UI de readiness, docs.
Tests que habría que agregar: dedicated/commercial policy matrix; no auto-approve fuera de allowlist; rollback/preview obligatorio.
Criterio de aceptación: ninguna operacion sobre archivos reales del operador se ejecuta sin preview persistido y decision humana salvo sandbox efimero.
Riesgo de reparación: Medio.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 6.

ID: AUDIT-007
Título: El cockpit F82 compila, pero el contrato E2E de autenticacion/navegacion/MemoryView esta roto
Severidad: P1 High
Categoría: UX issue / Missing test / Runtime risk
Área: Frontend / E2E
Estado: Confirmado
Evidencia:
- Archivo(s): `frontend/app/lib/hooks.ts:60-82`, `frontend/app/components/Sidebar.tsx:162-171`, `frontend/app/components/TopBar.tsx:46-55`, `frontend/app/views/SettingsView.tsx:63-79`, `frontend/tests/e2e/*`.
- Línea(s): E2E espera clases/labels/localStorage; UI usa los anclajes pero estado no coincide en tests.
- Comando ejecutado: `npx playwright test --reporter=list` contra `:3001`.
- Resultado: 10 fallos: JWT seeded queda vacio en TopBar, tabs no ganan clase `active` segun test, Settings labels no encontrados en momento esperado, recipe proposals section no aparece, mobile hamburger no aparece.
- Observación: no declare que la UI este rota para un humano sin reparacion; declare que su prueba oficial esta rota y no demuestra sanidad comercial.
Impacto comercial: no hay prueba confiable de navegacion principal, auth local ni estados moviles.
Impacto técnico: posible drift de contrato o bug de state/hydration.
Escenario real de fallo: operador pega JWT, cambia tab o entra en mobile y la UI no refleja estado o no carga data.
Causa probable: reescritura visual F82 sin actualizar E2E o regresion en hooks/responsive.
Por qué esto es una zona débil/endeble: el cockpit es la superficie operativa de aprobaciones y diagnostico.
Cómo lo resolvería: decidir anclajes contractuales, agregar `data-testid` estables, corregir localStorage seed/hydration si falla, reparar responsive, MemoryView recipe section.
Archivos que probablemente habría que tocar: `frontend/app/page.tsx`, `hooks.ts`, `Sidebar.tsx`, `SettingsView.tsx`, `MemoryView.tsx`, tests E2E.
Tests que habría que agregar: auth/localStorage determinista, 20 tabs con `aria-current`, mobile menu, recipe section, notifications.
Criterio de aceptación: Playwright completo verde en desktop/mobile y screenshots revisadas.
Riesgo de reparación: Medio.
Bloquea uso comercial: Sí parcial.
Prioridad de reparación: 7.

ID: AUDIT-008
Título: Integraciones externas clave estan configuradas, no demostradas en vivo dentro de esta auditoria
Severidad: P1 High
Categoría: Integration fragility / Fake readiness
Área: LLM / Google / GoDaddy / Mail / Browser / Code Director
Estado: Confirmado como no verificado
Evidencia:
- Archivo(s): `backend/tests/conftest.py:24-48`, `214-235`, docs de integraciones.
- Línea(s): tests unitarios bloquean factories LLM reales; integraciones reales quedan fuera del default.
- Comando ejecutado: `/system/credentials-status`, `/health/dashboard`, QA.
- Resultado: 18/21 credenciales configuradas; health marca varios ready/configured; no se ejecutaron writes ni llamadas LLM reales por politica de auditoria.
- Observación: esto no es necesariamente bug; es un limite de evidencia.
Impacto comercial: no se puede decir "operativo comercial" para proveedores sin smoke seguro y reproducible.
Impacto técnico: fallos de scope, token, cuota, provider o model/tool_choice pueden aparecer solo en runtime real.
Escenario real de fallo: LLM gateway cambia schema, Gmail/Drive token vence, GoDaddy rechaza prod, SMTP falla; tests siguen verdes.
Causa probable: suite hermetica prioriza seguridad y determinismo.
Por qué esto es una zona débil/endeble: integraciones son parte del valor comercial, pero no tienen gate live seguro.
Cómo lo resolvería: crear smokes read-only/live con opt-in, budgets, redaccion y sin writes; separar "configured", "last_verified_at", "verified_live".
Archivos que probablemente habría que tocar: `core/health.py`, `scripts/full-qa.sh`, docs/qa, tests integration, provider services.
Tests que habría que agregar: LLM no-spend/minimal, Google readonly, GoDaddy OTE/dry-run, SMTP auth noop, Code Director adapter dry-run.
Criterio de aceptación: cada integracion tiene prueba live segura o queda marcada NO VERIFICADA.
Riesgo de reparación: Medio.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 8.

## 7. Hallazgos P2 Medium

ID: AUDIT-009
Título: Telegram tiene 37 comandos implementados, pero la paridad real esta poco demostrada
Severidad: P2 Medium
Categoría: Missing test / Runtime risk
Área: Telegram
Estado: Confirmado parcial
Evidencia:
- Archivo(s): `backend/src/cognitive_os/integrations/telegram_bot.py:14-45`, `124-129`, `166-234`, `725-834`, `837-900`, `backend/tests/test_telegram_bot.py`.
- Línea(s): 37 `@command(...)`; auth por user_id; plain message routea a chat en `dedicated_local`; approvals usan `telegram:<chat_id>`.
- Comando ejecutado: `rg "^@command"`, inspeccion tests.
- Resultado: 37 comandos; 21 tests, concentrados en approvals, prefix resolver, algunos guards, capabilities, thread/reset/plain messages.
- Observación: no hay prueba runtime contra Telegram API ni happy path por cada comando documentado.
Impacto comercial: Telegram podria fallar en comandos documentados sin que QA lo detecte.
Impacto técnico: handlers hacen llamadas DB/servicios sincronas con `asyncio.run`; errores se reportan genericamente.
Escenario real de fallo: `/calendar`, `/drive`, `/mail`, `/research` o `/codebuild` fallan por config/backend y el usuario solo ve error tardio.
Causa probable: cobertura unitaria focalizada en riesgos previos, no matriz completa.
Por qué esto es una zona débil/endeble: Telegram es canal de aprobaciones y operacion fuera del panel.
Cómo lo resolvería: matriz de comandos documentados/implementados/testeados, tests de auth/backend down/JWT/config por comando critico.
Archivos que probablemente habría que tocar: `telegram_bot.py`, `test_telegram_bot.py`, docs.
Tests que habría que agregar: `/start`, `/help`, `/health`, `/stats`, `/config`, `/jobs`, `/approvals`, `/approve`, `/mail`, `/maps`, `/calendar`, `/drive`, `/research`, `/codebuild` happy/error paths.
Criterio de aceptación: cada comando tiene test de parse, auth, degraded y exito mockeado; approvals verifican AuditEvent actor.
Riesgo de reparación: Bajo/medio.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 9.

ID: AUDIT-010
Título: La documentacion esta inflada y contradictoria respecto de QA, comandos, integraciones y estado real
Severidad: P2 Medium
Categoría: Docs drift
Área: Docs
Estado: Confirmado
Evidencia:
- Archivo(s): `README.md:18-20`, `33-39`, `360-367`; `docs/USER_GUIDE.md:94-115`, `750-790`; `docs/COGNITIVE_OS_GUIDE.md:1-5`, `18`.
- Línea(s): claims de QA verde y 800 passed; Google autorizado y luego blocked en el mismo bloque; TOC dice "20 vistas" con anchor "18 vistas"; docs antiguas conservan conteos distintos.
- Comando ejecutado: inspeccion docs.
- Resultado: multiples estados historicos conviven con estado actual.
- Observación: documentacion sirve como contrato, pero no es confiable como evidencia.
Impacto comercial: operador toma decisiones con informacion equivocada.
Impacto técnico: QA/release se basa en snapshots no reproducibles.
Escenario real de fallo: Diego cree que Telegram/Google/E2E estan verdes y usa flujos no verificados.
Causa probable: docs acumulativas por fases sin una fuente unica generada.
Por qué esto es una zona débil/endeble: "grado comercial" exige docs contractuales exactas.
Cómo lo resolvería: docs se actualizan despues de gates verdes; tabla unica generada de endpoints/tasks/commands/migrations; marcar NO VERIFICADO.
Archivos que probablemente habría que tocar: README, USER_GUIDE, COGNITIVE_OS_GUIDE, ARCHITECTURE, docs/qa.
Tests que habría que agregar: doc check que compara conteos reales con claims principales.
Criterio de aceptación: ninguna afirmacion "operativo/verificado" sin comando/fecha/evidencia reproducible.
Riesgo de reparación: Bajo.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 10.

ID: AUDIT-011
Título: La suite backend es hermetica y valiosa, pero no prueba los flujos comerciales reales mas riesgosos
Severidad: P2 Medium
Categoría: Fake tests / Missing test
Área: QA / LLM / Integraciones
Estado: Confirmado
Evidencia:
- Archivo(s): `backend/tests/conftest.py:24-48`, `214-235`, `backend/tests/test_mail_api.py`, `docs/qa/FINAL_AUDIT_REPORT.md`.
- Línea(s): factories LLM reales bloqueadas por defecto; integration/slow excluidos; tests mail usan fake service.
- Comando ejecutado: full QA, inspeccion tests.
- Resultado: 799 tests pasan pero no prueban LLM real, SMTP real, Google real, GoDaddy real ni Telegram real.
- Observación: esto es correcto para hermeticidad, pero insuficiente para readiness comercial.
Impacto comercial: green tests pueden ocultar fallos de proveedores.
Impacto técnico: falta suite live opt-in con sandbox/dry-run.
Escenario real de fallo: provider real rompe tool calling; deterministic fallback permite que tests sigan verdes.
Causa probable: se priorizo no gastar/no tocar externo.
Por qué esto es una zona débil/endeble: las capacidades vendidas dependen de integraciones reales.
Cómo lo resolvería: agregar capa `integration-live-readonly` segura y separada del default.
Archivos que probablemente habría que tocar: tests integration, scripts QA, docs QA.
Tests que habría que agregar: smokes con credenciales sandbox/read-only y budgets.
Criterio de aceptación: release comercial exige unit hermetico + integration live read-only + E2E UI.
Riesgo de reparación: Medio por manejo de credenciales.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 11.

ID: AUDIT-012
Título: Mail sync manual desde UI corre en el proceso API aunque existe dispatch a cola `mail`
Severidad: P2 Medium
Categoría: Runtime risk / Worker mismatch
Área: Mail / Backend / Frontend / Celery
Estado: Confirmado
Evidencia:
- Archivo(s): `frontend/app/views/MailInboxView.tsx:36-43`, `backend/src/cognitive_os/api/app.py:2912-2926`.
- Línea(s): UI llama `/mail/sync`; endpoint ejecuta `PersonalMailService().sync_now()`; endpoint separado `/mail/sync/dispatch` usa Celery.
- Comando ejecutado: inspeccion estatica; `/jobs` mostro syncs por beat/worker.
- Resultado: hay dos caminos de sync con semantica distinta.
- Observación: el path UI puede bloquear API por IMAP/Gmail lento o fallido.
Impacto comercial: cockpit puede quedar ocupado o fallar por latencia de mail provider.
Impacto técnico: worker `mail` no es la unica via operativa pese a docs de queue.
Escenario real de fallo: GoDaddy IMAP lento causa timeout en request UI y usuario no ve job rastreable.
Causa probable: se mantuvo "sync now" sin reconducir a dispatch.
Por qué esto es una zona débil/endeble: una integracion externa lenta no debe correr en request/response.
Cómo lo resolvería: UI usa `/mail/sync/dispatch`, muestra job; `/mail/sync` queda solo admin/debug o con timeout claro.
Archivos que probablemente habría que tocar: `MailInboxView.tsx`, `api/app.py`, `mail/service.py`, tests.
Tests que habría que agregar: UI sync crea job; provider timeout produce JobEvent failed; API no bloquea.
Criterio de aceptación: todo sync manual visible como job con status y errores.
Riesgo de reparación: Bajo/medio.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 12.

ID: AUDIT-013
Título: OpenHarness `research/full` introduce Bash/file-write/FULL_AUTO dentro del backend cuando se habilita
Severidad: P2 Medium
Categoría: Security-operational / Architecture risk
Área: Research / OpenHarness / Filesystem
Estado: Confirmado
Evidencia:
- Archivo(s): `backend/src/cognitive_os/integrations/openharness_research.py:57-76`, `96-176`, `179-186`, `docs/SECURITY.md:126-148`, `docs/OPENHARNESS_FUSION.md:196-206`.
- Línea(s): preset `research` registra `BashTool`, `FileWriteTool`, `FileEditTool`, cron/task/team tools y usa `PermissionMode.FULL_AUTO`.
- Comando ejecutado: inspeccion estatica.
- Resultado: default flag `ENABLE_OPENHARNESS_RESEARCH=false`, pero si se activa el blast radius crece mucho.
- Observación: docs de seguridad lo reconocen; readiness comercial debe tratarlo como feature de alto riesgo, no como research normal.
Impacto comercial: ejecucion de shell/file writes dentro del proceso backend puede mutar workspace.
Impacto técnico: un LLM/tool loop externo opera con permisos del backend.
Escenario real de fallo: research con OpenHarness habilitado escribe archivos o ejecuta bash no esperado en workspace compartido.
Causa probable: integracion de upstream tool-heavy loop.
Por qué esto es una zona débil/endeble: es opt-in, pero peligroso si se habilita para "mejor research".
Cómo lo resolvería: preset `minimal` por defecto comercial, policy allowlist, sandbox OS/container, no FULL_AUTO salvo aprobacion explicita.
Archivos que probablemente habría que tocar: `openharness_research.py`, config defaults, docs, tests.
Tests que habría que agregar: research preset no incluye Bash/FileWrite en commercial; workspace containment; timeout/fallback.
Criterio de aceptación: OpenHarness no puede escribir/ejecutar shell fuera de sandbox aprobado.
Riesgo de reparación: Medio.
Bloquea uso comercial: Parcial si se habilita.
Prioridad de reparación: 13.

ID: AUDIT-014
Título: El runtime acumula 100 aprobaciones pendientes sin umbral visible de salud operacional
Severidad: P2 Medium
Categoría: Observability / Runtime risk
Área: HumanApproval / Memory / UX
Estado: Confirmado
Evidencia:
- Archivo(s): `/approvals` runtime, `workers/celery_app.py:160-163` approval reaper.
- Línea(s): reaper existe, pero runtime devolvio 100 `pending`, todas `deepagents_memory_update`.
- Comando ejecutado: `curl /approvals`.
- Resultado: 100 pendientes.
- Observación: puede ser demo/seed, pero para grado comercial un backlog grande debe ser una señal de salud o carga operativa.
Impacto comercial: operador no sabe que la cola humana esta saturada.
Impacto técnico: MemoryView/ApprovalsView pueden degradar; aprendizaje queda bloqueado o acumulado.
Escenario real de fallo: aprobaciones criticas se pierden entre ruido de propuestas de memoria.
Causa probable: no hay triage/limites/retention por tipo.
Por qué esto es una zona débil/endeble: la aprobacion humana es el control de seguridad principal.
Cómo lo resolvería: contadores por tipo/edad, alerta por backlog, paginacion/filtros, auto-expiry configurable para propuestas no criticas.
Archivos que probablemente habría que tocar: approval service/API, UI Approvals/Memory, reaper settings.
Tests que habría que agregar: backlog threshold aparece en health/readiness; paginacion; reaper por tipo.
Criterio de aceptación: aprobaciones criticas no quedan enterradas y health muestra backlog accionable.
Riesgo de reparación: Bajo/medio.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 14.

ID: AUDIT-015
Título: `docker compose config` sin env-file oculta variables vacias con warnings no bloqueantes
Severidad: P2 Medium
Categoría: Config fragility
Área: Infra / Docs
Estado: Confirmado
Evidencia:
- Archivo(s): `infra/docker-compose.yml`, runbook.
- Línea(s): compose usa variables `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `WEAVIATE_API_KEY`, `NEO4J_USER`, `NEO4J_PASSWORD`.
- Comando ejecutado: `docker compose -f cognitive-os/infra/docker-compose.yml config`.
- Resultado: OK con warnings "variable is not set. Defaulting to a blank string."
- Observación: el comando oficial recomendado debe incluir env-file o validacion previa.
Impacto comercial: operador puede levantar infra con credenciales vacias o mal interpoladas si no sigue exactamente el script.
Impacto técnico: errores de arranque/config aparecen tarde.
Escenario real de fallo: `docker compose config` parece OK pero generaria servicios con valores vacios.
Causa probable: Compose default behavior.
Por qué esto es una zona débil/endeble: configuracion es parte del arranque reproducible.
Cómo lo resolvería: script wrapper que falla si variables requeridas faltan; docs con comando unico correcto.
Archivos que probablemente habría que tocar: scripts init/start/status, docs/RUNBOOK, compose env validation.
Tests que habría que agregar: shellcheck/config validation en CI sin env y con env fixture.
Criterio de aceptación: config sin variables requeridas falla explicitamente.
Riesgo de reparación: Bajo.
Bloquea uso comercial: Parcial.
Prioridad de reparación: 15.

## 8. Hallazgos P3/P4

ID: AUDIT-016
Título: Conteos de endpoints/tareas/comandos aparecen como claims manuales y derivan con facilidad
Severidad: P3 Low
Categoría: Docs drift
Área: Docs / QA
Estado: Confirmado
Evidencia:
- Archivo(s): README y guias varias; runtime OpenAPI 136 paths; codigo route decorators ~144; docs dicen 143.
- Comando ejecutado: `rg "@app\\."`, `curl /openapi.json`.
- Resultado: conteos no alinean 1:1.
- Observación: puede haber diferencia legitima entre decorators y paths, pero los claims deben generarse.
Impacto comercial: menor, pero erosiona confianza.
Impacto técnico: revisiones futuras parten de numeros dudosos.
Escenario real de fallo: se cree que un endpoint existe por docs, no por OpenAPI.
Causa probable: conteos manuales por fases.
Por qué esto es una zona débil/endeble: los numeros son usados como prueba de madurez.
Cómo lo resolvería: generar tabla de endpoints/tasks/commands en QA.
Archivos que probablemente habría que tocar: scripts/docs QA.
Tests que habría que agregar: compare docs generated snapshot.
Criterio de aceptación: conteos vienen de script.
Riesgo de reparación: Bajo.
Bloquea uso comercial: No.
Prioridad de reparación: 16.

## 9. Zonas débiles o endebles

| Zona | Por qué es débil | Cómo puede fallar | Cómo fortalecerla | Test que la probaría |
|---|---|---|---|---|
| Mail send | Accion irreversible fuera del gate central | SMTP real por click UI | ActionRequest+HumanApproval+worker+AuditEvent | UI click crea approval, no SMTP; approval envia una vez |
| Health/readiness | `configured` se cuenta como OK | Dashboard verde con provider caido | readiness live separada | proveedor fake caido => degraded visible |
| Frontend E2E | Suite roja | Navegacion/JWT/mobile sin garantia | anclajes estables y repair | Playwright desktop/mobile verde |
| Learning auto-promote | Mutacion de comportamiento sin humano | warning incorrecto altera prompts | propuesta pendiente obligatoria | threshold no activa memoria |
| MCP filesystem | Scope `/home/jgonz` | lectura/escritura accidental amplia | limitar a workspace | config commercial rechaza `/home` |
| Kimi WebBridge | Browser real logueado | side effects por navigate/click | approval/policy por dominio | navigate sensible exige approval |
| dedicated_local | auto-approval amplio | mover archivos reales | perfil commercial estricto | computer_organize fuera sandbox queda pending |
| Telegram | paridad no demostrada | comando falla en calle | matriz de comandos | cada comando happy/degraded/auth |
| OpenHarness | FULL_AUTO shell/file tools | mutacion por research | sandbox/preset minimal | no Bash/FileWrite en commercial |
| Docs | claims no reproducibles | operador confia en estado viejo | docs post-QA generadas | doc claims vs script |

## 10. Flujos no suficientemente demostrados

| Flujo | Qué está implementado | Qué no se demostró | Qué test falta | Riesgo |
|---|---|---|---|---|
| A. Arranque | scripts, Docker, backend, worker, beat; runtime parcial arriba | frontend correcto como parte del stack en puerto esperado | smoke de launchers con puerto y proceso esperado | Alto |
| B. Auth/JWT | JWT helper, auth dependency | E2E JWT/localStorage verde | Playwright auth repair | Alto |
| C. Chat/research | LangGraph/DeepAgent/OpenHarness/fallback | LLM real, citations real, persistence real | live read-only LLM/research smoke | Alto |
| D. Document ingest | worker + tests | PDF corrupto/OCR/parser runtime | integration with fixtures corrupt/large | Medio |
| E. Document Analysis | service, events, exports, human review drafts | legal docs reales, no hallucinated citations | golden legal fixture with citations | Alto |
| F. Action Plane | validate/request/dispatch services | retries/failure end-to-end for each action | broker down + duplicate + stuck tests | Alto |
| G. Mail | sync/send service, logs | central approval send; SMTP failure path | approval worker mail integration | Critico |
| H. Google Ops | status/list/request endpoints | OAuth refresh/write approval real | Google sandbox/read-only + dry-run write request | Alto |
| I. GoDaddy | preview/request/dry-run code | OTE/prod write flow | OTE dry-run + approval no-write | Alto |
| J. Browser | headless + Kimi services | real profile policy | domain policy and timeout E2E | Alto |
| K. Computer/filesystem | inventory/organize | rollback and path safety over real home | sandbox path E2E | Alto |
| L. Office docs | exporters/actions | render/verify DOCX/XLSX/PPTX | artifact render smoke | Medio |
| M. Memory/learning | proposals, beat, auto loops | no hidden prompt drift | approval-only promotion suite | Alto |
| N. Code Director | planner/worker endpoints | adapters real dry-run, budget enforcement | adapter mock + CLI dry-run | Medio |

## 11. Frontend

- Estado real: build y lint pasan, pero E2E no pasa. El cockpit correcto en `:3001` falla 10/17 tests; `:3000` estaba ocupado por otra app.
- Rutas sanas: endpoints backend llamados por regression-critical desde Playwright pasaron; el HTML principal carga.
- Rutas frágiles: auth/JWT, Settings, navigation active state, Memory recipes, mobile hamburger, dashboard metric "componentes ok".
- Mismatch con backend: UI Mail "Enviar" llama endpoint directo de SMTP; UI "sync now" usa sync API directo en vez de dispatch worker.
- Network errors: en E2E contra `:3001`, fallos fueron principalmente DOM/state, no 5xx. `/system/mcp` es lento.
- Console errors: no se concluye 0 console errors porque suite falla antes de cierre verde.
- UX blockers: E2E no prueba ni garantiza operator flow de approvals/mail/health; puerto equivocado puede abrir app ajena.
- Tests faltantes: full-walk estable, dangerous buttons disabled/approval, degraded states para credenciales, forms de cada vista critica, notification center/palette.

## 12. Backend

- Estado real: amplio y en buena forma estructural; migraciones limpias; mypy/ruff check pasan; worker registrado.
- Endpoints sanos: `/health`, `/health/dashboard`, `/system/info`, `/system/readiness`, `/system/credentials-status`, `/openapi.json`, `/jobs`, `/approvals`, `/mail/status` respondieron read-only.
- Endpoints frágiles: `/system/mcp` lento; `/mail/messages/{id}/approve-send`; `/mail/sync`; WebBridge direct endpoints.
- Servicios frágiles: mail, health/readiness, OpenHarness, Kimi WebBridge, learning auto-promote.
- Error handling: varios fallos se devuelven, pero health puede ocultar no-verificacion como configured.
- Auth/RBAC: JWT funciona localmente; no audit completo RBAC por rol endpoint-by-endpoint.
- Tests faltantes: live safe integration, negative provider failure, approval bypass, per-endpoint RBAC matrix.

## 13. Celery/jobs/beat

- Workers: 1 node online (`celery@J`).
- Queues: `default`, `ingestion`, `agent_longrun`, `maintenance`, `mail` activas.
- Beat tasks: configuradas por flags en `workers/celery_app.py`; beat process visto en `ps`.
- Jobs: runtime `/jobs` mostro 50 completados recientes, principalmente `personal_mail_sync`, reapers.
- Eventos: `JobEvent` existe y muchas tareas lo usan; mail send directo no usa JobEvent.
- Retries: Celery tiene acks late, prefetch 1, time limits; no se probo broker failure en runtime.
- Idempotencia: existe en ActionRequest y mail local send guard; no verificado en end-to-end real.
- Riesgos: API path de mail sync directo; approval backlog; live beat lag no expuesto como health propio.
- Tests faltantes: worker crash/retry, broker down, duplicate dispatch, beat schedule visibility, queue lag.

## 14. Telegram

- Comandos documentados: `/start`, `/help`, `/health`, `/stats`, `/config`, `/capabilities`, `/agents`, `/skills`, `/memory`, `/consolidate`, `/jobs`, `/job`, `/cancel`, `/codebuild`, `/sandbox`, `/approvals`, `/approve`, `/reject`, `/threads`, `/chat`, `/ingest`, `/documents`, `/research`, `/runs`, `/audit`, `/tasks`, `/task`, `/done`, `/notes`, `/note`, `/mail`, `/gmaildigest`, `/maps`, `/calendar`, `/freebusy`, `/drive`.
- Comandos implementados: 37 decorators `@command`, coinciden en gran parte con la tabla.
- Comandos testeados: approvals/dispatch, openshell resolver, approval prefix, job wildcard, maps separator/disabled, calendar blocked, drive query required, mail disabled, sandbox disabled, capabilities, view coverage, thread/reset/plain messages, initial state.
- Paridad con UI: parcial. No hay prueba viva Telegram <-> REST <-> UI para la mayoria.
- Approvals: usa helper compartido y actor `telegram:<chat_id>` en codigo; no verificado en runtime real.
- Riesgos: long polling no probado, backend down no probado, token revocado/no autorizado no probado, comandos externos no cubiertos en happy path.
- Tests faltantes: matriz completa de comandos con auth, degraded, happy mocked, error backend, approvals actor/audit.

## 15. Action Plane y approvals

- Validate: endpoints y policy existen.
- Preview: browser/computer/drive/godaddy/documents tienen preview/request en codigo.
- Request: `ActionRequestService` central existe.
- HumanApproval: existe y se usa para muchas acciones; runtime tiene 100 pendientes.
- Dispatch: Celery dispatch con audit existe para ActionRequests y Telegram.
- Execute: worker `run_action_request` registrado.
- Audit: `AuditEvent` y `JobEvent` se usan en varios servicios; mail send queda fuera.
- Bypass encontrados: mail send directo; WebBridge navigate directo; auto-approve reversibles en `dedicated_local`; OpenHarness FULL_AUTO si se habilita.
- Riesgos: backlog, policy drift, docs que prometen mas que el path real.

## 16. Integraciones externas

| Integración | Estado | Cómo se verificó | Qué no se verificó | Modo degradado | Riesgo | Tests faltantes |
|---|---|---|---|---|---|---|
| LLM gateway | No verificado vivo | health configured, tests hermeticos | chat/tool_choice real | deterministic fallback | Alto | live minimal no-write |
| MCP | Operativo pero riesgoso | `/system/mcp` 200 en 10.77s | permisos efectivos de cada tool | timeout/error per server | Alto | MCP least-privilege |
| Google Calendar | No verificado | health ready/status | OAuth refresh/write create | blocked/ready status | Alto | readonly list + request no-write |
| Google Drive | No verificado | health ready/status | upload/organize real | status/readiness | Alto | sandbox folder dry-run |
| Gmail | No verificado | credentials/status | OAuth read live/digest | status | Medio | digest readonly smoke |
| GoDaddy DNS | No verificado | code/docs | OTE/prod dry-run live | status/preview | Alto | OTE dry-run test |
| Mail GoDaddy | Parcial alto riesgo | `/mail/status`, read list | SMTP send via approval worker | MailServiceError | Critico | approval send worker path |
| Browser | Parcial alto riesgo | Kimi ready, code | real navigation/click safety | status blocked/ready | Alto | domain/approval E2E |
| CapSolver | No verificado | health ready | API solve real | status | Medio | mocked + optional live |
| ElevenLabs | No verificado | health ready | STT/TTS real | status | Medio | tiny audio smoke opt-in |
| Kimi/WebBridge | Parcial | daemon running, code | extension connected false; mutations | blocked/ready | Alto | real-safe snapshot only |
| Code Director adapters | No verificado | endpoints/worker code | Claude/Codex/Kimi CLI dry-run | approval/budget code | Medio | adapter dry-run mocks |

## 17. DB, migraciones y aislamiento test/producción

- Alembic: `heads/current/check` OK, head `202605200003`.
- Modelos: no hice audit exhaustivo modelo por modelo, pero migracion check no detecto drift.
- Test DB: `backend/tests/conftest.py` redirige a DB con `test` y se niega a correr contra prod; esto es una fortaleza real.
- Riesgos: pytest requiere Postgres local y dropea/recrea DB de test; documentar claramente. Runtime leyo datos personales reales en `/mail/messages`, por lo que toda auditoria debe mantener redaccion.
- Drift: no Alembic drift; si hay docs drift de conteos.
- Tests faltantes: migracion downgrade/rollback no verificado; seed/reset production-safe; backup/restore.

## 18. Observabilidad y diagnóstico

- Health dashboard: responde, 17 componentes, pero mezcla configured/ready/ok.
- Readiness: existe y fue mas honesto: `2/9 capacidades habilitadas`.
- Logs: procesos escriben a `/tmp/cogos_*.log`; no hice analisis profundo de logs.
- AuditEvent: existe; DocumentAnalysis y ActionPlane lo usan; mail send no.
- JobEvent: existe; Celery y ActionRequest lo usan; mail send directo no.
- Correlation/request IDs: no verificado endpoint-by-endpoint.
- Errores visibles al operador: UI usa toasts y health, pero E2E no esta verde.
- Gaps: falta `last_verified_at`, queue lag, approval backlog health, MCP latency threshold, provider live status diferenciado.

## 19. Plan de reparación por oleadas

### OLEADA 0 — Safety freeze

- Objetivo: asegurar que nada toque produccion ni acciones externas mientras se repara.
- Cambios propuestos: trabajar en branch limpia; snapshot DB; confirmar `.env` no productivo; setear `TOOLS_READONLY_MODE=true`, `ENABLE_EMAIL_SEND=false`, `GODADDY_DNS_DRY_RUN_ONLY=true`, `GODADDY_ALLOW_PRODUCTION_WRITES=false`, `KIMI_WEBBRIDGE_ALLOW_MUTATIONS=false`; deshabilitar mail send real; bloquear `/mail/messages/{id}/approve-send` temporalmente o poner feature flag de no-send durante reparacion.
- Archivos probables: `.env.local` local no versionado, scripts de start/status, docs QA.
- Riesgos: detener flujos que Diego usa.
- Tests obligatorios: `git status --short`, health/readiness read-only, no pending external dispatch.
- Criterio de aceptación: entorno congelado, sin writes externos, backups/snapshot listos.
- Qué NO tocar: codigo productivo antes de aprobacion, migraciones, credenciales reales.
- Orden interno: branch/snapshot, flags, confirmar procesos, documentar estado.
- Dependencias: aprobacion de Diego.

### OLEADA 1 — Bloqueantes P0

- Objetivo: volver a un release gate reproducible y cerrar bypass de mail.
- Cambios propuestos: reparar test SW/version o SW; reparar `ruff format`; arreglar Playwright/UI contract; convertir mail send a `HumanApproval` + worker `mail` + `AuditEvent` + `JobEvent`.
- Archivos probables: `test_frontend_static_assets.py`, `frontend/tests/e2e/*`, `frontend/app/*`, `mail/service.py`, `api/app.py`, `workers/tasks.py`, `actions/service.py`, mail tests.
- Riesgos: duplicar envios si la migracion de flujo no es idempotente.
- Tests obligatorios: full QA, Playwright, mail approval tests, duplicate send tests.
- Criterio de aceptación: no SMTP sin approval central; QA oficial verde.
- Qué NO tocar: docs optimistas hasta que el codigo pase.
- Orden interno: format/SW, E2E, mail gate.
- Dependencias: Oleada 0.

### OLEADA 2 — Núcleo funcional

- Objetivo: endurecer chat/research/document analysis/jobs/events/approvals/audit.
- Cambios propuestos: readiness live separada; smoke LLM safe; document analysis golden legal fixtures; approval backlog signals; ensure JobEvent/AuditEvent for critical flows.
- Archivos probables: `core/health.py`, `agents/*`, `deepagents/*`, `document_analysis/*`, `ApprovalsView`.
- Riesgos: coste/latencia de probes.
- Tests obligatorios: live opt-in read-only, golden fixtures, negative provider failures.
- Criterio de aceptación: cada flujo critico tiene estado, error y trazabilidad.
- Qué NO tocar: external writes.
- Orden interno: health/readiness, events, core tests.
- Dependencias: P0 verde.

### OLEADA 3 — Async y reliability

- Objetivo: jobs no se pierden y estados no quedan colgados.
- Cambios propuestos: queue lag health, beat health, stuck job remediation, retry/backoff tests, dispatch idempotency across all action types, move mail sync UI to dispatch.
- Archivos probables: `workers/*`, `actions/dispatch_audit.py`, `api/app.py`, `MailInboxView.tsx`.
- Riesgos: cambios de semantica operacional.
- Tests obligatorios: broker down, duplicate dispatch, worker crash, beat disabled.
- Criterio de aceptación: operador puede diagnosticar y reintentar.
- Qué NO tocar: provider writes reales.
- Orden interno: observability, idempotency, UI job states.
- Dependencias: Oleada 1.

### OLEADA 4 — Frontend comercial

- Objetivo: cockpit confiable y honesto.
- Cambios propuestos: E2E anchors estables, degraded states, dangerous buttons disabled/request-only, notification center verified, mobile verified, no misleading "ready".
- Archivos probables: `frontend/app/components/*`, `views/*`, `tests/e2e/*`.
- Riesgos: snapshots/visual regressions.
- Tests obligatorios: desktop/mobile Playwright, forms, all 20 tabs, approvals, mail no-send, GoogleOps degraded.
- Criterio de aceptación: 0 console errors, 0 5xx, clear degraded states.
- Qué NO tocar: backend business logic salvo contract bugs.
- Orden interno: auth/nav, critical views, dangerous actions.
- Dependencias: Oleada 1.

### OLEADA 5 — Telegram

- Objetivo: paridad real, no solo lista de comandos.
- Cambios propuestos: command matrix tests; backend-down tests; auth/user_id tests; approval actor/audit tests; clear errors for missing config.
- Archivos probables: `telegram_bot.py`, `test_telegram_bot.py`, docs.
- Riesgos: Telegram Markdown escaping and sync/async behavior.
- Tests obligatorios: every command parse/happy/degraded; `/approve` dispatch; `/reset` persistence.
- Criterio de aceptación: 37 commands tested or docs reduced.
- Qué NO tocar: Telegram real API unless opt-in.
- Orden interno: matrix, approvals, external read commands.
- Dependencias: core stable.

### OLEADA 6 — Integraciones externas

- Objetivo: marcar cada integracion como verified, degraded o not verified con pruebas seguras.
- Cambios propuestos: live read-only smokes for LLM, Google, Gmail, GoDaddy OTE/dry-run, MCP, Kimi snapshot; least privilege MCP; OpenHarness sandbox.
- Archivos probables: provider services, config, docs/qa, scripts.
- Riesgos: credenciales/coste.
- Tests obligatorios: opt-in env-gated integration suite.
- Criterio de aceptación: ninguna integracion se declara lista sin `last_verified_at`.
- Qué NO tocar: production writes.
- Orden interno: readonly first, dry-run, then approved write simulations.
- Dependencias: safety freeze.

### OLEADA 7 — QA definitivo

- Objetivo: release gate completo.
- Cambios propuestos: `full-qa` incluye backend, frontend, Playwright, integration-readonly opt-in, doc claim checks, compose config validation.
- Archivos probables: `scripts/full-qa.sh`, `docs/qa/*`, CI.
- Riesgos: suite lenta.
- Tests obligatorios: full QA, stress QA, Playwright, integration safe.
- Criterio de aceptación: todo verde en entorno limpio documentado.
- Qué NO tocar: docs de estado antes de pasar.
- Orden interno: fast gates, E2E, opt-in live.
- Dependencias: Oleadas 1-6.

### OLEADA 8 — Documentación contractual

- Objetivo: docs reflejan solo lo probado.
- Cambios propuestos: reescribir estado actual, matrices generadas, "NO VERIFICADO" explicito, runbook de diagnostico.
- Archivos probables: README, USER_GUIDE, COGNITIVE_OS_GUIDE, ARCHITECTURE, docs/qa.
- Riesgos: prometer de mas de nuevo.
- Tests obligatorios: doc claim check contra scripts.
- Criterio de aceptación: cada claim comercial tiene evidencia/fecha/comando.
- Qué NO tocar: codigo.
- Orden interno: docs despues de gates.
- Dependencias: Oleada 7.

## 20. Orden exacto recomendado

1. Diego aprueba Oleada 0 y 1 solamente.
2. Congelar writes externos y crear snapshot/branch limpia.
3. Arreglar `ruff format --check` y SW static test sin tocar comportamiento.
4. Reparar E2E auth/nav/settings/mobile/MemoryView o actualizar tests si el nuevo contrato UI es correcto.
5. Rediseñar mail send para central `HumanApproval` + worker + AuditEvent/JobEvent.
6. Ejecutar full QA + Playwright hasta verde.
7. Separar health barato de readiness live.
8. Corregir learning auto-promote o documentarlo como excepcion aprobada por Diego.
9. Endurecer MCP/Kimi/dedicated_local policies.
10. Completar Telegram command matrix.
11. Agregar integration smokes read-only.
12. Actualizar documentacion contractual al final.

## 21. Criterios de aceptación finales

- `bash scripts/full-qa.sh` verde de punta a punta.
- `uv run pytest -q`, ruff check, ruff format, mypy, Alembic check verdes.
- `npm run lint`, `npm run build`, `npx playwright test --reporter=list` verdes en desktop/mobile.
- Ningun email real sale sin `HumanApproval approved`, worker `mail`, `JobEvent`, `AuditEvent` y idempotencia.
- Health distingue `configured`, `verified_live`, `degraded`, `not_verified`.
- `/system/readiness` no permite declarar comercial si capacidades prometidas no estan verificadas.
- Telegram tiene matriz completa documentado/implementado/testeado.
- MCP filesystem limitado al workspace o explicitamente bloqueado en perfil comercial.
- Kimi WebBridge y OpenHarness tienen sandbox/policy/approval claros.
- All external writes siguen preview/request/approval/dispatch/audit.
- Docs principales no contienen claims verdes sin evidencia reproducible.
- `git status --short` solo muestra cambios esperados de la reparacion aprobada.

## 22. Prompt de reparación — NO EJECUTAR HASTA APROBACIÓN DE DIEGO

PROMPT DE REPARACIÓN — NO EJECUTAR HASTA APROBACIÓN DE DIEGO

Actua como responsable de reparacion de Cognitive OS. No empieces sin aprobacion explicita de Diego. Trabaja solo Oleada 0 y Oleada 1 primero. No mezcles refactors con fixes. No toques documentacion de estado hasta que el codigo y tests esten verdes. No ejecutes acciones externas reales. No envies emails. No modifiques DNS. No apruebes ActionRequests ni HumanApprovals reales. Mantén todos los approval gates.

Objetivo inicial:
1. Congelar seguridad operativa.
2. Reparar las compuertas P0.
3. Mostrar diff y resultados.
4. Detenerte antes de Oleada 2.

Fase A — Safety freeze:
- Verifica `git status --short`.
- Confirma que no estas sobre cambios no entendidos.
- Asegura flags locales de no-write para mail/DNS/browser/Kimi/Action Plane.
- No modifiques `.env` versionado; si hace falta tocar env local, pide aprobacion.
- No uses proveedores externos salvo endpoints read-only ya autorizados.

Fase B — QA gates:
- Corrige el fallo de `backend/tests/test_frontend_static_assets.py` frente a `frontend/public/sw.js` o corrige el SW si el test era la fuente de verdad.
- Corrige el `ruff format --check` en `backend/tests/conftest.py`.
- Repara Playwright contra `frontend` en `:3001`: auth/localStorage, nav active state, Settings labels, Memory recipes, mobile hamburger.
- Ejecuta despues de cada grupo: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `npm run lint`, `npm run build`, `npx playwright test --reporter=list`.

Fase C — Mail P0:
- Cambia el flujo `MailInboxView`/`/mail/messages/{id}/approve-send` para que no llame SMTP directamente.
- Crear envio mail como approval/action/job: `HumanApproval` pendiente, dispatch en queue `mail` tras aprobacion, `MailSendLog`, `JobEvent`, `AuditEvent`.
- Mantener idempotencia de envio: doble click/retry no puede duplicar SMTP.
- Agregar tests: no SMTP antes de approval, approval envia una vez, failure SMTP queda failed visible, Telegram approve usa mismo actor/audit.

Restricciones:
- No crear migraciones salvo necesidad explicada.
- No actualizar dependencias.
- No tocar backups/snapshots.
- No tocar docs de estado hasta pasar QA.
- Si aparece riesgo de produccion o credencial real, detenerse y pedir decision.
- Antes de pasar a Oleada 2, mostrar resumen, diff, comandos y pedir aprobacion de Diego.

## Apéndice — Estado git final de la auditoría

Comando obligatorio ejecutado: `git status --short` desde la raiz del workspace.

- Escritura realizada por esta auditoria: `cognitive-os/docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md` dentro del directorio nuevo `cognitive-os/docs/audits/`.
- Incidente de auditoria: el worktree contiene muchos cambios tracked fuera del informe (`AGENTS.md`, `cognitive-os/README.md`, `cognitive-os/docs/USER_GUIDE.md`, `cognitive-os/frontend/*`, `cognitive-os/task_plan.md`, `cognitive-os/progress.md`, etc.). Esos cambios ya estaban presentes en el baseline inicial antes de crear este informe, pero deben tratarse como worktree sucio y no mezclarse con reparaciones sin decision explicita.
- Untracked preexistentes observados desde el baseline: `.claude/`, `.codex-audit/`, `.codex/`, componentes frontend nuevos, iconos PNG/SVG y `frontend/public/offline.html`.
- No intente revertir, formatear ni reparar ninguno de esos cambios.

## Declaración del auditor

1. No aceptaria ser responsable tecnico del proyecto en su estado actual para uso comercial serio. Aceptaria responsabilidad de una fase controlada de reparacion, no de operacion comercial.
2. Lo aceptaria bajo estas condiciones: gates P0 verdes, mail irreversible detras de approval central, readiness live honesta, E2E frontend verde, integraciones externas marcadas verified/no-verificadas con evidencia.
3. Las 5 reparaciones mas importantes: QA oficial verde; mail send centralizado con approval/audit/job; frontend E2E auth/nav/mobile reparado; health/readiness sin falsa certeza; politicas MCP/Kimi/dedicated_local reducidas.
4. Las 5 pruebas mas importantes que faltan: mail approval-send end-to-end; Playwright full-walk verde; LLM/research live read-only; Telegram command matrix con approvals; broker/worker failure/idempotency suite.
5. La parte mas peligrosa por fragilidad oculta: acciones externas/locales bajo apariencia de "read-only" o "reversible": mail SMTP, Kimi real browser, MCP filesystem y computer organize.
6. La parte mas solida: base backend estructural, Alembic/Postgres, Celery registration/queues y aislamiento de DB de test.
7. Diego debe decidir si quiere un sistema estricto de grado comercial o un perfil `dedicated_local` de alta autonomia. Esa decision define si se eliminan auto-approvals y auto-promotions o si se documentan como riesgo aceptado.
