# TestSprite Web Portal UI QA Compatibility Fix Log

Superseded: this compatibility approach was rejected on 2026-05-26 because it used
synthetic UI data. The active direction is no demo data, no provisional UI
fallbacks, and no false success states. Authentication uses only
`#cogos_token=<JWT_WITHOUT_BEARER>`, and Documents/Audit/Health must reflect real
backend state.

Date: 2026-05-26

## Current Replacement

- Removed frontend QA mode and all UI-side demo/fixture fallbacks.
- Kept only real hash-token bootstrap: `#cogos_token=<JWT_WITHOUT_BEARER>`.
- Kept real UI improvements: stronger hotkeys, document detail view for persisted documents,
  responsive mail grid, and responsive audit cards.
- Seeded canonical project documents through the backend database as real persisted documents,
  pages, chunks, and audit records. The source is project documentation, not synthetic UI data.
- Cleared a real stale queued job through the `/jobs/{id}/cancel` API so passive Health no longer
  reports an operational backlog degradation.

## TestSprite Instruction

Any rerun must reject demo/provisional success. The UI should pass only by exercising the real SPA,
real API state, real documents, real audit events, and controlled explicit degraded/configured
states.
