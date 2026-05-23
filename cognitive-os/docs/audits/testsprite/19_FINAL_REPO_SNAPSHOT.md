# 19 · Final Repo Snapshot — 2026-05-23 07:01 UTC-4

## 1. Fecha/hora

`sáb 23 may 2026 07:01:01 -04` (Chile / CLT).

## 2. Git

- **Branch:** `codex/commercial-zero-friction-hardening`
- **HEAD:** `9ab77a44946e2ce91725b359c55ada33802eb8bc`
- **git status --short:** `0 modified files`
- **git diff --check:** OK (sin whitespace ni conflictos pendientes)

### Últimos commits (8)

```
9ab77a4 harden: LLM probe timeout + full-qa race guard + Ctrl+K anti-flake + commercial cert
a1d5b9c docs: sync all canonical markdowns to commit 647f103 + expand USER_GUIDE
647f103 fix: eager_defaults=True + zero-friction Playwright runner + TestSprite audit docs
9b22f77 docs: sync current commercial state
5953b40 fix: stabilize mcp inventory and frontend shortcuts
2c3cff6 commercial zero friction hardening
e76ef19 chore: finish repo hygiene (audit AUDIT-2026-I/J/K)
2ea3a01 docs: sync all project documentation with current state
```

## 3. Versiones

- Python 3.12.3
- uv 0.11.6 (x86_64-unknown-linux-gnu)
- Node v22.22.0
- npm 10.9.4
- Docker version 29.5.2, build 79eb04c
- Docker Compose version v5.1.4
- SO: Linux 6.17.0-22-generic (host)

## 4. Puertos (todos `127.0.0.1`, ningún bind público)

| Puerto | Proceso |
|---|---|
| 3001 | next-server (v16.2.6) pid 2010372 |
| 8000 | uvicorn / FastAPI pid 2010105 |
| 5432 | cognitive_os_postgres (docker) |
| 6379 | cognitive_os_redis (docker) |
| 7475 | cognitive_os_neo4j HTTP (docker) |
| 7688 | cognitive_os_neo4j Bolt (docker) |
| 8081 | cognitive_os_weaviate HTTP (docker) |
| 50052 | cognitive_os_weaviate gRPC (docker) |
| 10086 | kimi-webbridge pid 2010561 |

## 5. Procesos activos

| Componente | PIDs | Comando |
|---|---|---|
| uvicorn | 2010079/2010105 | `uv run uvicorn cognitive_os.api.app:app --host 127.0.0.1 --port 8000 --log-level info` |
| celery worker | 2010333+ | `worker -Q default,ingestion,agent_longrun,maintenance,mail --loglevel=info` |
| celery beat | 2010348/2010365 | `beat --loglevel=info` |
| next-server | 2010372 | Next.js 16.2.6 production server |
| telegram bot | 2010423 | `python -m cognitive_os.integrations.telegram_bot` |
| kimi webbridge | 2010561 + 1075410 | daemon Node + MCP bridge |

## 6. Docker containers (cognitive-os)

| Container | Status |
|---|---|
| cognitive_os_postgres | Up 10 hours (healthy) |
| cognitive_os_redis | Up 10 hours (healthy) |
| cognitive_os_weaviate | Up 10 hours (healthy) |
| cognitive_os_neo4j | Up 10 hours (healthy) |

## 7. Variables clave (redacted)

```
OPERATOR_PROFILE=dedicated_local           ✓
TELEGRAM_ENABLED=true                       ✓
ENABLE_EMAIL_SEND=false                     ✓ (no auto-send)
MAIL_REQUIRE_APPROVAL_FOR_SEND=true         ✓
KIMI_WEBBRIDGE_URL=http://127.0.0.1:10086
KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true         ✓
KIMI_WEBBRIDGE_ALLOW_MUTATIONS=false         ✓
KIMI_WEBBRIDGE_ALLOWED_DOMAINS=*             ✓
GODADDY_DNS_DRY_RUN_ONLY=true                ✓
ENABLE_MCP_CLIENT=true                       ✓
HEALTH_LLM_PROBE_TIMEOUT_SECONDS=10          ✓ (nuevo, pass 3)
LIVE_TESTS_ENABLED=<no presente>             ✓ (opt-out)
MAIL_ALLOW_EXPLICIT_SEND=<no presente>       ✓ (escape hatch cerrado)
```

## 8. Perfil operativo detectado

