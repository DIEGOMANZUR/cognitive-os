# 17 - TestSprite Zero Defects Context

Fecha UTC: 2026-05-24

## Fuentes leidas

- PRD canonicos:
  - `/home/jgonz/Escritorio/testsprite/PRD.md`
  - `/home/jgonz/Escritorio/testsprite/PRD_FRONTEND.md`
  - `/home/jgonz/Escritorio/testsprite/PRD_BACKEND.md`
  - `/home/jgonz/Escritorio/testsprite/cognitive-os-launchers-README.md`
- Reportes TestSprite previos:
  - `01_TESTSPRITE_INPUT_REVIEW.md` a `16_TESTSPRITE_REPAIR_FINAL_REPORT.md`
- Artifacts previos:
  - `test-results/testsprite/initial-full-audit/`
  - `test-results/testsprite/repair-reruns/`
  - `test-results/testsprite/post-repair-critical/`

No faltaron archivos obligatorios del prompt final.

## Que se probo antes de este loop

- UI publica `https://cognitive.doctormanzur.com`.
- API publica `https://cognitive-api.doctormanzur.com`.
- Bootstrap UI, Health live, MCP status, Jobs, Approvals, Audit, Mail
  read-only y API critical read-only.
- Auth UI por `localStorage` y auth API por `Authorization: Bearer`.
- CORS public frontend origin.
- Mail no-send/no-draft desde UI y API GET-only.

## Que fallo inicialmente

- TS-001 P1: UI publica podia quedar con `Failed to fetch`, Health sin lecturas
  y `Verificando...`, por carrera entre default local y `localStorage`.
- TS-004 P2: Settings ocultaba `MCP servers` cuando `/system/mcp` no cargaba.
- TS-002/TS-003: gaps de TestSprite API, no bugs de runtime:
  - lectura de `/tmp` desde sandbox remoto;
  - plan backend de 1 solo caso.
- TC020: caso TestSprite asumio cola Approvals vacia, pero runtime real tenia
  cola poblada y estable.

## Que se corrigio

- `useLocalState` lee `localStorage` sincronamente en navegador.
- La UI publica usa `https://cognitive-api.doctormanzur.com` como default cuando
  se sirve desde `cognitive.doctormanzur.com`.
- Auto-token y Health live tienen timeout accionable.
- `MCP servers` se renderiza siempre con estado honesto.
- Planes TestSprite API/UI se ajustaron:
  - `TCAPI001`-`TCAPI007`;
  - `TC020` acepta Approvals poblado o empty state.

## Riesgos que quedan para revalidar

- TestSprite a veces genera assertions demasiado estrictas o acciones
  prohibidas aunque el prompt las bloquee. Debe triagearse cada fallo contra
  PRD antes de tocar codigo.
- La UI tiene muchas superficies; este loop final debe cubrir tabs no
  ejercitadas en la reparacion: DeepAgents, Skills, Memoria, Asistente, Google
  Ops, Document Analysis, Research, Code Director, Sandbox y LangSmith.
- Los raw reports TestSprite pueden contener placeholders; la evidencia final
  se consolida en `20` a `24`.

## Que TestSprite debe revalidar

- UI total por tabs, command palette, hotkeys, notifications, consola, network,
  no localhost y no mixed content.
- API total por grupos public/protected, auth negative, CORS, malformed payload,
  invalid UUID, no secrets y no 5xx esperables.
- E2E UI publica -> API publica para health, jobs, approvals, chat, documents,
  document analysis, research, mail, action plane, MCP y Code Director.
- Regression cases de TS-001, TS-004, TS-002, TS-003, TS-005 y TC020.

## Suites existentes

- `testsprite_tests/testsprite_frontend_test_plan.json`
- `testsprite_tests/testsprite_backend_test_plan.json`
- Artifacts:
  - `test-results/testsprite/repair-reruns/`
  - `test-results/testsprite/post-repair-critical/`

## PRD por area

- PRD.md: contrato global local-first, dedicated_local/full, no falsos verdes,
  no writes peligrosos y zero-friction.
- PRD_FRONTEND.md: SPA en `/`, tabs internas, `localStorage` auth, API publica
  en auditoria, no pseudo-rutas, estados accionables.
- PRD_BACKEND.md: endpoints public/protected, Bearer auth, health/readiness,
  mail read-only, forbidden actions bloqueadas y no 5xx esperables.
