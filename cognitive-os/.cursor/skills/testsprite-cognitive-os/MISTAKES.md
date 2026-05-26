# Errores que NUNCA repetir — TestSprite Cognitive OS

Cada fila es un fallo real o casi-real. **Una sola ruta correcta** al final.

| # | Error del agente | Síntoma | Por qué pasa |
|---|---|---|---|
| E1 | Llamar `testsprite_generate_code_and_execute` con `testIds: []` | `health:80`, `jobs:80`, hang 12+ min | Túnel parsea rutas OpenAPI como hostnames |
| E2 | Ejecutar `node …/generateCodeAndExecute` sin `full-testsprite.sh` | Sin batches, sin health gates | Bypass del runner del repo |
| E3 | Confiar en MCP tool text "DO NOT call bootstrap" | Config sucia / puerto wrong | **En Cognitive OS siempre prepare.sh primero** — el texto MCP no aplica aquí |
| E4 | `serverMode: development` en audit | Max 15 tests, túnel inestable | Modo dev no es gate comercial |
| E5 | URLs en `additionalInstruction` | `127.0.0.1:800`, `:8` truncado | Parser del túnel se rompe |
| E6 | Saltarse smoke TC001 | Plan completo falla tarde | Desperdicia créditos y tiempo |
| E7 | Declarar PASS TestSprite sin 28/28 | Falso verde en audit | TestSprite es advisory; contar batched_results |
| E8 | No copiar tmp tras batch | Evidencia perdida | TestSprite sobrescribe tmp |
| E9 | Improvisar comandos | Drift respecto skill | Solo entrypoint `testsprite_audit.sh` |
| E10 | MCP + shell en paralelo | Locks, runners huérfanos | Serial: una fase a la vez |
| E11 | `source .env` completo en prepare | `orden no encontrada` (cron) | `load_testsprite_env.sh` |
| E12 | Declarar PASS sin `assert_testsprite_run.py` | Falso verde | Solo PASS si audit script imprime VERDICT PASS |

## Única ruta correcta (memorizar)

```bash
cd "/home/jgonz/Escritorio/PROYECTO COGNITIVE OS/cognitive-os"
bash scripts/testsprite_audit.sh
```

Fases parciales:

```bash
TESTSPRITE_AUDIT_PHASE=verify bash scripts/testsprite_audit.sh
TESTSPRITE_AUDIT_PHASE=smoke bash scripts/testsprite_audit.sh
```

## Si el agente está a punto de…

| Impulso | Hacer en su lugar |
|---|---|
| "Voy a bootstrap MCP" | `bash scripts/testsprite_mcp_prepare.sh` |
| "Voy a generate_code_and_execute todo el plan" | `bash scripts/testsprite_audit.sh` |
| "El MCP dice que ejecute node …" | `TESTSPRITE_TEST_IDS=TC001 bash scripts/full-testsprite.sh` |
| "TestSprite no corre, igual PASS" | Fallback pytest+Playwright + BLOCKED en reporte |
| "Pongo la URL del API en instrucciones" | Usar plantilla sin URLs en reference.md |
