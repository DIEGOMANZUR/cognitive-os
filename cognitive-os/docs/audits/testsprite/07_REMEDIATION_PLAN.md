# 07 — Remediation Plan

Fecha: **2026-05-25** | Orden de ejecución

## P0 — Ninguno

No se detectaron P0 en baseline Prompt 1.

## P1 — Ninguno

Flujos centrales verdes (pytest 1200, Playwright 43, stress 3×).

## P2 — TestSprite tunnel MCP crudo

| Campo | Valor |
|---|---|
| ID | TS-ZF-20260525-002 |
| Archivos | `scripts/full-testsprite.sh`, `testsprite_tests/tmp/config.json`, cloudflared config |
| Root cause | Invocación MCP directa sin runner canónico del repo |
| Solución | Documentar + usar `full-testsprite.sh`; no cambiar producto |
| Validación | `qa/reports/testsprite_latest_summary.md` histórico 28/28 |
| Riesgo | Bajo |
| Rollback | N/A |

## P3 — Doc drift 1192→1200

| Campo | Valor |
|---|---|
| ID | TS-ZF-20260525-001 |
| Archivos | README, CURRENT_STATE, RUNBOOK, USER_GUIDE, PROJECT_GUIDE, ARCHITECTURE, ACCEPTANCE_CHECKLIST, scripts/README, docs/qa/* |
| Solución | sed 1192→1200 + breakdown CURRENT_STATE |
| Test | `bash scripts/full-qa.sh` |
| Estado | **EJECUTADO** |

## Drift docs/código/tests

- Conteos estructurales (150 endpoints, 20 vistas): `sync_doc_counts --check` OK
- Conteo pytest: manual update aplicado

## Ejecución inmediata (sin aprobación)

1. ✅ Corregir docs 1200 passed
2. ✅ Re-run full-qa verde
3. ✅ Documentar hallazgos 06–09
4. ⏭ Prompt 2: re-audit TestSprite serial via `full-testsprite.sh` + live smokes opt-in
