# 18 — Targeted Rerun Results

Fecha: **2026-05-26**  
QA source: TestSprite MCP only.

## Focal reruns executed

| ID | Objetivo | Resultado TestSprite | Triage |
|---|---|---|---|
| `TCPUB001` | UI pública + auth seed + no localhost | **FAILED** | BLOCKED por harness MCP: navega primero a localhost |
| `TCAPI001` | API pública health/docs/openapi | **BLOCKED/TIMEOUT** | No produjo resultado nuevo confiable |

## TCPUB001 — Resultado detallado

| Campo | Valor |
|---|---|
| Artifact results | `test-results/testsprite_cursor/repair/focal/tcpub001-regenerated-results.json` |
| Artifact code | `test-results/testsprite_cursor/repair/focal/tcpub001-regenerated-code.py` |
| Terminal | `test-results/testsprite_cursor/repair/focal/tcpub001-regenerated-terminal.txt` |
| TestSprite status | `FAILED` |
| Expected | Primer navegador debe abrir `https://cognitive.doctormanzur.com/`, obtener token vía `POST /auth/local-token`, seed `cogos.token`/`cogos.api`, no navegar a localhost |
| Actual | Código generado navega primero a `http://localhost:3001/`, luego a público; TestSprite falla por la propia regla anti-localhost |
| Clasificación | **BLOCKED — TestSprite MCP fuerza `localEndpoint` local antes del caso** |
| Producto bug | No confirmado |

Fragmento relevante del código generado por TestSprite:

```text
await page.goto("http://localhost:3001/")
...
await page.goto("https://cognitive.doctormanzur.com/")
...
raise AssertionError("... navigated to http://localhost:3001 during setup ...")
```

## TCAPI001 — Resultado detallado

| Campo | Valor |
|---|---|
| Terminal | `test-results/testsprite_cursor/repair/focal/tcapi001-terminal.txt` |
| Resultado | Timeout / sin resultado TestSprite nuevo confiable |
| Clasificación | **BLOCKED** |
| Producto bug | No confirmado |

## Decisión

Los fixes de plan/harness se aplicaron, pero TestSprite MCP sigue imponiendo comportamiento local/túnel en ejecución. No se puede marcar `VERIFIED_FIXED` ningún P1 operativo sin soporte de TestSprite para:

1. URL pública first-class sin preflight `localhost`.
2. API plan activo/backend ejecutable sin `[]` ni `NaN`.

## Estados tras rerun

| ID | Estado |
|---|---|
| `TS-CURSOR-001` | **BLOCKED** |
| `TS-CURSOR-002` | **BLOCKED** |
| `TS-CURSOR-003` | **PARTIAL — casos agregados, suite completa no ejecutable aún** |
| `TS-CURSOR-004` | **FIXED_PENDING_RERUN** |
