# 03 Coverage Gaps

| ID | Severidad | Area | Brecha | Evidencia | Riesgo | Reparacion |
|---|---|---|---|---|---|---|
| GAP-001 | P1 | Release | `full-qa.sh` no falla si `alembic check` falla con `.env` presente | Script imprime `WARN` y sigue | Gate verde falso ante drift DB | Corregido: Alembic hard-fail cuando hay configuracion DB; skip solo sin `.env`/`DATABASE_URL` |
| GAP-002 | P2 | Frontend Health | Sidebar pinta `configured` como danger en vez de warn | `Sidebar.tsx` solo trata ok/degraded/no-auth | Diagnostico visual inconsistente | Corregido: clase warning + Playwright |
| GAP-003 | P2 | Playwright | No existe suite comercial hermetica con mocks para todos los views | 9 specs actuales, muchas live-stack | Falso rojo/falso verde por entorno | Corregido: specs comerciales con API mocks; full-e2e 31 passed |
| GAP-004 | P2 | Docs | Algunos docs secundarios mantienen texto pre-zero-friction | USER_GUIDE/ACTION_PLANE | Futuros agentes reintroducen friccion | Corregido: docs principales y QA actualizados al snapshot 944/31 + live/TestSprite + MCP 5/5 |
| GAP-005 | P2 | Action Plane | Falta matriz E2E visible de jobs/approvals/action lifecycle | Tests backend parciales | UI puede quedar muda ante estados queued/running/failed | Corregido: Playwright lifecycle con approval/dispatch/job event |
| GAP-006 | P2 | TestSprite | TestSprite no tenia config/plan usable al inicio | Bootstrap timeout y CLI sin plan; luego PRD/plan generados | Sin crawling externo funcional si el MCP queda colgado | Mitigado: TestSprite ejecutado 3/3 passed como smoke advisory; Playwright 31/31 sigue como gate fuerte |
