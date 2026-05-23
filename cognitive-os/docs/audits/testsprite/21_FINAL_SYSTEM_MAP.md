# 21 · Final System Map — Regenerado Desde Código + Runtime

Fecha: 2026-05-23 07:05 UTC-4
Origen: inspección directa del código y consultas live al runtime
arrancado en Fase 3.

## 1. Conteos canónicos (live + sync_doc_counts)

| Concepto | Conteo live | Documentado | Estado |
|---|---|---|---|
| Endpoints REST `@app.*` | **147** | 147 | ✓ |
| OpenAPI paths | **140** (147 method entries) | — | ✓ (algunas paths con múltiples métodos) |
| Tareas Celery `cognitive_os.*` | **23** | 23 | ✓ |
| Celery queues | 5 (default/ingestion/agent_longrun/maintenance/mail) | 5 | ✓ |
| Beat jobs registrados | **13** (3 reapers always-on + 10 condicionales) | 13 | ✓ |
| Migraciones Alembic | **20** (head `202605200003`) | 20 | ✓ |
| Frontend views `.tsx` | **20** | 20 | ✓ |
| Telegram commands (`ALL_TELEGRAM_COMMANDS`) | **37** | 37 | ✓ |
| Health components (`_safe_check`) | 17 + 1 checkpointer = **18 totales** | 18 | ✓ |
| MCP servers live | **5/5** | 5 | ✓ |
| MCP tools live | **67** | 67 | ✓ |
| Action types (CHECK constraint) | **11** | 11 (WORKFLOW_EXPORTABLE_TYPES tiene 9 — los exportables) | ✓ |
| Action capability sets live | **8** | 8 | ✓ |
| Backend pytest tests | **950** | 950 | ✓ |
| Frontend Playwright | **31** | 31 | ✓ |

`scripts/sync_doc_counts.py --check` → **OK: conteos canónicos sincronizados**.

## 2. Endpoints (147 REST decorators)

Familias detectadas:

```
/health, /health/dashboard, /health/verify
/auth/local-token
/system/{info,readiness,mcp,credentials-status}
/chat, /threads/*
/documents/*, /document-analysis/*
/jobs/*
/approvals/*
/actions/* — capabilities + browser{,/preview/request,/interactive/request,/validate}
            + computer/organize/{preview,request}
            + documents/request + documents/preview + documents/status
            + drive/{folders,files,organize}/{preview,request}
            + calendar/{events,freebusy,status}
            + maps/{geocode,route,status}
            + gmail/{query,query/preview,status}
            + godaddy/{dns,status}
            + webbridge/{click,fill,evaluate,close_session,list_tabs,screenshot}
            + requests/{action_request_id}/{,cancel,workflow}
/research/*
/code-director/{run,{job_id},{job_id}/download,{job_id}/events}
/mail/*
/deepagents/* (memory/skills/learning)
/sandbox/openshell/*
/assist/{tasks,notes,notes/search}
/audit/events
/config/public
/openapi.json
/docs (Swagger)
```

## 3. Action Plane: capacidades y políticas en `dedicated_local/full`

| Capability | Status | Requires Approval | Dry-Run Only | Notas |
|---|---|---|---|---|
| browser | ready | **false** | false | `allowed_domains=["*"]`, Playwright |
| computer | ready | **false** | false | `allowed_roots=[/home/jgonz, /tmp, /mnt]` |
| documents | ready | **false** | false | DOCX/XLSX/PPTX gen |
| gmail | ready | **false** | false | read-only digest (no draft/send) |
| godaddy | ready | **false** | **true** | DNS dry-run forzado |
| maps | ready | **false** | **true** | read-only routes/freebusy |
| google_calendar | ready | **true** | false | preview-first; create via /request |
| google_drive | ready | **true** | false | upload/folder/organize via /request |

Cero fricción aplicada: 6/8 capabilities sin approval, 2/8 con approval
para Calendar/Drive (contrato del Action Plane, no del perfil).

## 4. Action types (CHECK constraint)

11 declarados en `ActionRequest.action_type` y `ck_ar_action_type`:

```
computer_organize
browser_navigation
gmail_query
godaddy_dns_change
document_generate
browser_preview
browser_interactive
calendar_create_event
drive_upload_file
drive_ensure_folder
drive_organize_files
```

Migración `202605170001_action_requests_drive_folder_organize.py` añadió
los últimos 2 (drive_ensure_folder, drive_organize_files) — fix de la
Fase 65.

## 5. Health components (18 totales)

17 vía `_safe_check` + 1 `checkpointer`:

```
postgres, redis, weaviate, neo4j,
primary_llm, embeddings, workers, langsmith,
voice, maps, google_calendar, google_drive,
kimi_webbridge, captcha_solver, mail, mcp_client,
operational_backlog,    ← AUDIT-2026-F
checkpointer            ← componente especial
```

`primary_llm` y `embeddings` ahora usan el timeout específico
`HEALTH_LLM_PROBE_TIMEOUT_SECONDS=10` (TS-ZF-20260523-007 fix).

## 6. Beat jobs (13)

Always-on (3 reapers):
```
action-request-reaper
approval-reaper
stale-jobs-reaper
```

