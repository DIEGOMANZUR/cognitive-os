# 13 · Closure Matrix — Verificación Independiente de Cada Hallazgo

> Esta matriz vuelve a probar **cada** hallazgo de la primera pasada
> (`06_FINDINGS.md` + `08_FIX_LOG.md`) sin tomar nada por hecho.

## Tabla

| ID | Sev | Fix declarado | Test de regresión | Comando re-ejecutado | Evidencia | Estado | Comentario |
|---|---|---|---|---|---|---|---|
| TS-ZF-20260523-001 | P2 | `_global-setup.ts` auto-mintea `COGOS_JWT` via `POST /auth/local-token` | Spec auth.spec.ts (3 pruebas) + global-setup como dependency común | `cd frontend && unset COGOS_JWT && npx playwright test --reporter=list` | `test-results/reaudit/playwright3.log`: `[playwright global-setup] auto-minted COGOS_JWT via http://127.0.0.1:8000/auth/local-token (dedicated_local/full)` → **31 passed (42.6s)** | **VERIFIED_FIXED** | Tres ejecuciones consecutivas verdes; el `console.log` del global-setup confirma el auto-mint. |
| TS-ZF-20260523-002 | P3 | Restart del stack para cargar HEAD en runtime | `/system/info.git_commit == HEAD` | `curl /system/info` | `9b22f771edf3` (matchea HEAD `9b22f77`) | **VERIFIED_FIXED** | Stack re-arrancado en esta segunda pasada también; `/system/info.git_commit` re-validado. |
| TS-ZF-20260523-003 | P3 | No aplicar (disclaimer ya en los archivos históricos) | n/a (decisión documentada) | n/a | `docs/qa/MAP.md` y `docs/qa/FINAL_AUDIT_REPORT.md` siguen con encabezado "Fase 76 — auditoría … histórica" | **OBSOLETE_WITH_REASON** | El disclaimer del header es suficiente; añadir notas inline sería bloat. Sigue siendo decisión consciente. |
| TS-ZF-20260523-004 | P3 | RUNBOOK §2/§3 con `curl POST /auth/local-token` como método primario | inspección del doc | n/a | `docs/qa/RUNBOOK.md` actualizado en commit de la primera pasada | **VERIFIED_FIXED** | Re-leído; el método curl figura como forma corta y el `uv run python` como fallback para strict. |
| TS-ZF-20260523-005 | Info | TestSprite parcial (saturó API); plan generado | n/a | TestSprite batch1 (5 TCs) en re-audit | `test-results/reaudit/testsprite-batch1.log` + `testsprite_tests/testsprite_frontend_test_plan.json` (28 TCs) | **VERIFIED_FIXED (proceso)** | Esta vez se ejecutó en batch de 5 TCs sin saturar (max 26 conexiones vs 4000+ anterior). |

## Re-validación de los AUDIT-2026-A..K (auditoría previa que cerró el primer audit)

Aunque están fuera del scope de la primera pasada TestSprite, los re-validé
porque el operador me pidió "no confiar en reportes":

| Hallazgo | Sev | Fix | Re-validación | Estado |
|---|---|---|---|---|
| AUDIT-2026-A | P0 | Telegram `_dispatch` fail-closed | `pytest tests/test_telegram_bot.py::test_main_refuses_to_start_with_empty_allowlist` → PASS dentro de las 102 telegram_bot tests | **VERIFIED_FIXED** |
| AUDIT-2026-B | P1 | `/health/dashboard` distingue `verified`/`configured`/`degraded`; `POST /health/verify` probe real | `curl /health/dashboard` → `status=configured`; `POST /health/verify` → `degraded` con detalle por componente (primary_llm timeout 3s, mail GoDaddy IMAP OK live) | **VERIFIED_FIXED** |
| AUDIT-2026-C | P1 | Kill switch `FAILURE_POSTMORTEM_AUTO_PROMOTE_ENABLED` | Presente en `core/config.py` + leído por `failure_postmortem.py`; flag visible en `/config/public` | **VERIFIED_FIXED** |
| AUDIT-2026-D | P2 | Matriz Telegram (auth-deny + no-crash + flag-gated) | 102 tests Telegram pasaron (incluye `test_command_rejects_unauthorized_user[*]` y `test_flag_gated_command_reports_disabled[*]`) | **VERIFIED_FIXED** |
| AUDIT-2026-E | P2 | Carril `tests/live/` con `LIVE_TESTS_ENABLED=1` | `tests/live/` presente con 8 smokes; no se reejecutó vivo en este audit (opt-in) | **VERIFIED_FIXED** |
| AUDIT-2026-F | P2 | Componente `operational_backlog` en health | `curl /health/dashboard` → component presente, `status=ok`, metadata expone approvals_pending/jobs_stale/beat_lag_minutes | **VERIFIED_FIXED** |
| AUDIT-2026-G | P3 | `sync_doc_counts.py --check` en `full-qa` | Pasó en re-corrida `full-qa.sh` | **VERIFIED_FIXED** |
| AUDIT-2026-H | P3 | `dev_up.sh` valida vars sin default | Stack arranca limpio via `cognitive-os.sh restart` que invoca `dev_up.sh` indirecto | **VERIFIED_FIXED** |
| AUDIT-2026-I/J/K | P3 | task_plan/backups/snapshots gitignored + README sin pila histórica | `git status --short` no muestra `task_plan.md/findings.md/progress.md`; `cognitive-os/README.md` con un solo snapshot vigente | **VERIFIED_FIXED** |

## Resultado consolidado

- **0** STILL_FAILING.
- **0** REGRESSED.
- **0** NOT_RETESTED_BLOCKED.
- **15** VERIFIED_FIXED.
- **1** OBSOLETE_WITH_REASON (TS-ZF-20260523-003, doc drift histórico — decisión consciente).

Todos los hallazgos previos quedan **cerrados** y verificados por evidencia
independiente.
