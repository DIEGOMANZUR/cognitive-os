# Contrato del agente — 60 segundos

**Si no cumples esto, no ejecutes TestSprite.**

## Garantía

No dependes de “recordar bien”. El repo **rechaza** la corrida si repites el error del tunnel
(`health:80`) o declaras PASS sin evidencia. Entrypoint único con gates automáticos:

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os"
bash scripts/testsprite_audit.sh
```

Si ese comando no termina con `VERDICT TestSprite: PASS`, **no** digas que TestSprite pasó.

## Excepción explícita: Web Portal

Si el usuario pide usar TestSprite desde el sitio web/frontend/Edge/browser session o subir PRDs en el portal, este contrato MCP/local no aplica como ruta de ejecución. En ese caso:

```text
Leer y seguir .cursor/skills/testsprite-web-portal-cognitive-os/SKILL.md
```

También en portal: no hay PASS sin reporte TestSprite limpio y artifacts locales.

## 10 reglas

1. Entrypoint único MCP/local: `bash scripts/testsprite_audit.sh`.
2. Leer antes: `SKILL.md`, `MISTAKES.md`, `DECISION_TREE.md`.
3. Prohibido: MCP `generate_code_and_execute` con `testIds: []`.
4. Prohibido: `node …/generateCodeAndExecute` sin `full-testsprite.sh`.
5. Obligatorio: `testsprite_mcp_prepare.sh` aunque MCP diga "skip bootstrap".
6. Obligatorio: smoke TC001 validado por `assert_testsprite_run.py --mode smoke`.
7. `serverMode: production` en config y executionArgs (validate lo exige).
8. Sin URLs en `additionalInstruction` (validate lo exige).
9. Serial: una fase; no MCP + shell en paralelo.
10. TestSprite falló → `full-qa.sh` + Playwright; reporte BLOCKED, no PASS falso.

## Scripts que te protegen

| Script | Función |
|---|---|
| `scripts/testsprite_audit.sh` | Orquestador único |
| `scripts/load_testsprite_env.sh` | Carga API key sin romper `.env` |
| `validate_testsprite_config.py` | Config fail-closed pre-run |
| `assert_testsprite_run.py` | Post-run smoke/full fail-closed |

## Recovery estándar

```bash
export TESTSPRITE_API_KEY=...   # si falta
bash scripts/testsprite_mcp_prepare.sh
TESTSPRITE_AUDIT_PHASE=smoke bash scripts/testsprite_audit.sh
bash scripts/testsprite_audit.sh
```
