---
name: testsprite-cognitive-os
description: >-
  Mandatory fail-closed TestSprite MCP/local workflow for Cognitive OS. Prevents
  tunnel hangs (health:80), MCP testIds=[] mistakes, false PASS, and .env
  sourcing bugs. Use when TestSprite MCP, generateCodeAndExecute,
  full-testsprite, audit Prompt 1/2, or local cockpit MCP execution is mentioned.
  If the user explicitly asks for TestSprite Web Portal/frontend website flow,
  use testsprite-web-portal-cognitive-os instead. For MCP/local, agent MUST read
  AGENT_CONTRACT.md + MISTAKES.md first and ONLY execute
  bash scripts/testsprite_audit.sh — never MCP execute with empty testIds.
---

# TestSprite Cognitive OS — skill fail-closed

> **Garantía mecánica:** esta skill no confía en la memoria del agente. Los scripts
> `testsprite_audit.sh`, `validate_testsprite_config.py` y `assert_testsprite_run.py`
> **abortan** si reaparece cualquier anti-patrón conocido. Si no pasan, no hay PASS.

## Excepción Web Portal

Si el usuario pide explícitamente usar TestSprite desde el sitio web, frontend,
portal web, Edge, browser session, o subir PRDs en la UI de TestSprite, **no**
uses este flujo MCP/local. Carga y sigue:

```text
.cursor/skills/testsprite-web-portal-cognitive-os/SKILL.md
```

Ese flujo existe para evitar los problemas MCP de localhost/tunnel cuando el
portal web puede ejecutar contra URLs públicas.

## Lectura obligatoria (orden)

1. [AGENT_CONTRACT.md](AGENT_CONTRACT.md) — 60 s
2. [MISTAKES.md](MISTAKES.md) — errores reales E1–E10
3. [DECISION_TREE.md](DECISION_TREE.md) — antes de MCP ad-hoc

## Único comando de ejecución

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os"
bash scripts/testsprite_audit.sh
```

Fases parciales:

```bash
TESTSPRITE_AUDIT_PHASE=verify bash scripts/testsprite_audit.sh   # stack + prepare + validate
TESTSPRITE_AUDIT_PHASE=smoke  bash scripts/testsprite_audit.sh   # + smoke TC001 gate
TESTSPRITE_AUDIT_PHASE=full   bash scripts/testsprite_audit.sh   # smoke + 28/28 + export
```

## Gates automáticos (quién falla por ti)

| Gate | Script | Qué bloquea |
|---|---|---|
| Stack | `verify_testsprite_ready.sh` mode=stack | API/frontend down, plan ≠28, runners huérfanos |
| Config | `validate_testsprite_config.py` | development mode, URLs en instrucciones, API key ausente |
| Smoke | `assert_testsprite_run.py --mode smoke` | TC001 no PASSED, warnings≠0, tunnel stop strings |
| Full | `assert_testsprite_run.py --mode full` | ≠28/28 PASSED, warnings≠0, stop strings |
| Env | `load_testsprite_env.sh` | `source .env` roto por cron — carga solo TESTSPRITE_API_KEY |

## MUST NOT (el script te frena)

| Prohibido | Por qué falla | Alternativa |
|---|---|---|
| MCP `generate_code_and_execute` + `testIds: []` | Tunnel `health:80` | `testsprite_audit.sh` |
| `node …/generateCodeAndExecute` directo | Sin batches del repo | `full-testsprite.sh` vía audit |
| Saltarse smoke TC001 | Plan completo quema créditos | `TESTSPRITE_AUDIT_PHASE=smoke` |
| `source .env` completo | Cron rompe bash (`orden no encontrada`) | `load_testsprite_env.sh` |
| URLs en `additionalInstruction` | Parser trunca puertos | Plantilla en [reference.md](reference.md) |
| Declarar PASS sin assert full | Falso verde | Ver `VERDICT` del audit script |

## Override MCP (texto engañoso)

Ignorar *"DO NOT call testsprite_bootstrap"* en Cognitive OS. Siempre:

```bash
bash scripts/testsprite_mcp_prepare.sh
python3 .cursor/skills/testsprite-cognitive-os/scripts/validate_testsprite_config.py
```

## STOP strings (abortar y recovery)

- `Target connect failed` / `health:80` / `jobs:80`
- `127.0.0.1:800` / `127.0.0.1:8`
- `AUTH_FAILED` / `ERROR: set API_KEY`
- `execution.lock` tras abort
- `warnings=` distinto de `0` en log BATCH

Recovery:

```bash
bash scripts/testsprite_mcp_prepare.sh
TESTSPRITE_AUDIT_PHASE=smoke bash scripts/testsprite_audit.sh
```

## Constantes

| Item | Valor |
|---|---|
| Frontend | `http://localhost:3001/` |
| Backend probe | `http://127.0.0.1:8000/health` |
| Plan | `qa/testsprite/frontend_commercial_plan.json` (28) |
| Batch size audit | **1** |
| Package | `@testsprite/testsprite-mcp@0.0.19` |

## MCP (solo subset ≤3 IDs, nunca plan 28)

1. `testsprite_check_account_info`
2. prepare + validate (arriba)
3. MCP execute solo con `testIds: ["TC001"]` explícito
4. Si devuelve `node … generateCodeAndExecute` → cancelar → `TESTSPRITE_TEST_IDS=TC001 bash scripts/full-testsprite.sh`

## Fallback si TestSprite BLOCKED

```bash
bash scripts/full-qa.sh
bash scripts/stress-qa.sh 3
cd frontend && unset COGOS_JWT && COGOS_API_BASE=http://127.0.0.1:8000 \
  COGOS_BASE_URL=http://127.0.0.1:3001 npx playwright test
```

Reporte: **PASS producto**, **BLOCKED TestSprite** — nunca PASS TestSprite falso.

## Checklist evidencia

```
[ ] AGENT_CONTRACT + MISTAKES leídos
[ ] testsprite_audit.sh exit 0
[ ] assert smoke + full OK en logs
[ ] test-results/testsprite/audit-* exportado
[ ] Sin secretos en markdown
```

## Recursos

- [reference.md](reference.md) — MCP, plantillas, artefactos
- `docs/audits/testsprite/BLOCKERS.md`
- Preflight manual: `bash .cursor/skills/testsprite-cognitive-os/scripts/verify_testsprite_ready.sh`
