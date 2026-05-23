# 00 Scope - Commercial Zero Friction Hardening

Fecha: 2026-05-22
Branch inicial: `codex/commercial-zero-friction-hardening`
Commit base: `e76ef195580f9d7f96c0b718692daa6e031bf355`

## Mandato

Auditar y endurecer Cognitive OS contra sus contratos canonicos, priorizando
`OPERATOR_PROFILE=dedicated_local` + `LOCAL_AUTONOMY_MODE=full`.

La definicion de "infalible" usada aqui no es SaaS multiusuario. Es:

- falla visible, diagnosticable y recuperable;
- health/readiness honesto;
- jobs, approvals y action requests observables;
- idempotencia y reapers;
- tests hermeticos y DB de test aislada;
- Playwright que cubre flujos reales, no solo home;
- mail normal read-only: no drafts, no send;
- cero friccion indebida en `dedicated_local/full`.

## Precedencia documental

1. `docs/CURRENT_STATE.md`
2. `docs/ZERO_FRICTION_OPERATING_MODEL.md`
3. `README.md`, `docs/USER_GUIDE.md`, `docs/PROJECT_GUIDE.md`,
   `docs/ARCHITECTURE.md`, `docs/COGNITIVE_OS_GUIDE.md`,
   `docs/AGENT_LEARNING_PLAN.md`, `docs/ACTION_PLANE.md`,
   `docs/RUNBOOK.md`
4. `docs/qa/*`, `docs/audits/*`, `task_plan.md`, `findings.md`,
   `progress.md`

## Evidencia inicial

```text
pwd: /home/jgonz/Escritorio/PROYECTO COGNITIVE OS
branch inicial: main
branch de trabajo: codex/commercial-zero-friction-hardening
commit base: e76ef195580f9d7f96c0b718692daa6e031bf355
worktree inicial: limpio
```

## Documentos leidos

- `docs/CURRENT_STATE.md`
- `docs/ZERO_FRICTION_OPERATING_MODEL.md`
- `README.md`
- `docs/USER_GUIDE.md`
- `docs/PROJECT_GUIDE.md`
- `docs/ARCHITECTURE.md`
- `docs/COGNITIVE_OS_GUIDE.md`
- `docs/AGENT_LEARNING_PLAN.md`
- `docs/ACTION_PLANE.md`
- `docs/RUNBOOK.md`
- `docs/qa/RUNBOOK.md`
- `docs/qa/FINAL_AUDIT_REPORT.md`
- `docs/qa/MAP.md`
- `docs/audits/CODEX_COMMERCIAL_READINESS_AUDIT.md`
- `task_plan.md`, `findings.md`, `progress.md` (bitacoras locales)

## Restricciones aplicadas

- No tocar `.env`, credenciales, datos productivos ni proveedores write.
- No usar live tests salvo `LIVE_TESTS_ENABLED=1`.
- No editar backups/snapshots.
- No reintroducir Tailwind, shadcn, MUI, tema claro ni iconos Unicode
  estructurales.
- Mantener mail read-only por defecto.
- Mantener `strict` disponible sin contaminar `dedicated_local/full`.
