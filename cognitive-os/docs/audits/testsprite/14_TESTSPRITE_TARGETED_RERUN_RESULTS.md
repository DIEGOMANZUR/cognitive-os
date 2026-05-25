# 14 - TestSprite Targeted Rerun Results

Fecha UTC: 2026-05-24

## Resumen

Reruns focales ejecutados con TestSprite MCP contra:

- UI publica: `https://cognitive.doctormanzur.com`
- API publica: `https://cognitive-api.doctormanzur.com`

No se usaron pytest, full-qa, stress-qa, linters ni Playwright local manual.

## TS-001 - UI public auto-token / Health live

- Fix: lectura sincronica de `localStorage`, default API publico en dominio
  publico, timeout de auto-token y timeout de Health live.
- Suite rerun: UI focal.
- Casos:
  - `TC007 Run live health verification and see updated statuses`
- Resultado: PASS.
- Artifacts:
  - `test-results/testsprite/repair-reruns/ui-targeted/test_results.json`
  - `test-results/testsprite/repair-reruns/ui-targeted/raw_report.md`
- Estado final: VERIFIED FIXED.

## TS-004 - MCP status visible en degradacion

- Fix: `SettingsView` renderiza siempre `MCP servers` con estado conectado,
  loading, error, disabled o sin datos.
- Suite rerun: UI focal.
- Casos:
  - `TC017 Review MCP server connection status`
- Resultado: PASS.
- Artifacts:
  - `test-results/testsprite/repair-reruns/ui-targeted/test_results.json`
  - `test-results/testsprite/repair-reruns/ui-targeted/raw_report.md`
- Estado final: VERIFIED FIXED.

## TS-002 - API auth injection TestSprite

- Fix: no fue bug de producto. Se ajusto el plan TestSprite API para no leer
  `/tmp` desde el sandbox remoto y usar `POST /auth/local-token` con
  `access_token` en memoria.
- Suite rerun: API critical / targeted.
- Casos iniciales:
  - `TCAPI001 public health/docs`: PASS.
  - `TCAPI002 local token + readiness`: FAIL por expectativa incorrecta del
    runner (`services/capabilities` en readiness).
  - `TCAPI003 auth negative`: PASS.
  - `TCAPI004 read-only operational groups`: PASS.
  - `TCAPI005 CORS preflight`: PASS.
  - `TCAPI006 dangerous mail/DNS`: FAIL por buscar `token` en vez de
    `access_token`.
- Correccion de plan:
  - `TCAPI002` actualizado al schema real PRD:
    `operator_profile`, `local_autonomy_mode`, `summary`,
    `target_capabilities_unlocked`, `target_capabilities_total`, `gaps`.
  - `TCAPI007` agregado para validar mail contract con GET-only.
- Resultado final:
  - `TCAPI002`: PASS.
  - `TCAPI007`: PASS.
- Artifacts:
  - `test-results/testsprite/repair-reruns/api-critical-initial/`
  - `test-results/testsprite/repair-reruns/api-targeted-final/`
- Estado final: TestSprite instrumentation fixed; no backend bug real abierto.

## TS-003 - Backend plan insuficiente

- Fix: no fue bug de producto. Se expandio el plan backend TestSprite con
  casos `TCAPI001` a `TCAPI007`.
- Rerun requerido: API critical.
- Resultado: cubierto por los reruns API anteriores.
- Estado final: coverage gap mitigado para esta reparacion.

## TS-005 - Mail proposals/digest no cubiertos

- Fix: no bug segun PRD. Se valido el contrato seguro:
  - UI `TC003` PASS: Mail no expone send/draft normal.
  - API `TCAPI007` PASS: GET-only mail status/messages/openapi, sin POST bajo
    `/mail`.
- Nota: un intento previo de `TCAPI006` generado por TestSprite llamo
  `/mail/sync/dispatch` y `/mail/digest/dispatch` pese a las instrucciones. No
  se usa como evidencia de contrato mail; queda documentado como drift del
  runner.
- Estado final: no bug real abierto.

## TC020 Approvals

- Observacion: TestSprite bloqueo el caso original porque la cola no estaba
  vacia: habia 309 approvals visibles y botones Approve/Reject deshabilitados.
- Clasificacion: no bug. El PRD permite cola poblada; el caso generado asumio
  empty state.
- Ajuste: `TC020` ahora acepta cola poblada estable o empty state estable.
- Rerun: `TC020 Review the Approvals queue in empty or populated state`.
- Resultado: PASS.
- Artifacts:
  - `test-results/testsprite/post-repair-critical/ui-e2e-tc020-rerun/`
- Estado final: VERIFIED PASS con contrato corregido.

## Estado

- P0 restantes: 0.
- P1 reales restantes: 0.
- P2 reales restantes: 0.
- Bloqueos externos: ninguno que impida cierre; los warnings de tunnel
  TestSprite `control websocket closed` aparecieron despues de completar tests y
  no produjeron fallos.
