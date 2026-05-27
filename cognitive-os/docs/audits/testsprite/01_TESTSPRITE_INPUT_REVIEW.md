# 01 — TestSprite Input Review

> **Actualización 2026-05-26:** este archivo es evidencia histórica de auditoría. El flujo vigente ya no usa TopBar: la autenticación pública es por `#cogos_token` o `localStorage.cogos.token`, la API se resuelve automáticamente por host y el shell estable se valida con `<main data-cogos-active-tab="...">`. Las menciones a TopBar debajo se conservan solo como contexto histórico.

Fecha: 2026-05-24
Auditoría: Cognitive OS — TestSprite initial full audit
Fuente principal leída completa: `/home/jgonz/Escritorio/testsprite/`

Archivos fuente usados:

- `/home/jgonz/Escritorio/testsprite/PRD.md`
- `/home/jgonz/Escritorio/testsprite/PRD_FRONTEND.md`
- `/home/jgonz/Escritorio/testsprite/PRD_BACKEND.md`
- `/home/jgonz/Escritorio/testsprite/cognitive-os-launchers-README.md`

Contexto secundario leído del repo:

- `docs/CURRENT_STATE.md`
- `docs/ZERO_FRICTION_OPERATING_MODEL.md`
- `docs/ACTION_PLANE.md`
- `docs/RUNBOOK.md`
- `docs/USER_GUIDE.md`
- `docs/ARCHITECTURE.md`

## Exigencias de `PRD.md`

Cognitive OS debe auditarse como un sistema local-first, mono-operador, para PC dedicado, optimizado para cero fricción operativa y funcionamiento perfecto bajo:

- `OPERATOR_PROFILE=dedicated_local`
- `LOCAL_AUTONOMY_MODE=full`
- `CODE_DIRECTOR_BUDGET_MODE=soft`

La auditoría TestSprite debe validar cero fricción sin debilitar controles no negociables:

- health honesto;
- readiness accionable;
- trazabilidad mediante `AuditEvent`;
- coherencia de `JobEvent`;
- `ActionRequest` idempotente;
- no falsos verdes;
- no errores silenciosos;
- no secretos expuestos;
- no duplicación de acciones peligrosas;
- no side effects reales durante tests;
- mail read-only en flujo normal.

Áreas críticas a cubrir:

- frontend completo: Dashboard, Health, Chat, Threads, Jobs, Job detail/events, Approvals, Action Plane, Documents, Document Analysis, Research, DeepAgents, Memory, Skills, Mail, Google Ops, Code Director, MCP/System, Audit, Settings/Configuration;
- backend: `/system/*`, `/health/*`, `/jobs/*`, `/approvals`, `/actions/*`, `/mail/*`, `/documents/*`, `/document-analysis/*`, `/research/*`, `/deepagents/*`, `/code-director/*`, `/audit/events`, `/threads/*`, `/chat`;
- health/readiness, jobs/workers, approvals, Action Plane, documents, document analysis, research, DeepAgents/memory/skills, Code Director, Telegram si es testable, MCP y negative tests.

## Exigencias de `PRD_FRONTEND.md`

La UI pública bajo `https://cognitive.doctormanzur.com` es una SPA. Sólo existen server-side:

- `/`
- `/manifest.webmanifest`
- `/_next/*`
- `/icons/*`

No son bugs:

- `/dashboard` 404;
- `/health` 404;
- `/mail` 404;
- `/chat` 404;
- cualquier vista navegada como path directo fuera de `/`.

La navegación válida es por:

- sidebar;
- hotkeys `1` a `9`;
- command palette `Ctrl/Cmd+K`.

Autenticación UI:

```js
localStorage.setItem('cogos.token', '<JWT>');
localStorage.setItem('cogos.api', 'https://cognitive-api.doctormanzur.com');
```

Luego se debe cargar o recargar `https://cognitive.doctormanzur.com` y esperar TopBar `Connected`.

Tabs obligatorios:

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
- Conexión

Criterios UI:

- cada tab carga y alcanza estado terminal en menos de 10 s;
- no hay crashes ni excepciones JS no manejadas;
- no hay errores críticos de consola;
- no hay hydration/chunk failures;
- no hay CORS ni mixed content;
- no hay fetch a `localhost:*` ni `127.0.0.1:*` desde origen público;
- botones críticos tienen efecto verificable;
- formularios validan;
- estados loading/empty/error son claros y accionables;
- no hay éxito falso.

## Exigencias de `PRD_BACKEND.md`

Backend público bajo `https://cognitive-api.doctormanzur.com`.

Públicos sin auth:

- `GET /health` → 200 con `status=ok`, `service=cognitive-os`;
- `GET /openapi.json`;
- `GET /docs`;
- `GET /redoc`.

Todo lo demás requiere:

```http
Authorization: Bearer <JWT>
```

Claims esperados:

- `sub` string;
- `roles` incluye `admin`;
- `exp` unix epoch.

Auth negative esperado:

- sin token → 401 `Not authenticated`;
- token inválido → 401;
- token expirado → 401 `JWT has expired`;
- rol insuficiente → 403 `forbidden_role`.

Namespaces a cubrir:

