# 04 - TestSprite MCP Status

Fecha UTC: 2026-05-24T08:25:01Z

## Herramientas TestSprite MCP reales disponibles

Se inspeccionaron las herramientas expuestas en el namespace
`mcp__testsprite_agent__`. Herramientas reales:

- `testsprite_check_account_info`
- `testsprite_generate_frontend_test_plan`
- `testsprite_generate_backend_test_plan`
- `testsprite_generate_code_and_execute`
- `testsprite_open_test_result_dashboard`

No se observaron herramientas separadas para:

- crear proyecto con nombre explicito;
- cargar PRD por path como parametro;
- cargar OpenAPI por URL como parametro;
- configurar frontend URL por parametro;
- configurar backend URL por parametro;
- configurar auth por parametro;
- editar plan por ID;
- listar failures como llamada estructurada;
- exportar screenshots/traces por llamada estructurada.

Esas capacidades pueden existir dentro del runner/dashboard TestSprite, pero no
estan expuestas como tools MCP independientes en esta sesion.

## Cuenta TestSprite

`testsprite_check_account_info` respondio correctamente:

- cuenta: disponible;
- plan: Starter;
- creditos al inicio de esta fase: 540.

El email de la cuenta no se repite aqui para minimizar exposicion de datos.

## Generacion de plan frontend

Tool usado:

- `testsprite_generate_frontend_test_plan`

Resultado:

- OK.
- Plan generado: `testsprite_tests/testsprite_frontend_test_plan.json`
- Casos generados: 27.

Observacion: el plan generado cubre varias areas importantes, pero no basta por
si solo para todo el alcance PRD; se amplia mediante instrucciones estrictas de
ejecucion y planes Markdown 05/07.

## Generacion de plan backend

Primer intento:

- `testsprite_generate_backend_test_plan(projectPath=...)`
- Resultado: fallo con mensaje exacto:

```text
Failed to generate backend test plan: This tool only supports backend tests. Please set testType to "backend".
```

La tool MCP expuesta no acepta parametro `testType`. Reparacion razonable:

- se ajusto el artefacto runtime ignorado `testsprite_tests/tmp/config.json`
  de `type=frontend` a `type=backend`;
- se reintento la misma tool.

Segundo intento:

- OK.
- Plan generado: `testsprite_tests/testsprite_backend_test_plan.json`
- Casos generados: 1.

Limitacion: 1 caso no cubre `PRD_BACKEND.md`; se documenta como gap TestSprite
MCP de planificacion y se compensa con instrucciones de ejecucion API desde PRD.

## Ejecucion TestSprite

Tool disponible para ejecutar:

- `testsprite_generate_code_and_execute`

Caracteristica observada: devuelve un `next_action` con comando local
`generateCodeAndExecute`; el comando debe ejecutarse en terminal para completar
la corrida. El runner directo puede dejar artefactos temporales que deben
sanitizarse despues.

## Riesgos MCP

- TestSprite es cloud/external y recibe contexto de pruebas.
- Puede automatizar browser y API contra URLs publicas.
- Puede consumir creditos.
- Puede generar artefactos con headers/config si no se sanitizan.

Mitigaciones aplicadas:

- JWT en `/tmp` con permisos `0600`;
- reportes sin JWT completo;
- prohibicion explicita de mail send/draft, DNS write y destructive actions;
- ejecuciones limitadas por timeout;
- sanitizacion de artefactos locales al cierre.

## Hallazgos MCP durante ejecucion

- El runner sobrescribe `testsprite_tests/tmp/test_results.json` y
  `testsprite_tests/tmp/raw_report.md` en cada corrida; los artifacts deben
  copiarse inmediatamente despues de cada suite.
- El plan backend MCP genero solo 1 caso, pese a que `PRD_BACKEND.md` exige
  cobertura amplia de endpoints y journeys J1-J10.
- La ejecucion backend se realizo en sandbox remoto `/var/task`; ese entorno no
  pudo leer `/tmp/cognitive_os_testsprite_jwt.txt`.
- La variable `COGNITIVE_OS_TESTSPRITE_JWT` pasada al proceso local del runner no
  llego al sandbox remoto en la prueba backend.
- Algunos reportes raw generados por TestSprite quedaron con placeholders
  (`{{TODO:AI_ANALYSIS}}`); por eso el reporte canonico de esta auditoria es
  `09_TESTSPRITE_INITIAL_RESULTS.md`, no el `raw_report.md` sin completar.
- El archivo runtime `testsprite_tests/tmp/config.json` puede contener API key
  del MCP; se sanitizo localmente despues de las ejecuciones y no se copia como
  artifact final.
