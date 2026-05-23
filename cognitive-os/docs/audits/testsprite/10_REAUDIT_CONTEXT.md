# 10 · Re-Audit Context — Auditor Independiente (2026-05-23)

## Auditor

Claude Opus 4.7, segunda pasada (post-remediación). Mandato: intentar
romper el sistema, validar cada fix, buscar regresiones.

## Lo que se corrigió antes (docs/audits/testsprite/06_FINDINGS.md + 08_FIX_LOG.md)

| ID | Severidad | Fix declarado |
|---|---|---|
| TS-ZF-20260523-001 | P2 | `_global-setup.ts` auto-mintea COGOS_JWT via `POST /auth/local-token` en dedicated_local/full |
| TS-ZF-20260523-002 | P3 | Stack reiniciado para cargar HEAD `9b22f77` en runtime |
| TS-ZF-20260523-003 | P3 | Decisión: no aplicar (disclaimer ya presente en historical sections) |
| TS-ZF-20260523-004 | P3 | RUNBOOK §2/§3 usa `curl POST /auth/local-token` como método primario |
| TS-ZF-20260523-005 | Info | TestSprite parcial — saturó accept-queue uvicorn |

## Lo que debe revalidarse

1. **Auto-mint Playwright:** correr `unset COGOS_JWT && npx playwright test`
   → debe pasar 31/31.
2. **Runtime carga HEAD:** `/system/info.git_commit` debe matchear
   `git rev-parse HEAD`.
3. **Health honesto:** `/health/dashboard.status="configured"` mientras
   componentes LLM/embeddings/mail/mcp_client estén "configured".
4. **MCP 5/5 y 67 tools.**
5. **Readiness 14/14 capacidades.**
6. **Mail read-only:** sin draft, sin send, escape hatch 3-flags-required.
7. **Telegram fail-closed:** allowlist no vacía, dispatch correcto.
8. **Action Plane idempotente:** dispatch_state, idempotency key, audit.
9. **Reapers operacionales:** componente `operational_backlog`.

## Superficies sensibles tras la primera pasada

- `frontend/playwright.config.ts` — global setup nuevo, puede romper specs.
- `frontend/tests/e2e/_global-setup.ts` — nuevo, falla silenciosa ante
  backend caído (¿se silencia demasiado?).
- `frontend/tests/e2e/_helpers.ts` — mensaje de error refrescado; tests
  que parsearan el mensaje literal podrían quebrarse.
- `docs/qa/RUNBOOK.md` — método de mint cambió.
- Runtime: tras restart, posible re-condicionamiento de health a
  "configured" por probes en frío.

## Contratos de cero fricción a verificar

- `/auth/local-token` mintea sin auth en dedicated_local/full.
- `/system/readiness` 14/14 unlocked, gaps=[].
- `require_human_approval_for_external_actions=false`.
- `approval_require_four_eyes=false`.
- 14/14 capabilities unlocked.
- Comando `unset COGOS_JWT && npx playwright test` debe pasar.
- Telegram conversacional sin `/` activo.
- Command palette Ctrl/Cmd+K capture phase.

## Tests nuevos existentes

- `frontend/tests/e2e/_global-setup.ts` — auto-mint JWT. No tiene
  assertions; corre como setup. No genera "test passed" sino que habilita
  los 31 que sí lo hacen.

## Riesgos residuales declarados

1. **TestSprite saturó API** (4000+ connections, accept-queue exhausto).
   Riesgo de proceso, no de producto. Recomendación previa: limitar
   `testIds` a subsets.
2. **Carril live no se re-ejecutó** porque `LIVE_TESTS_ENABLED` no estaba
   activo. Último gate live: 8/8 read-only OK (pre-audit).
3. **Stress-qa no se re-ejecutó** post-fix. Delta de código es localizado
   (runner Playwright + doc), pero técnicamente queda pendiente.
4. **Doc drift histórico** (`docs/qa/MAP.md`, `FINAL_AUDIT_REPORT.md`) no
   se "limpió" por ser bloat. Riesgo cosmético.

## Plan de esta segunda pasada

1. Snapshot estado actual (Fase 1).
2. Restart controlado si hace falta (Fase 2). Si el runtime ya está
   sano post-primera pasada, no destruir trabajo: snapshot y seguir.
3. Gates oficiales completos + stress-qa esta vez (Fase 3).
4. TestSprite re-audit en **subsets de 4-6 TC** para evitar saturar API
   (Fase 4).
5. Closure matrix de cada hallazgo previo (Fase 5).
6. Pruebas complementarias + chaos básico (Fase 6).
7. Nuevos hallazgos + fix en sitio (Fase 7-8).
8. Validación cero fricción (Fase 9).
9. Reporte final (Fase 10).

Cualquier nuevo P0/P1/P2: corregir inmediatamente, agregar test, no
diferir.