- `/actions`
- `/deepagents`
- `/mail`
- `/document-analysis`
- `/assist`
- `/system`
- `/jobs`
- `/langsmith`
- `/research`
- `/code-director`
- `/health`
- `/threads`
- `/documents`
- `/approvals`
- `/voice`
- `/chat`
- `/sandbox`
- `/auth`
- `/audit`
- `/knowledge`
- `/config`
- `/agents`

Backbone API J1-J10:

1. liveness `GET /health` sin auth;
2. readiness + system info;
3. catalog discovery;
4. chat round trip;
5. document index;
6. approvals + audit;
7. jobs introspection;
8. DeepAgents catalog;
9. auth negative;
10. CORS preflight desde `https://cognitive.doctormanzur.com`.

## Restricciones de seguridad funcional activas

Durante esta auditoría no se debe ejecutar ningún side effect externo real. Flags y contratos relevantes según PRD:

- `ENABLE_EMAIL_SEND=false`;
- `MAIL_ALLOW_EXPLICIT_SEND=false`;
- `GODADDY_DNS_DRY_RUN_ONLY=true`;
- `GODADDY_ALLOW_PRODUCTION_WRITES=false`;
- `TOOLS_READONLY_MODE=true`;
- `ENABLE_BROWSER_AUTOMATION=false` para flows externos no aprobados;
- `ALLOW_DANGEROUS_TOOLS=false`.

Mail es excepción dura: sólo lectura, clasificación, resumen, propuesta de texto y copia manual por el operador.

## Qué NO debe ejecutar TestSprite

TestSprite no debe:

- enviar correos;
- crear drafts;
- aprobar envíos outbound;
- llamar `POST /mail/messages/{id}/approve-send` con condiciones de escape hatch reales;
- llamar `POST /mail/messages/{id}/send` si existiera;
- ejecutar DNS write real;
- ejecutar `POST /actions/dispatch` contra DNS o write peligroso;
- ejecutar sandbox destructivo;
- borrar archivos;
- rotar JWT secret;
- modificar admin users;
- togglear safety flags;
- conducir browser automation contra sitios externos con sesión real;
- usar tests que escriban en producción.

Sí puede verificar que los guards bloqueen esos flujos con 400/403/409 y sin 5xx.

## Qué debe probar TestSprite sí o sí

Frontend:

- bootstrap con localStorage;
- uso de API pública;
- ausencia de llamadas a localhost;
- navegación SPA por sidebar/hotkeys/Ctrl+K;
- las 20 tabs;
- health honesto;
- dashboard sin spinner infinito;
- chat round trip o error controlado;
- documents list/detail o empty state;
- jobs, approvals, audit;
- mail read-only;
- estados disabled/degraded accionables;
- responsive y consola limpia.

Backend:

- public endpoints;
- protected endpoints con auth;
- negative auth;
- malformed payloads;
- invalid UUIDs;
- nonexistent resources;
- CORS preflight;
- no secretos;
- no 500 esperados;
- guards de mail, DNS, dangerous tools y sandbox.

E2E:

- UI pública opera contra API pública;
- `cogos.api` apunta a `https://cognitive-api.doctormanzur.com`;
- no fetch a `localhost`/`127.0.0.1`;
- health/jobs/approvals/audit reflejan backend real;
- mail no permite draft/send normal;
- Action Plane no ejecuta writes reales;
- Document Analysis/Research/Code Director crean jobs o degradan con explicación.

## Cómo autenticar UI

1. Obtener JWT admin temporal.
2. Enmascarar el valor en reportes.
3. En pre-step del navegador TestSprite:

```js
localStorage.setItem('cogos.token', '<JWT>');
localStorage.setItem('cogos.api', 'https://cognitive-api.doctormanzur.com');
```

4. Navegar a `https://cognitive.doctormanzur.com`.
5. Recargar si TopBar no refleja `Connected`.

## Cómo autenticar API

Todas las llamadas protegidas deben usar:

```http
Authorization: Bearer <JWT>
```

El JWT completo no debe imprimirse. En reportes sólo se permite forma enmascarada, por ejemplo `eyJhbGciOi...<redacted>`.

## Cómo distinguir bug real de comportamiento esperado

No es bug:

- 404 al navegar directamente a `/dashboard`, `/health`, `/mail`, `/chat`, etc.;
- 401 sin JWT;
- 401 con JWT inválido o expirado;
- 403 por rol insuficiente;
- 4xx al probar flujos prohibidos;
- proveedor `disabled` o `degraded` si la UI/API explica el motivo;
- latencia razonable en LLM/research/chat si termina en éxito o error controlado;
- placeholder local `http://127.0.0.1:8000` antes de sembrar `cogos.api`, siempre que las requests reales usen la API pública después del seed.

Bug real:

- UI pública llama `localhost` o `127.0.0.1` tras seed;
- CORS/mixed-content rompe uso público;
- endpoint central devuelve 5xx ante payload inválido o estado esperado;
- health muestra verde sin verificación honesta;
- readiness omite causa accionable;
- mail puede crear draft/send en flujo normal;
- DNS write real queda disponible por default;
- Action Plane duplica dispatch o side effect;
- secretos aparecen en UI/API/log/report;
- jobs quedan colgados sin JobEvent ni explicación;
- botones críticos no hacen nada ni informan estado.
