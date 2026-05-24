# 00 Scope

Pasada Codex iniciada el 2026-05-23 en la rama
`codex/commercial-zero-friction-hardening`, desde HEAD inicial
`d25af91a2256662df36a4e675d2ad1e771b5f936`.

## Mandato

Auditar Cognitive OS contra sus Markdown canonicos y endurecer el proyecto sin
cambiar su postura de producto:

- local-first, mono-operador, PC dedicado;
- `OPERATOR_PROFILE=dedicated_local`;
- `LOCAL_AUTONOMY_MODE=full`;
- cero friccion operativa por encima de seguridad SaaS estricta;
- trazabilidad, diagnostico, idempotencia y recuperacion fuertes;
- mail normal read-only: leer, clasificar, resumir y proponer texto, sin drafts
  ni envio.

## Documentos leidos

Orden de lectura aplicado:

1. `docs/CURRENT_STATE.md`
2. `docs/ZERO_FRICTION_OPERATING_MODEL.md`
3. `README.md`
4. `docs/USER_GUIDE.md`
5. `docs/PROJECT_GUIDE.md`
6. `docs/ARCHITECTURE.md`
7. `docs/COGNITIVE_OS_GUIDE.md`
8. `docs/AGENT_LEARNING_PLAN.md`
9. `docs/ACTION_PLANE.md`
10. `docs/RUNBOOK.md`
11. `docs/qa/*`
12. `docs/audits/*`
13. `docs/audits/testsprite/34_COMMERCIAL_QUALITY_CERTIFICATION.md`

## Reglas de precedencia

1. `docs/CURRENT_STATE.md`
2. `docs/ZERO_FRICTION_OPERATING_MODEL.md`
3. Codigo y tests reales
4. Guias secundarias, runbooks y reportes historicos

Cuando una guia secundaria contradice el contrato canonico, se corrige la guia
secundaria. Cuando el codigo contradice el contrato vigente, se corrige el
codigo con test de regresion.

## Alcance de esta pasada

Incluido:

- inventario de contratos documentales verificables;
- inventario de suites y gates existentes;
- correccion de falsos verdes de QA detectados durante esta pasada;
- correccion de documentacion secundaria obsoleta que contradice dark-only o
  conteos QA actuales;
- tests estaticos de regresion para que esos falsos verdes no vuelvan;
- actualizacion de bitacora QA de esta rama.

No incluido sin opt-in externo:

- writes contra proveedores reales;
- live tests si `LIVE_TESTS_ENABLED=1` no esta seteado por el operador antes de
  invocar el gate;
- TestSprite si no hay tool/CLI MCP disponible y funcional en la sesion;
- cambios de producto que introduzcan RBAC, confirmaciones humanas redundantes o
  postura SaaS multiusuario.

## Estado inicial observado

Comandos Fase 0:

```bash
pwd
git status --short
git branch --show-current
git rev-parse HEAD
```

Resultado:

- `pwd`: `/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os`
- branch: `codex/commercial-zero-friction-hardening`
- HEAD inicial: `d25af91a2256662df36a4e675d2ad1e771b5f936`
- cambios previos observados al inicio: ninguno en `git status --short`.

## Politica de ejecucion

- No borrar cambios existentes.
- No tocar `cognitive-os-backup-*` ni `cognitive-os-snapshot-*`.
- No bajar asserts, no agregar skips para esconder fallas.
- Preferir errores explicitos, health honesto, idempotencia y reapers sobre
  friccion humana.
- Mantener strict disponible sin contaminar `dedicated_local/full`.
