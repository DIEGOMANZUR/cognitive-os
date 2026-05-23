# 25 · Zero-Friction Release Validation — 30 Puntos

Fecha: 2026-05-23 07:15 UTC-4
Mandato: validar que el sistema se siente y funciona como PC dedicado
mono-operador con cero fricción.

## Matriz de 30 asserciones

| # | Aserción | Estado | Evidencia |
|---|---|---|---|
| 1 | `dedicated_local/full` está activo | **PASS** | `/system/info.operator_profile=dedicated_local`; `/system/readiness.local_autonomy_mode=full` |
| 2 | UI muestra qué capacidades están disponibles | **PASS** | `/actions/capabilities` 8 capability sets `ready`; SettingsView tile "Capacidades bloqueadas" |
| 3 | Readiness dice qué falta y cómo arreglarlo | **PASS** | `/system/readiness.gaps=[]` con `summary="Sin fricción..."` (cuando hay gaps, cada uno incluye `capability`, `reason`, `remediation`) |
| 4 | Operador puede operar sin leer código | **PASS** | RUNBOOK §1 tiene los 4 launchers desktop; §2 el mint JWT one-liner; SettingsView muestra readiness en UI |
| 5 | Sin aprobaciones redundantes en dedicated_local/full | **PASS** | `require_human_approval_for_external_actions=false`, `approval_require_four_eyes=false`; 6/8 capabilities sin approval |
| 6 | Acciones locales permitidas se ejecutan sin bloqueo artificial | **PASS** | `/actions/computer/organize/preview` con root_path en `COMPUTER_ALLOWED_ROOTS` retorna `status=ok` (sin approval); browser_preview auto-dispatcha |
| 7 | Action Plane mantiene trazabilidad sin frenar | **PASS** | Cada ActionRequest crea AuditEvent + JobEvent; dispatch automático en reversibles |
| 8 | Telegram permite operar rápido | **PASS** | 37 commands + modo conversacional sin `/` en dedicated_local; bot live |
| 9 | Modo conversacional Telegram funciona | **PASS** | `test_telegram_bot.py::test_conversational_no_slash_routes_to_orchestrator` pasa |
| 10 | Kimi/Edge real usable | **PASS** | `/health/dashboard.kimi_webbridge.status=ready`, daemon corriendo en :10086, Edge DevTools en :9222, extensión conectada |
| 11 | Filesystem local usable | **PASS** | `COMPUTER_ALLOWED_ROOTS=[/home/jgonz, /tmp, /mnt]` configurado; `/actions/computer/organize/preview` con path válido retorna preview ejecutable |
| 12 | Code Director sin políticas absurdas | **PASS** | `CODE_DIRECTOR_BUDGET_MODE=soft`, planner LLM-driven con fallback heurístico; adapter `fake` rechazado en prod (HTTP 400 con mensaje claro), claude_code/codex/kimi/deepagent disponibles |
| 13 | Errores son accionables | **PASS** | F-08 mail send: "Mail sending is disabled by policy. Normal flow is read-only: generate a summary/proposed reply and Diego sends manually." (qué pasa + qué hacer); F-10 422 con campo exacto |
| 14 | UI no es decorativa | **PASS** | DashboardView muestra latencias reales, 14/18 ok contado en vivo, audit log con últimos eventos clickeables |
| 15 | Botones importantes hacen algo real | **PASS** | "Verificar en vivo" llama `/health/verify`; "Abrir Chat" cambia tab; "Ingestar PDF" abre modal; "Consolidar memoria" encola tarea Celery |
| 16 | Estados disabled/degraded explican motivo | **PASS** | `/health/dashboard` componentes con `detail` legible; `disabled` con motivo (`MAIL_ENABLED=false`, etc.) |
| 17 | Operador entiende qué variable falta | **PASS** | `/system/readiness.gaps` lista flag + remediation; sin gaps actualmente |
| 18 | Tareas largas van a background sin congelar API | **PASS** | Celery 5 colas + dispatch state machine; jobs visibles en UI con progress |
| 19 | Jobs muestran progreso | **PASS** | `Job.progress` field, `JobEvent` timeline; JobsView UI muestra histórico (5609 completed, 69 failed visibles en Dashboard) |
| 20 | Reapers limpian estados colgados | **PASS** | 3 reapers always-on en beat; `operational_backlog.status=ok` con counters; pasada 2 demostró: `reap_stuck_action_requests_task` limpió 1 stuck → backlog volvió a ok |
| 21 | Sin confirmaciones dobles innecesarias | **PASS** | Action requests reversibles (browser_preview, computer_organize, document_generate, drive_ensure_folder, etc.) se auto-dispatchan en `dedicated_local/full` |
| 22 | Mail mantiene excepción read-only | **PASS** | F-08 confirmado live: HTTP 409 con mensaje exacto. ENABLE_EMAIL_SEND=false, MAIL_ALLOW_EXPLICIT_SEND ausente, MAIL_REQUIRE_APPROVAL_FOR_SEND=true |
| 23 | `strict` existe sin contaminar `dedicated_local/full` | **PASS** | Settings condicionales por `operator_profile`; en dedicated_local los flags estrictos no se aplican; auth_local-token retorna 403 en strict |
| 24 | No se introdujo seguridad SaaS restrictiva como comportamiento principal | **PASS** | Pasadas 1/2/3 NO añadieron approvals nuevos; el único endurecimiento (`eager_defaults`) es fix SQLAlchemy idiomático sin impacto en política |
| 25 | Experiencia general comercialmente usable | **PASS** | Dashboard responde con datos vivos; las 20 tabs montan limpias; 0 console errors |
| 26 | Se siente como command center, no demo | **PASS** | UI muestra: 18 health components reales con latencia, 5609 jobs completados reales, 309 approvals reales, audit log con eventos reales `tool.webbridge.list_tabs`, configuración con LLM real (`gpt-5.5`) |
| 27 | Operador resuelve bloqueos desde UI/readiness | **PASS** | `/system/readiness.gaps[*].remediation` provee `env_var` + `value` exacto; UI tile lo muestra |
| 28 | Capacidades locales amplias no escondidas | **PASS** | `/actions/capabilities` lista 8 capacidad sets; UI Action Plane y GoogleOpsView las consumen |
| 29 | Acciones preparatorias no frenadas por exceso de confirmación | **PASS** | Preview endpoints (`browser/preview`, `computer/organize/preview`, `gmail/query/preview`, `godaddy/dns/preview`) son read-only y devuelven preview sin approval |
| 30 | Sistema privilegia diagnóstico/idempotencia en vez de bloqueo | **PASS** | Pattern visible en todo el código: idempotency UNIQUE index, AuditEvent en cada acción, reapers, health verify con probes reales, errores con detalle accionable |

