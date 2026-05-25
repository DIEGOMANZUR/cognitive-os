# 03 - TestSprite Auth Setup

Fecha UTC: 2026-05-24T08:25:01Z

## Modelo de autenticacion

`PRD_FRONTEND.md` y `PRD_BACKEND.md` definen que Cognitive OS no usa login
clasico. La UI y API se autentican con JWT local de operador.

## JWT temporal

Se genero un JWT temporal admin para auditoria TestSprite con el metodo
documentado del repo:

```bash
cd cognitive-os/backend
uv run python -c "from cognitive_os.core.auth import create_access_token; print(create_access_token(user_id='testsprite-auditor', roles=['admin']))"
```

Guardado local:

- `/tmp/cognitive_os_testsprite_jwt.txt`
- permisos `0600`
- mask para reportes: `eyJhbGciOiJI...188`

El valor completo no debe escribirse en Markdown, logs versionados ni reportes
TestSprite sanitizados.

## Auth UI para TestSprite

Pre-step requerido antes de navegar o antes de recargar:

```js
localStorage.setItem('cogos.token', '<JWT>');
localStorage.setItem('cogos.api', 'https://cognitive-api.doctormanzur.com');
```

Despues:

1. Navegar a `https://cognitive.doctormanzur.com`.
2. Recargar si la TopBar aun no refleja estado conectado.
3. Confirmar que la UI no llama a `localhost` ni `127.0.0.1`.

## Auth API para TestSprite

Header requerido para endpoints protegidos:

```http
Authorization: Bearer <JWT>
```

Casos negativos esperados y no-bug:

- sin token -> 401;
- token invalido -> 401;
- token expirado -> 401;
- rol insuficiente -> 403.

## Restricciones de reporte

Si TestSprite exporta request headers, debe enmascarar:

```text
Authorization: Bearer eyJhbGciOiJI...<redacted>
```

No se debe copiar el JWT completo a:

- `docs/audits/testsprite/*.md`;
- `test-results/testsprite/initial-full-audit/`;
- reportes HTML/Markdown exportados;
- logs persistidos.

## Limitacion observada de TestSprite

La ejecucion UI inicial y el re-run selectivo mostraron que el generador de
TestSprite no aplico de forma consistente el pre-step de `localStorage` pedido:
en varios scripts navego primero a la UI y dependio del auto-token visible de la
app. La ejecucion API se ejecuto en sandbox `/var/task` y no pudo leer
`/tmp/cognitive_os_testsprite_jwt.txt`; al pasar el JWT como variable de entorno
al runner local tampoco quedo disponible dentro del sandbox remoto.

Por eso los fallos `JWT file not found`, `Failed to fetch` y backend no
respondio se clasifican separando:

- limitacion de TestSprite/auth injection cuando el script no llega a sembrar
  JWT;
- posible bug real si la UI publica debe auto-mintar token en
  `dedicated_local/full` y no puede hacerlo contra el backend publico.
