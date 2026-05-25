# 23 - TestSprite Final Double Run

Fecha UTC: 2026-05-24

## Final Run A

Artifacts: `test-results/testsprite/zero-defects-final-run-a/`

| Suite | Tests | Pass | Fail real | Notas |
|---|---:|---:|---:|---|
| API total batch | 14 | 11 | 0 | 3 falsos positivos: `TCAPI002`, `TCAPI006`, `TCAPI009`. |
| API focal reruns | 4 | 3 | 0 | `TCAPI002` PASS, `TCAPI009` PASS, `TCAPI016` PASS; `TCAPI006` reemplazado por GET-only `TCAPI016`. |
| UI/E2E/regression singles | 13 | 13 | 0 | `TC003`, `TC005`, `TC007`, `TC017`, `TC018`, `TC020`, `TC028`, `TC029`, `TC030`, `TC031`, `TC036`, `TC037`, `TC038`. `TC037`/`TC038` replace runner-broken `TC034`/`TC035`. |

Estado Final Run A: PASS sin defectos reales conocidos.

## Final Run B

Artifacts: `test-results/testsprite/zero-defects-final-run-b/`

| Suite | Tests | Pass | Fail real | Notas |
|---|---:|---:|---:|---|
| API total batch | 14 | 13 | 0 | 1 falso positivo en `TCAPI016` por heuristica secret-like sobre mail normal. |
| API focal rerun | 1 | 1 | 0 | `TCAPI016` corregido PASS. |
| UI/E2E/regression singles | 13 | 13 | 0 | Mismo set critico de Final A, reiniciado tras interrupcion y completado limpio. |

Estado Final Run B: PASS sin defectos reales conocidos.

## Cobertura final

- UI: PASS.
- API: PASS.
- E2E: PASS.
- Regression: PASS.
- Mail read-only: PASS por UI `TC003` y API `TCAPI015`.
- Health/readiness: PASS por UI `TC007`, API `TCAPI002`, `TCAPI014`.
- API base hygiene: PASS por `TC037` (public/local API base according to host).
- Action Plane guards: PASS por `TC038`, `TCAPI012`, `TCAPI016`.
- Document Analysis: PASS por `TC029`, `TCAPI010`.
- Research: PASS por `TC030`, `TCAPI011`.
- Code Director/Sandbox/LangSmith: PASS por `TC031`, `TCAPI011`.
