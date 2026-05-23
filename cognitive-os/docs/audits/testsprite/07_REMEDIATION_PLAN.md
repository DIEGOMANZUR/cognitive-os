# 07 · Remediation Plan — TestSprite Audit 2026-05-23

Orden de ejecución por severidad y por impacto en cero fricción.

## 1. P2 — TS-ZF-20260523-001: Auto-mint JWT en Playwright runner

**Archivos:**
- `frontend/tests/e2e/_helpers.ts`
- `frontend/tests/e2e/auth.spec.ts` (test de regresión)
- `docs/qa/RUNBOOK.md §2` (documentación)

**Root cause:** `readJwt()` lanza error si `COGOS_JWT` no está exportado.
Históricamente el mint requería Python; ahora `POST /auth/local-token` es
trivial vía HTTP en `dedicated_local/full`.

**Solución:** convertir `readJwt()` en `async function ensureJwt(): Promise<string>` que:
1. Si `COGOS_JWT` existe → usarlo.
2. Si no, hacer `POST ${COGOS_API_BASE}/auth/local-token` y devolver
   `access_token`.
3. Si el endpoint retorna 403 (perfil != dedicated_local), entonces sí
   lanzar con mensaje claro: "Set COGOS_JWT manually for strict profile".

**Test:**
- `auth.spec.ts` con env limpia + `dedicated_local/full` → debe pasar sin
  exportar JWT.
- Test que mockee 403 y verifique el mensaje claro.

**Comando de validación:**
```bash
cd cognitive-os/frontend
unset COGOS_JWT
COGOS_API_BASE=http://127.0.0.1:8000 COGOS_BASE_URL=http://localhost:3001 \
  npx playwright test --reporter=list
# Esperado: 31 passed
```

**Riesgo:** bajo — el endpoint ya existe y está cubierto por pytest.

**Rollback:** revertir `_helpers.ts` y volver al modelo "COGOS_JWT required".

## 2. P3 — TS-ZF-20260523-004: Documentar mint vía /auth/local-token

**Archivos:**
- `docs/qa/RUNBOOK.md §2`

**Solución:** añadir como método primario el `curl POST
/auth/local-token` con `python3 -c`; dejar el método `uv run python -c
"from cognitive_os.core.auth ..."` como fallback para `strict`.

**Test:** ninguno (es documentación).

**Comando de validación:**
```bash
JWT=$(curl -sX POST http://127.0.0.1:8000/auth/local-token | \
      python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
curl -sI -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/system/info | head -1
# Esperado: HTTP/1.1 200 OK
```

## 3. P3 — TS-ZF-20260523-002: Reiniciar runtime para matchear HEAD

**Acción:** apagar `uvicorn` y `next-server` actuales y volverlos a
arrancar. Esto cargará el código de `HEAD = 9b22f77` con:

- `MCP_INVENTORY_TIMEOUT_SECONDS=30` por default.
- `mcp_client.py` con inventario paralelo en código (en RAM cuando se
  reinicie).
- `hooks.ts` con `useKeyboard` capture phase (ya en el build).

**No requiere reset Docker / Postgres / Redis.**

**Riesgo:** medio — interrumpe el panel del operador. Coordinaré la
ventana o lo dejaré como recomendación post-audit.

**Decisión tomada en este audit:** NO reiniciar dentro de la auditoría
automatizada. Dejarlo documentado como acción que el operador puede
ejecutar con `~/Escritorio/Reiniciar Cognitive OS.sh` o
`/home/jgonz/Escritorio/cognitive-os.sh restart`. Documentar en el
`09_FINAL_REMEDIATION_REPORT.md`.

## 4. P3 — TS-ZF-20260523-003: Doc drift histórico

**Acción:** marcar los párrafos históricos en `docs/qa/MAP.md` y
`docs/qa/FINAL_AUDIT_REPORT.md` con `<!-- HIST -->` o nota en bloque
`> *Histórico Fase 76. El snapshot vigente al inicio de este archivo
> manda.*` para que no haya confusión cuando alguien busca números.

**Riesgo:** ninguno (documental).

## 5. Acciones de cierre

- Rerun Playwright sin COGOS_JWT exportado → verificar el fix.
- Rerun full-qa.sh.
- TestSprite final pass para confirmar.
- Actualizar `09_FINAL_REMEDIATION_REPORT.md`.

## Lo que NO se va a tocar (por contrato)

- Mail: no se afloja read-only / no-draft / no-send.
- Telegram: se mantiene fail-closed.
- Auto-resolución de approvals en `dedicated_local/full`: se mantiene como
  está.
- `MAIL_GODADDY_PASSWORD` en `.env`: decisión del operador.
- `KIMI_WEBBRIDGE_REQUIRE_APPROVAL=true`: se mantiene.
- `GODADDY_DNS_DRY_RUN_ONLY=true`: se mantiene.

## Orden de ejecución (sin esperar confirmación)

1. P2 — Auto-mint JWT en `_helpers.ts` + test de regresión.
2. P3 — RUNBOOK update con `/auth/local-token`.
3. P3 — Doc drift histórico (notas).
4. (Opcional) reiniciar runtime — solo si el operador lo aprueba en sesión
   interactiva; documentado como acción recomendada.
5. Rerun gates (full-qa + Playwright sin JWT exportado).
6. TestSprite final.
