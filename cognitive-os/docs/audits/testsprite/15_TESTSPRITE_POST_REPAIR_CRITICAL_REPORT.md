# 15 - TestSprite Post-Repair Critical Report

Fecha UTC: 2026-05-24

## Scope

Pasada critica post-reparacion ejecutada con TestSprite MCP en lotes para evitar
que el runner frontend quedara abierto una hora despues de completar.

- UI: `https://cognitive.doctormanzur.com`
- API: `https://cognitive-api.doctormanzur.com`
- Backend auth: `POST /auth/local-token`, usando `access_token` en memoria y sin
  imprimir JWT completo.

## UI / E2E critical

### Batch A

- Artifacts: `test-results/testsprite/post-repair-critical/ui-e2e-batch-a/`
- Casos:
  - `TC005 Move between main cockpit views without leaving the app`: PASS.
  - `TC007 Run live health verification and see updated statuses`: PASS.
  - `TC017 Review MCP server connection status`: PASS.
- Resultado: 3/3 PASS.

### Batch B

- Artifacts: `test-results/testsprite/post-repair-critical/ui-e2e-batch-b/`
- Casos:
  - `TC003 Keep mail read-only for normal send actions`: PASS.
  - `TC018 Review the current job queue`: PASS.
  - `TC020 Review the Approvals queue when it is empty or malformed`: BLOCKED
    por caso mal especificado; la cola estaba poblada y estable, no vacia.
  - `TC027 Handle a malformed audit list gracefully`: PASS.
- Resultado bruto: 3 PASS, 1 BLOCKED no-bug.

### TC020 corrected rerun

- Artifacts:
  `test-results/testsprite/post-repair-critical/ui-e2e-tc020-rerun/`
- Caso:
  - `TC020 Review the Approvals queue in empty or populated state`: PASS.
- Resultado final UI/E2E critical: PASS.

## API critical

### Initial API critical

- Artifacts:
  `test-results/testsprite/post-repair-critical/api-critical/initial-6-case/`
- Casos:
  - `TCAPI001 public health/docs`: PASS.
  - `TCAPI002 local token + readiness`: FAIL por expectativa incorrecta del
    runner, no por backend.
  - `TCAPI003 auth negative`: PASS.
  - `TCAPI004 read-only operational groups`: PASS.
  - `TCAPI005 CORS preflight`: PASS.
  - `TCAPI006 dangerous mail/DNS`: FAIL por buscar `token` en vez de
    `access_token`; ademas el runner intento POST mail no aceptados como
    evidencia de contrato mail.
- Resultado bruto: 4 PASS, 2 instrumentation FAIL.

### Corrected targeted API

- Artifacts:
  - `test-results/testsprite/repair-reruns/api-targeted-final/`
  - `test-results/testsprite/post-repair-critical/api-critical/mail-get-only/`
- Casos:
  - `TCAPI002 local token + readiness`: PASS con schema PRD correcto.
  - `TCAPI007 mail contract GET-only`: PASS.
- Resultado final API critical: PASS.

## Contratos criticos

- UI usa dominio publico y no requiere pseudo-rutas: PASS.
- Health live ya no queda bloqueado en `Verificando...`: PASS.
- MCP status visible y honesto: PASS.
- Jobs/Audit renderizan estado estable: PASS.
- Approvals con cola poblada estable y acciones guardadas: PASS tras ajuste de
  caso.
- Mail read-only sin send/draft normal en UI: PASS.
- Mail API validado por GET-only; no se usa como evidencia el caso que intento
  dispatch: PASS.
- Auth negative missing/invalid token: PASS.
- CORS public frontend origin: PASS.
- No P0/P1/P2 real abierto: PASS.

## Riesgos residuales

- Los raw reports de TestSprite siguen trayendo placeholders
  `{{TODO:AI_ANALYSIS}}`; la interpretacion consolidada esta en este reporte y
  en `14_TESTSPRITE_TARGETED_RERUN_RESULTS.md`.
- TestSprite genera a veces scripts con assertions demasiado estrictas o con
  acciones que contradicen restricciones del prompt. Se corrigieron los casos
  afectados y se preservaron artifacts antes/despues.
- No se ejecuto full-qa, pytest completo, stress-qa, linters ni Playwright local
  manual, por restriccion explicita del prompt.

## Estado final

Post-repair critical: PASS.
