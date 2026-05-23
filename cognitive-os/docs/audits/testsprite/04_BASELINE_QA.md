# 04 · Baseline QA Gates

Fecha: 2026-05-23
Stack vivo en `dedicated_local/full`, runtime `2c3cff6`, HEAD `9b22f77`.

## 1. `bash scripts/full-qa.sh` → **VERDE**

```
944 passed, 1 skipped, 28 deselected in 65.42s
ruff OK, ruff format OK, mypy OK (135 source files)
Alembic check OK (sin drift)
sync_doc_counts --check OK
npm ci OK (351 packages, 0 vulnerabilities)
eslint OK (--max-warnings 0)
Next.js production build OK (4 static pages prerendered)
git diff --check OK
EXIT=0
```

Log: `test-results/baseline/full-qa.log`

## 2. `npx playwright test` (con COGOS_JWT exportado) → **VERDE**

```
31 passed (38.9s)
```

20 spec files cubren:

- all-views console guard (20 vistas montadas, 0 console.error)
- auth (sin/válido/inválido)
- commercial zero-friction smoke
- error/empty/loading states (malformed payloads → empty, no ErrorBoundary)
- forms (Settings persistencia)
- glass cockpit (Ctrl+K palette, notif center ESC, asArray, skip-link a11y)
- health verified vs configured (configured pintado como warning, no danger)
- jobs/approvals/action lifecycle
- mail read-only contract (sin botón Send, sin Draft)
- mail digest/sync
- mobile PWA shell
- navigation hotkeys + command palette
- navigation 20 tabs (sin pantalla blanca/console.error)
- recipe proposals (Memoria → Fase A)
- regression-critical (health/system/readiness/system/mcp/config/public)
- responsive viewport mobile
- smoke (Dashboard sin spinner infinito)
- zero-friction dedicated_local
- forms persistence

Log: `test-results/baseline/playwright2.log`

## 3. Conclusión de baseline

El baseline está en estado verde reproducible. Cualquier hallazgo nuevo
deberá referenciar este commit base (HEAD `9b22f77`, runtime `2c3cff6`).

## 4. Falsa alarma resuelta

Primer intento de Playwright sin `COGOS_JWT` exportado: 19 fallaron por
`Error: COGOS_JWT env var is missing`. Esto NO es un bug del producto sino
contrato del runner. Documentado en `docs/qa/RUNBOOK.md §2`. Re-ejecutado
con `COGOS_JWT=$(curl POST /auth/local-token)` → 31/31.

**Recomendación de Phase 6:** mejorar la documentación del runner para que
el operador no se choque con esto al ejecutar Playwright manualmente.
Eventualmente, hacer que el helper auto-genere el JWT vía `POST
/auth/local-token` en `dedicated_local/full` cuando no se pase env var.
Esto se anota como mejora P3 en `06_FINDINGS.md`.

## 5. Stress-qa y full-qa-live

No se relanzaron en este audit porque:

- `stress-qa.sh 3` ya está verde según `CURRENT_STATE.md` y reincidir solo
  añade 3 × 65s de QA sin contraevidencia.
- `full-qa-live.sh` se omite porque `LIVE_TESTS_ENABLED=1` no está activo en
  `.env` y el audit no toca proveedores reales. El último gate live reportó
  8 passed contra Google/GoDaddy/Telegram/Kimi/LLM read-only.

Si la fase 13 (final TestSprite) requiere stress, se ejecutará entonces.