## Resultado consolidado

**30 / 30 PASS.**

Cero fricción VERIFIED. El producto se opera como command center
local-first sin restricciones SaaS contaminando el perfil dedicado.

## Sub-verificaciones extra

### Auto-mint JWT (cero-friction)

```
$ curl -sI http://localhost:3001/ | head -1
HTTP/1.1 200 OK

→ La SPA detecta localStorage["cogos.token"] vacío
→ Llama POST /auth/local-token (sin auth, sólo dedicated_local/full)
→ Persiste localStorage["cogos.token"] con source="auto"
→ Polls comienzan inmediatamente con 200
```

### Playwright cero-friction

```
$ unset COGOS_JWT
$ npx playwright test --reporter=list
[playwright global-setup] auto-minted COGOS_JWT via
  http://127.0.0.1:8000/auth/local-token (dedicated_local/full)
Running 31 tests using 1 worker
...
  31 passed (41.9s)
```

### Auto-dispatch en reversibles

```
POST /actions/drive/folders/ensure/request {"name":"test-folder"}
→ status=queued, approval_id presente, job_id presente
   (auto-approved + auto-dispatched, sin click manual)
```

### Mail manteniendo contrato

```
POST /mail/messages/.../approve-send
→ HTTP 409
→ "Mail sending is disabled by policy. Normal flow is read-only:
   generate a summary/proposed reply and Diego sends manually."
```

## Restricciones que NO se introdujeron en esta fase

- No se cambió `KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*`.
- No se restringió `COMPUTER_ALLOWED_ROOTS`.
- No se forzó `approval_require_four_eyes=true`.
- No se exigió `require_human_approval_for_external_actions=true`.
- No se añadieron approvals nuevos a capabilities.
- No se forzaron live probes en polling pasivo.
- No se reintrodujo Tailwind/shadcn.
- No se debilitó el contrato mail.

**Cero degradación de cero fricción.**
