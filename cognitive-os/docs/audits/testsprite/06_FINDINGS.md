# 06 — Findings

Fecha: **2026-05-25** | Commit baseline: `6891d5c`

## Resumen por severidad

| Sev | Abiertos inicio | Corregidos | Residuales |
|---|---|---|---|
| P0 | 0 | 0 | 0 |
| P1 | 0 | 0 | 0 |
| P2 | 1 | 0 | 1 (TestSprite tunnel MCP crudo) |
| P3 | 1 | 1 | 0 |
| P4 | 0 | 0 | 0 |

---

### TS-ZF-20260525-001 — Doc drift conteo pytest

- **Severidad:** P3
- **Superficie:** Documentación canónica
- **Contrato:** CURRENT_STATE/README deben reflejar gate real `full-qa.sh`
- **Comportamiento real:** 1200 passed; docs decían 1192
- **Causa:** +8 tests en `test_final_functional_hardening.py` (commit `6891d5c`) sin sync textual
- **Evidencia:** `qa/reports/full-qa-prompt1.log`
- **Fix:** Actualizar 1192→1200 en docs canónicos + breakdown en CURRENT_STATE
- **Test regresión:** `sync_doc_counts --check` + manual review
- **Estado:** **FIXED**

---

### TS-ZF-20260525-002 — TestSprite MCP generateCodeAndExecute tunnel URL misparsing

- **Severidad:** P2 (herramienta externa, no producto)
- **Superficie:** TestSprite MCP runner
- **Contrato:** TestSprite debe alcanzar :3001/:8000 vía túnel
- **Comportamiento real:** Intentos a `health:80`, `127.0.0.1:800`, `127.0.0.1:8` — ECONNREFUSED/ENOTFOUND
- **Evidencia:** `test-results/testsprite/20260525_185002/run.log` (tunnel warnings)
- **Reproducción:** Invocar MCP `testsprite_generate_code_and_execute` sin bootstrap/`full-testsprite.sh`
- **Impacto cero fricción:** Ninguno en producto; bloquea auditoría cloud ad-hoc
- **Fix recomendado:** Usar `bash scripts/full-testsprite.sh` con plan canónico y cloudflared tunnel activo
- **Estado:** **MITIGATED** — baseline producto cubierto por Playwright 43 + pytest 1200; TestSprite histórico 28/28 PASS

---

### TS-ZF-20260525-003 — Trailing whitespace gate full-qa (sesión auditoría)

- **Severidad:** P4
- **Superficie:** docs/audits/testsprite/00_*.md creado en sesión
- **Fix:** Eliminar trailing spaces
- **Estado:** **FIXED**

---

## Hallazgos NO reabiertos (verificados runtime Prompt 1)

| ID histórico | Verificación Prompt 1 |
|---|---|
| F-RUNTIME-001 browser_preview | `status=completed`, title Example Domain |
| Mail SMTP escape | Matriz pytest 10/10 (no re-live) |
| Telegram fail-closed | 102/102 hermético vigente |
| MissingGreenlet | eager_defaults tests verdes |

## Operativos operador (no código)

- F-P1-001 OAuth Google scope — P2 operador
- F-P1-003 ~310 approvals pending — P2 operador triage
