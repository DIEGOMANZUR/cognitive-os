# Degradation And Recovery Tests

## Verified Degradation Coverage

| Scenario | Evidence | Result |
|---|---|---|
| Invalid JWT | Playwright auth spec, backend auth negative tests | PASS |
| Missing JWT | Backend API auth tests; UI auto-token path | PASS |
| Health configured vs verified | Playwright `health-verified-vs-configured`; `/health/verify` | PASS |
| MCP status | `/system/mcp` HTTP 200, 5 servers, 67 tools | PASS |
| Mail disabled/read-only states | Playwright mail specs, TestSprite TC003 | PASS |
| Malformed frontend lists | Playwright malformed list payloads | PASS |
| Jobs failed/running states | Playwright commercial fixtures | PASS |
| Action dispatch broker failure | Backend tests cover Celery dispatch failure with operator-visible reason | PASS |
| Voice status without secret leak | Backend voice tests and TestSprite TCAPI014 | PASS |

## Not Simulated Destructively

We did not intentionally stop Redis, Postgres, Weaviate, Neo4j, or mutate external providers during final close because the prompt forbids destructive or real external writes. Equivalent safe tests were run through health/readiness, mocks, Playwright malformed responses, and backend failure-path unit tests.

Residual: no product degradation defect remains known.

