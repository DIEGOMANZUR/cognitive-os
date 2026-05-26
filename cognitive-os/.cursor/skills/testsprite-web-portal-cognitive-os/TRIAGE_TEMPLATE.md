# TestSprite Web Portal Triage Template

Use this template for local reports after a TestSprite Web Portal run.

```markdown
# [NN] — TestSprite Web Portal [UI/API/E2E/GUARD] Results

Fecha: **YYYY-MM-DD**
Fuente QA: **TestSprite Web Portal**
Proyecto TestSprite: `[name]`
Report URL: `[portal report URL]`
Estado: **PASS / PARTIAL / FAIL / BLOCKED**

## Resultado bruto

| Métrica | Valor |
|---|---:|
| Total cases | 0 |
| Passed | 0 |
| Failed | 0 |
| Blocked | 0 |

## Clasificación

| ID | Evidencia TestSprite | Clasificación | Motivo PRD |
|---|---|---|---|
| `WEB-[SUITE]-001` | `[exact observation]` | Real bug / Expected / False positive / Blocked / Flaky | `[PRD anchor]` |

## Bugs reales

- `[Real bug summary]`

## Falsos positivos / esperado

- `[Expected behavior with PRD reason]`

## Blocked

- `[Blocked reason and retry path]`

## Rerun recomendado

- `[Focused TestSprite titles or paths]`

## Veredicto

`[PASS/PARTIAL/FAIL/BLOCKED]`
```

## Classification Rules

Real bug:

- Documented API namespace returns 404 when PRD says it is required.
- UI critical view cannot load or stays in infinite loading.
- UI fetches `localhost`/`127.0.0.1` from public origin after seed.
- CORS/mixed-content/hydration/chunk critical error.
- Mail send/draft succeeds in normal flow.
- Health/readiness shows false green.
- Dangerous action succeeds without guard.
- Endpoint returns 5xx for controlled invalid input.

Expected behavior:

- SPA internal direct path returns 404.
- Missing/invalid token returns 401.
- Expired token returns 401.
- Insufficient role returns 403.
- Forbidden guard returns controlled 4xx/409.
- Provider disabled/degraded is explicit and non-5xx.

Blocked:

- TestSprite cannot create required fixture safely.
- Portal cannot parse uploaded docs.
- Browser upload is blocked by security.
- TestSprite consumes wrong credential type.
- Feature exploration times out before a report exists.

False positive:

- Only when PRD explicitly supports observed behavior.
- Always cite the PRD reason.

## Report Paths

Use:

- `docs/audits/testsprite_cursor/[NN]_WEB_PORTAL_[SUITE]_RESULTS.md`
- `test-results/testsprite_cursor/web_portal_[suite]_report_summary.md`

Never include raw JWTs, TestSprite API key, browser cookies, or secret-shaped values.
