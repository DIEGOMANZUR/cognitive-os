# 12 — E2E Results

Fecha: **2026-05-26**  
Suite objetivo: **E2E Integrated**  
Estado suite: **BLOCKED / NOT RUN**

## Razón de bloqueo

La suite E2E depende de dos precondiciones:

1. UI smoke válido contra `https://cognitive.doctormanzur.com/`.
2. API smoke válido contra `https://cognitive-api.doctormanzur.com`.

Ambas fallaron como precondición de TestSprite:

- UI `TC001` pasó, pero generó código contra `http://localhost:3001/` y token dummy.
- API `TCAPI001` no produjo resultados (`[]`, reporte `NaN`).

Por lo tanto, ejecutar la suite E2E habría producido una auditoría inválida.

## Casos planificados no ejecutados

| ID | Journey | Estado |
|---|---|---|
| `TE2E001` | Public UI auth seed + Connected TopBar | BLOCKED |
| `TE2E002` | Health tab reflects public backend | BLOCKED |
| `TE2E003` | Jobs tab lists jobs from API | BLOCKED |
| `TE2E004` | Approvals tab read-only list | BLOCKED |
| `TE2E005` | Chat roundtrip or controlled failure | BLOCKED |
| `TE2E006` | Documents list/detail or empty | BLOCKED |
| `TE2E007` | Document Analysis controlled start | BLOCKED |
| `TE2E008` | Research controlled start | BLOCKED |
| `TE2E009` | Mail read-only surface | BLOCKED |
| `TE2E010` | Action Plane preview/request guard | BLOCKED |
| `TE2E011` | MCP status in System/Settings | BLOCKED |
| `TE2E012` | Code Director plan-only | BLOCKED |
| `TE2E013` | Zero-friction dedicated_local/full | BLOCKED |
| `TE2E014` | No localhost fetch from public origin | BLOCKED |
| `TE2E015` | No CORS/mixed-content | BLOCKED |

## Artifacts

No TestSprite E2E artifacts fueron generados porque no se ejecutó la suite.

## Decisión

**No ejecutar hasta que UI/API smoke sean válidos por TestSprite contra los targets públicos del PRD.**