| Atributo | Valor |
|---|---|
| `operator_profile` | `dedicated_local` |
| `local_autonomy_mode` | `full` |
| `require_human_approval_for_external_actions` | `false` |
| `approval_require_four_eyes` | `false` |
| `action_payload_encryption_required` | `false` |
| `target_capabilities_unlocked` | 14/14 |
| `gaps` | `[]` |
| `summary` | `"Sin fricción. Todas las capacidades del perfil están activas."` |
| `git_commit (runtime)` | `9ab77a44946e` (matchea HEAD) |
| `alembic_head` | `202605200003` |

## 9. Estado de gates oficiales (verde al último cierre)

| Gate | Resultado | Log |
|---|---|---|
| `scripts/full-qa.sh` | 950 passed, 1 skipped, 28 deselected · EXIT=0 | `test-results/cert/full-qa-cert-final.log` |
| `scripts/stress-qa.sh 3` | 3 × 950 passed · EXIT=0 | `test-results/cert/stress-qa-cert.log` |
| Playwright × 3 stress | 3 × 31 passed · sin flakiness | `test-results/cert/playwright-stress-{1,2,3}.log` |
| `scripts/full-qa-live.sh` | 8 passed · EXIT=0 | `test-results/cert/full-qa-live-cert.log` |
| `verify_desktop_launchers.sh` | OK | `test-results/cert/verify_launchers-cert.log` |
| Migración up→down→up→check | clean | `/tmp/migrate_roundtrip.py` |

## 10. TestSprite MCP

- CLI: `@testsprite/testsprite-mcp` (npx)
- Config: `~/.config/@testsprite/testsprite-mcp-nodejs/config.json` (apiKey OK)
- Cuenta: Diego Manzur, Starter, créditos consumidos parcialmente en pasadas previas
- Plan generado: `testsprite_tests/testsprite_frontend_test_plan.json` (28 TC)
- Resultados acumulados: 10/10 PASSED en pasada 2 (batches TC001-003,007-008 + TC004,006,009-010,014)

## 11. Estado de docs/audits/testsprite

```
00_CANONICAL_READING_SUMMARY.md          (audit pass 1)
01_DISCOVERY_MAP.md                       (audit pass 1)
02_ZERO_FRICTION_RUNTIME_PROFILE.md       (audit pass 1)
03_RUNTIME_BOOT_LOG.md                    (audit pass 1)
04_BASELINE_QA.md                         (audit pass 1)
05_MASTER_TEST_PLAN.md                    (audit pass 1)
06_FINDINGS.md                            (audit pass 1)
07_REMEDIATION_PLAN.md                    (audit pass 1)
08_FIX_LOG.md                             (audit pass 1)
09_FINAL_REMEDIATION_REPORT.md            (audit pass 1)
10_REAUDIT_CONTEXT.md                     (audit pass 2)
11_REAUDIT_SNAPSHOT.md                    (audit pass 2)
12_OFFICIAL_GATES_RERUN.md                (audit pass 2)
13_CLOSURE_MATRIX.md                      (audit pass 2)
14_NEW_FINDINGS.md                        (audit pass 2 — P1 eager_defaults)
15_ZERO_FRICTION_VALIDATION.md            (audit pass 2)
16_FINAL_REAUDIT_REPORT.md                (audit pass 2)
17_COMMERCIAL_GRADE_CERTIFICATION.md      (hardening pass 3)
18_FINAL_CONTEXT_RECONSTRUCTION.md        (cierre absoluto — este ciclo)
19_FINAL_REPO_SNAPSHOT.md                 (cierre absoluto — este doc)
```

## 12. Estado de tests

- pytest backend: **950** tests collected, default deselect 28 (integration/slow/live_readonly).
- Playwright frontend: **31** tests collected (chromium-desktop + chromium-mobile).
- Live opt-in (`tests/live/`): **8** smokes read-only contra proveedores reales.

## 13. Confirmaciones rápidas

| Pregunta | Respuesta |
|---|---|
| ¿`dedicated_local/full` activo? | **SÍ** |
| ¿Kimi WebBridge daemon disponible? | **SÍ** |
| ¿Telegram bot vivo? | **SÍ** (allowlist configurada) |
| ¿Live tests habilitados por defecto? | **NO** (opt-in) |
| ¿Mail send bloqueado? | **SÍ** (`ENABLE_EMAIL_SEND=false`) |
| ¿MCP 5/5 servers? | **SÍ** (mem,gh,fs,cc,gem · 67 tools) |
| ¿Health overall pasivo? | `configured` (honesto — sin probe live) |
| ¿Operational backlog? | `ok` |
| ¿git diff --check? | OK |
| ¿Working tree limpio? | SÍ (0 modified files) |

## 14. Próximo paso

Fase 3: reboot controlado para certificar arranque desde cero (no usar
procesos actuales como evidencia del cierre final).
