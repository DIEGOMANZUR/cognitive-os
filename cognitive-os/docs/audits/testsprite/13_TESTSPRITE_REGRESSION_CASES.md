# 13 - TestSprite Regression Cases

Fecha UTC: 2026-05-24

Estos casos quedan definidos para TestSprite MCP como regresiones obligatorias
post-reparacion. No agregan otro framework de QA.

## REG-TS-001 - Public bootstrap no usa localhost

- Hallazgo cubierto: TS-001.
- Suite: UI / E2E.
- Tipo: regression case.
- Precondicion:
  - Navegador limpio o sin garantia de que TestSprite haya sembrado
    `localStorage` antes del primer render.
- Pasos:
  1. Abrir `https://cognitive.doctormanzur.com`.
  2. Si TestSprite puede ejecutar pre-step, sembrar:
     `localStorage.setItem('cogos.api', 'https://cognitive-api.doctormanzur.com')`.
  3. Observar network antes y despues de reload.
- Expected:
  - No hay requests a `localhost:8000` ni `127.0.0.1:8000`.
  - El TopBar muestra API publica.
  - La UI obtiene JWT automatico o usa el JWT sembrado.
  - Si falla auth, el error menciona timeout/API/JWT y no falso verde.

## REG-TS-002 - Health live terminal state

- Hallazgo cubierto: TS-001.
- Suite: UI / E2E.
- Tipo: regression case.
- Pasos:
  1. Abrir UI publica con API publica.
  2. Navegar a Health por sidebar/hotkey, no por ruta `/health`.
  3. Pulsar `Verificar en vivo`.
- Expected:
  - El boton muestra progreso mientras corre.
  - El flujo termina con componentes actualizados o error accionable.
  - No queda `Verificando...` indefinidamente.
  - No aparece `Sin lecturas todavia` junto con falso exito.

## REG-TS-003 - MCP status visible en degradacion

- Hallazgo cubierto: TS-004.
- Suite: UI.
- Tipo: regression case.
- Pasos:
  1. Abrir UI publica.
  2. Ir a `Conexión` / `Sistema` por sidebar o Ctrl+K.
  3. Inspeccionar la seccion `MCP servers`.
- Expected:
  - La seccion `MCP servers` existe siempre.
  - Muestra conteo conectado, disabled, loading, sin datos o error de
    `/system/mcp`.
  - No reporta OK sin inventario real.

## REG-TS-004 - API auth runner no lee `/tmp`

- Hallazgo cubierto: TS-002.
- Suite: API.
- Tipo: regression case de instrumentacion TestSprite.
- Pasos:
  1. Configurar `Authorization: Bearer <JWT>` dentro del contexto TestSprite.
  2. Ejecutar `GET /health/dashboard`, `GET /system/info` y auth negative.
- Expected:
  - El caso no lee `/tmp/cognitive_os_testsprite_jwt.txt` desde `/var/task`.
  - El valor JWT completo no se imprime en reportes.
  - Cualquier fallo reportado corresponde a respuesta real del backend.

## REG-TS-005 - Mail read-only permanece bloqueado

- Hallazgo cubierto: TS-005.
- Suite: UI / E2E / API critical.
- Tipo: safety regression.
- Pasos:
  1. Abrir Mail.
  2. Buscar botones o endpoints de send/draft/approve-send normal.
  3. Intentar solo validaciones dry-run/bloqueadas permitidas por TestSprite.
- Expected:
  - No hay send normal ni draft normal.
  - Cualquier endpoint peligroso queda bloqueado con 4xx esperado o disabled.
  - La UI presenta propuestas como texto cuando existan datos, sin ejecutar mail
    write.
