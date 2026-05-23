# 05 Zero Friction Repair Plan

## P0

No hay P0 abierto confirmado al inicio de esta intervencion. Los P0 historicos
Telegram fail-closed, mail read-only y DB test aislada ya tienen tests.

## P1 Corregidos

### ZF-P1-001 - Full QA puede dar verde falso si Alembic falla

- Evidencia: `scripts/full-qa.sh` convierte fallo de `alembic check` en `WARN`.
- Causa probable: tolerancia historica a Postgres apagado.
- Test que debe fallar: static test que prohibe `WARN: alembic check` y exige `exit 1`.
- Reparacion: `alembic check` hard-fail cuando existe `.env`, `.env.local` o `DATABASE_URL`;
  skip solo si no hay configuracion DB.
- Archivos: `scripts/full-qa.sh`, `scripts/README.md`, `backend/tests/test_frontend_static_assets.py`.
- Validacion: `bash scripts/full-qa.sh`.

### ZF-P1-002 - Gate E2E mata el frontend vivo con `npm ci`

- Evidencia: `full-e2e.sh` hacia `npm ci` tras verificar server vivo; Next dev perdia `node_modules`.
- Reparacion: `npm ci` opt-in (`COGOS_E2E_NPM_CI=1`), preflight CORS y verificacion de server despues de deps.
- Validacion: `bash scripts/full-e2e.sh` -> 31 passed.

## P2 Corregidos / Documentados

### ZF-P2-001 - Health configured se pinta mal en Sidebar

- Evidencia: `Sidebar.tsx` manda todo lo distinto de ok/degraded/no-auth a danger.
- Reparacion: mapear `configured` a warn.
- Test: Playwright `health-verified-vs-configured.spec.ts` con API mock.
- Validacion: `bash scripts/full-e2e.sh`.

### ZF-P2-002 - Playwright comercial insuficiente por flujos especificos

- Evidencia: specs actuales no cubren con nombre/alcance jobs approvals action lifecycle,
  zero-friction dedicated local, mobile PWA y malformed JSON generalizado.
- Reparacion: agregar specs comerciales con mocks hermeticos y console guard.
- Validacion: `bash scripts/full-e2e.sh` o specs focales.

### ZF-P2-003 - CORS local fallback demasiado estrecho

- Evidencia: frontend `:3101` contra API local generaba CORS errors masivos.
- Reparacion: defaults CORS incluyen `localhost/127.0.0.1:3101`; `full-e2e` diagnostica preflight antes de Playwright.
- Validacion: `test_config.py` y `full-e2e` con API temporal `:8001`.

### ZF-P2-004 - Docs secundarios pueden reintroducir friccion

- Evidencia: `USER_GUIDE.md` y `ACTION_PLANE.md` conservan frases antiguas.
- Reparacion: docs vigentes actualizados al snapshot `944/31`, MCP 5/5 y
  67 tools; frases historicas quedan en audit docs como historico.

## P3

- Crear `scripts/full-e2e.sh` como gate Playwright separado.
- Documentar TestSprite disponible/no disponible y su ejecucion. Estado:
  ejecutado con subconjunto critico 3/3 passed como smoke advisory; fallback
  fuerte y gate principal sigue siendo Playwright 31/31.