Condicionales por feature flag (10):
```
consolidate-deepagent-memory-all
failure-postmortem-scanner
nightly-reflection
personal-assistant-reminders
personal-mail-digest    (10:00 + 20:00 Chile)
personal-mail-sync
recipe-extractor
skill-promoter
telegram-gmail-digest
tool-scorecard-aggregator
```

## 7. Telegram commands (37)

Canónicos en `tests/test_telegram_bot.py::ALL_TELEGRAM_COMMANDS`:

```
agents, approvals, approve, audit, calendar, cancel, capabilities,
chat, codebuild, config, consolidate, documents, done, drive, freebusy,
gmaildigest, health, help, ingest, job, jobs, mail, maps, memory,
note, notes, reject, research, reset, runs, sandbox, skills, start,
stats, task, tasks, threads
```

37 verified live por `test_command_registry_matches_canonical_set` →
102 tests Telegram pasan (auth-deny + no-crash + flag-gated).

## 8. Comparación: documentación vs código

| Documento canónico | Conteo declarado | Conteo real | Estado |
|---|---|---|---|
| `CURRENT_STATE.md` AUTO:counts | 147 endp / 23 tasks / 20 mig / 20 views | Coinciden | ✓ |
| `AGENTS.md` snapshot | 147 / 23 / 5 colas / 13 beat / 20 mig / 37 cmd / 18 health | Coinciden | ✓ |
| `USER_GUIDE.md` header | 147 / 23 / 5 / 13 / 20 / 37 / 18 / 31 PW | Coinciden | ✓ |
| `RUNBOOK.md` snapshot | 147 / 23 / 5 / 13 / 20 / 37 / 18 + Playwright 31 | Coinciden | ✓ |
| `qa/MAP.md` | 31 PW desktop+mobile, 947→**950** tras audit | Coinciden (tras cierre pass 3) | ✓ |
| `qa/FINAL_AUDIT_REPORT.md` | 947→**950** | Coinciden | ✓ |
| `ARCHITECTURE.md` | 147 / 23 / 5 / 13 / 20 / 20 views / 18 / 37 / 5 MCP / 67 tools | Coinciden | ✓ |

Sin drift declarado al inicio de Fase 5.

## 9. Tests vs superficies (cobertura)

| Superficie | Tests | Estado |
|---|---|---|
| 147 endpoints REST | 950 pytest backend + 31 Playwright + 8 live + 10 TestSprite re-audit | Cobertura comercial verificada |
| 23 tareas Celery | 102 tests Telegram + tests focales reapers + tests integration deselected por default | Cobertura completa hermética + carriles opt-in |
| 18 health components | `test_health_dashboard.py` + `test_health_llm_probe_timeout.py` | 6 tests health + 3 nuevos timeout |
| Action Plane idempotency | `test_actions.py` 78 tests + `test_action_request_eager_defaults.py` 3 nuevos | Cubierto |
| Mail contract | `test_mail.py` + `mail-readonly-contract.spec.ts` + negative live test | Cubierto |
| MCP integration | `test_mcp_client.py` + live verification | Cubierto |
| 20 frontend views | `all-views-console-guard.spec.ts` + 19 specs más | Cubierto |
| 37 Telegram commands | `test_telegram_bot.py` matriz parametrizada × 78 cases | Cubierto |
| Migraciones | `alembic check` + roundtrip up→down→up | Cubierto |

## 10. Perfil `dedicated_local/full` esperado vs implementado

| Setting | Esperado | Implementado | Estado |
|---|---|---|---|
| `operator_profile` | `dedicated_local` | `dedicated_local` | ✓ |
| `local_autonomy_mode` | `full` | `full` (live readiness) | ✓ |
| `require_human_approval_for_external_actions` | `false` | `false` | ✓ |
| `approval_require_four_eyes` | `false` | `false` | ✓ |
| `action_payload_encryption_required` | `false` | `false` | ✓ |
| Auto-mint JWT (`/auth/local-token`) | sin auth en dedicated_local/full | OK (403 en strict) | ✓ |
| 14/14 capacidades unlocked | 14/14, gaps=[] | 14/14, gaps=[] | ✓ |

## 11. Controles funcionales irrenunciables

| Control | Implementado | Estado |
|---|---|---|
| AuditEvent + JobEvent + ActionRequest timeline | sí | ✓ |
| Idempotency UNIQUE index parcial | sí (PostgreSQL where status IN ('previewed','pending_approval','queued','running')) | ✓ |
| 3 reapers always-on en beat | sí (action_request, approval, stale_jobs) | ✓ |
| `operational_backlog` health | sí (AUDIT-2026-F) | ✓ |
| Mail send blocked sin 3 flags | sí (HTTP 409 + mensaje exacto) | ✓ |
| GoDaddy DNS dry-run forzado | sí (`GODADDY_DNS_DRY_RUN_ONLY=true`) | ✓ |
| Kimi WebBridge mutaciones bajo approval | sí | ✓ |
| Telegram fail-closed | sí (`_dispatch` rechaza si user_id ∉ allowlist) | ✓ |
| DB tests aislada | sí (`cognitive_os_test`, recreada por corrida) | ✓ |

## 12. Resultado de Fase 4

**Cero drift detectado entre código, documentación y runtime live.**
`sync_doc_counts.py --check` OK. Todos los conteos canónicos coinciden.
Cobertura de tests verificada superficie por superficie. Procedo a
Fase 5 (gates oficiales).
