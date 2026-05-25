# 05 - TestSprite UI Plan

Fecha UTC: 2026-05-24T08:25:01Z
Suite: Cognitive OS - TestSprite UI Full Audit - dedicated_local full

## Fuente

Fuente principal:

- `/home/jgonz/Escritorio/testsprite/PRD_FRONTEND.md`

Plan MCP generado:

- `testsprite_tests/testsprite_frontend_test_plan.json`
- Casos: 27

## URL y auth

- URL frontend: `https://cognitive.doctormanzur.com`
- API esperada: `https://cognitive-api.doctormanzur.com`

Pre-step obligatorio:

```js
localStorage.setItem('cogos.token', '<JWT>');
localStorage.setItem('cogos.api', 'https://cognitive-api.doctormanzur.com');
```

Luego cargar o recargar `/`.

## Disciplina SPA

TestSprite no debe navegar a rutas de tab como paths:

- `/dashboard`
- `/health`
- `/mail`
- `/chat`
- `/documents`
- `/settings`
- `/jobs`
- `/approvals`

Esos 404 son esperados por PRD. La navegacion valida es:

- sidebar;
- hotkeys;
- `Ctrl/Cmd+K`.

## Tabs obligatorias

TestSprite debe cubrir:

- Dashboard
- Chat
- DeepAgents
- Skills
- Memoria
- Asistente
- Mail
- Documentos
- Document Analysis
- Jobs
- Aprobaciones
- Google Ops
- Research
- Code Director
- Sandbox
- LangSmith
- Audit log
- Health
- Sistema
- Conexion

Para cada tab:

- carga;
- no crash;
- estado terminal en menos de 10 s;
- loading/empty/error correcto;
- no console errors criticos;
- no CORS;
- no mixed content;
- no requests a localhost/127.0.0.1;
- botones criticos tienen efecto o explican disabled/degraded;
- formularios validan;
- no falso exito.

## Journeys UI

J1 Bootstrap:

- abrir `/`;
- seed localStorage;
- reload;
- TopBar conectado;
- API base publica persistida.

J2 Health:

- hotkey `9` o sidebar Health;
- cards render;
- health honesto;
- `configured` no se trata como verified `ok`.

J3 Dashboard:

- hotkey `1`;
- KPIs render;
- sin spinner infinito.

J4 Chat:

- hotkey `2`;
- enviar mensaje corto;
- respuesta o error controlado;
- no 5xx silencioso.

J5 Documents:

- hotkey `3`;
- lista o empty state;
- primer documento si existe.

J6 Command Palette:

- `Ctrl/Cmd+K`;
- buscar tab;
- navegar sin cambiar URL.

J7 Settings persistence:

- Sistema/Conexion;
- confirmar `cogos.api` publico;
- no reintroducir tema claro como requisito.

J8 Audit:

- hotkey `8`;
- tabla o empty state correcto.

J9 Approvals:

- hotkey `6`;
- lista o empty state correcto;
- no aprobar envios mail.

J10 Notifications:

- bell icon si existe;
- panel abre o ausencia queda clara.

## Casos MCP generados

El plan MCP genero 27 casos, incluyendo mail read-only, persistencia de tabs,
health, configuracion, approvals, digest preview, MCP status, jobs, documents y
audit malformed handling.

Gap frente al PRD:

- no todos los tabs aparecen explicitamente por nombre en el plan generado;
- no hay assertion explicita de no-localhost por cada journey;
- no hay assertion explicita de mixed-content/CORS por cada journey;
- chat/document-analysis/research/code-director quedan subrepresentados;
- responsive/mobile queda subrepresentado.

Estos gaps se agregan como instrucciones obligatorias en la ejecucion E2E.

## Prohibiciones UI

No ejecutar:

- mail send;
- mail draft;
- aprobar envio outbound;
- DNS write real;
- browser automation externa;
- destructive filesystem;
- togglear safety flags;
- rotar JWT/admin.
