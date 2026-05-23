# 08 · Fix Log — TestSprite Audit 2026-05-23

## Fix 1 · TS-ZF-20260523-001 (P2) — Auto-mint JWT en Playwright runner

**Archivos modificados:**

- `frontend/tests/e2e/_global-setup.ts` (nuevo)
- `frontend/playwright.config.ts`
- `frontend/tests/e2e/_helpers.ts`

**Cambios:**

1. **`_global-setup.ts` (nuevo).** `globalSetup` que corre una vez antes
   de cualquier worker. Si `COGOS_JWT` no está exportado, hace
   `POST ${COGOS_API_BASE:-http://127.0.0.1:8000}/auth/local-token` y
   exporta el token a `process.env.COGOS_JWT` para que los workers lo
   hereden. Falla silenciosa si el endpoint 403 (perfil strict) o si el
   backend no responde — los specs entonces emiten el mensaje claro de
   `readJwt()`.
2. **`playwright.config.ts`.** Añadido
   `globalSetup: require.resolve("./tests/e2e/_global-setup")`. Comentario
   actualizado describiendo la estrategia de token (auto-mint en
   `dedicated_local/full`, manual en `strict`).
3. **`_helpers.ts::readJwt()`.** Mensaje de error refrescado para apuntar
   tanto al RUNBOOK §2 (mintea manual) como al global setup
   (`POST /auth/local-token`).

**Validación:**

```bash
cd cognitive-os/frontend
unset COGOS_JWT
COGOS_API_BASE=http://127.0.0.1:8000 COGOS_BASE_URL=http://localhost:3001 \
  npx playwright test --reporter=list
```

**Resultado:**

```
[playwright global-setup] auto-minted COGOS_JWT via
  http://127.0.0.1:8000/auth/local-token (dedicated_local/full)
Running 31 tests using 1 worker
...
  31 passed (36.0s)
```

✅ **Cero fricción restaurada para Playwright.**

Log: `test-results/baseline/playwright-fix2.log`

## Fix 2 · TS-ZF-20260523-004 (P3) — Docs RUNBOOK §2/§3

**Archivos modificados:**

- `docs/qa/RUNBOOK.md` §2 y §3

**Cambios:**

- §2 "Mintar un JWT" ahora documenta como **forma corta**:
  ```bash
  JWT=$(curl -sX POST http://127.0.0.1:8000/auth/local-token | \
    python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
  ```
  El método `uv run python -c` queda como **forma larga** para perfiles
  `strict`/`guarded`.
- §3 "Verificación rápida" reemplaza el `JWT=$(uv run python -c ...)` con
  el `curl POST /auth/local-token` equivalente.
- §2 menciona explícitamente que `tests/e2e/_global-setup.ts` mintea el
  JWT automáticamente para Playwright.

**Validación:** documento; no aplica test.

✅ Documentación alineada con el contrato de cero fricción.

## Fix 3 · TS-ZF-20260523-002 (P3) — Runtime restart para matchear HEAD

**Acción:** `~/Escritorio/cognitive-os.sh restart` ejecutado durante el
audit (necesario también para liberar la API después de que TestSprite
saturara el accept-queue con miles de conexiones CLOSE-WAIT/FIN-WAIT-2).

**Resultado:**

```
$ curl POST /auth/local-token → JWT minted
$ curl /system/info ⇒ git_commit: 9b22f771edf3   ← antes era 2c3cff6
                     alembic_head: 202605200003
                     operator_profile: dedicated_local
```

✅ Runtime ahora corre HEAD (`9b22f77`). MCP parallel inventory +
`MCP_INVENTORY_TIMEOUT_SECONDS=30` default + capture-phase `Ctrl/K` cargados.

## Fix 4 · TS-ZF-20260523-003 (P3) — Doc drift histórico

**Decisión:** **no aplicar**.

Razón: los párrafos históricos en `docs/qa/MAP.md` y
`docs/qa/FINAL_AUDIT_REPORT.md` están ya marcados con disclaimer y
encabezado "Fase 76 (auditoría E2E full-stack histórica)". Añadir
marcadores inline sería bloat sin valor incremental. El snapshot vigente
manda y está clara la separación.

## Fixes NO aplicados (por contrato)

- Mail send no se afloja.
- Telegram fail-closed no se afloja.
- `MAIL_GODADDY_PASSWORD` plaintext: decisión documentada del operador.
- `KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true`: contrato vigente.
- `GODADDY_DNS_DRY_RUN_ONLY=true`: contrato vigente.
- Auto-resolución de approvals en `dedicated_local/full`: contrato vigente.

## TestSprite MCP

**Estado:** se intentó ejecutar la suite completa de 28 TC (frontend).
La ejecución generó >4000 conexiones a `127.0.0.1:8000` y saturó el
accept-queue de uvicorn (CLOSE-WAIT + FIN-WAIT-2 acumulados), llevando la
API a un estado no responsivo. Tras 15 minutos sin completar (ningún
`raw_report.md` producido), se aborto el proceso y se reinició el stack
para validar los fixes con Playwright (el gate fuerte).

**Conclusión consistente con `CURRENT_STATE.md`:** "TestSprite no
sustituye Playwright porque los asserts generados son más superficiales".
Para esta auditoría, **Playwright 31/31 sin friction** es el verde de
referencia.

Detalle en `09_FINAL_REMEDIATION_REPORT.md`.
