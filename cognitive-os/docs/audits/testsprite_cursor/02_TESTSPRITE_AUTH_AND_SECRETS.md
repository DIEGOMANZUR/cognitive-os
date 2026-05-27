# 02 — TestSprite Auth and Secrets

> **Actualización 2026-05-26:** este archivo es evidencia histórica de auditoría. El flujo vigente ya no usa TopBar: la autenticación pública es por `#cogos_token` o `localStorage.cogos.token`, la API se resuelve automáticamente por host y el shell estable se valida con `<main data-cogos-active-tab="...">`. Las menciones a TopBar debajo se conservan solo como contexto histórico.

Fecha: **2026-05-26**  
Alcance: preparación auth — **sin imprimir secretos completos**

## Modelo de auth (contrato producto)

| Superficie | Mecanismo |
|---|---|
| Frontend público | `localStorage.cogos.token` (JWT sin prefijo Bearer) + `localStorage.cogos.api` |
| API pública | Header `Authorization: Bearer <JWT>` |
| Sin seed | 401 / estados vacíos → **esperado**, no bug |

## JWT preparado

| Item | Valor |
|---|---|
| Archivo | `/tmp/cognitive_os_testsprite_cursor_jwt.txt` |
| Permisos | `600` |
| Subject | `testsprite-cursor-auditor` |
| Roles | `admin` |
| Longitud | 197 chars |
| Máscara ejemplo | `eyJhbGciOiJI...kraqHFN8` |

Generación (ejecutada en prep, no es test suite):

```bash
cd backend
uv run python -c "from cognitive_os.core.auth import create_access_token; print(create_access_token(user_id='testsprite-cursor-auditor', roles=['admin']))" \
  > /tmp/cognitive_os_testsprite_cursor_jwt.txt
chmod 600 /tmp/cognitive_os_testsprite_cursor_jwt.txt
```

## Pre-step UI para TestSprite (pegar en additionalInstruction)

```javascript
// Before any navigation on https://cognitive.doctormanzur.com/
localStorage.setItem('cogos.token', '<JWT_FROM_FILE>');
localStorage.setItem('cogos.api', 'https://cognitive-api.doctormanzur.com');
location.reload();
```

Alternativa documentada: campo **"JWT local"** en TopBar + guardar.

## Pre-step API para TestSprite

```http
Authorization: Bearer <JWT_FROM_FILE>
```

Para negative tests usar tokens claramente inválidos (`invalid.jwt.token`) — **nunca** el JWT real.

## Errores esperados (no marcar como bug)

| Condición | Respuesta esperada |
|---|---|
| Sin token | **401** `Not authenticated` |
| Token inválido | **401** invalid signature |
| Token expirado | **401** `JWT has expired` |
| Rol insuficiente | **403** `forbidden_role` |

## Enmascarado en reportes

Reglas para Megaprompt 2:

- No pegar JWT completo en markdown versionado.
- En logs: mostrar solo primeros 12 + últimos 8 chars.
- No pegar `TESTSPRITE_API_KEY` en docs (vive en `.env` gitignored).
- TestSprite video URLs: omitir o redactar en exports públicos.

## TestSprite API key (cloud)

| Item | Ubicación |
|---|---|
| Variable | `TESTSPRITE_API_KEY` en `cognitive-os/.env` (gitignored) |
| Uso | Runner MCP cloud / `full-testsprite.sh` |
| Reportes | Referir como "presente en .env local" — no valor |

## Verificación realizada (availability only)

- Bearer JWT → `GET https://cognitive-api.doctormanzur.com/system/info` = **200**
- Sin auth → **401**

**Estado:** JWT preparado y usable para suites B/C/D.
