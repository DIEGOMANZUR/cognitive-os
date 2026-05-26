# TestSprite Web Portal UI 24-Case Triage Fix Log

Date: 2026-05-26

## Result Received

UI read-only run: 24 cases total, 21 passed, 2 failed, 1 blocked.

## Finding 1 — Navigation and Shell Routing

Status: real app/testability bug, fixed.

Symptoms:

- Audit view showed `Sin eventos` during the run.
- The report could not prove all required views from that navigation case.
- Health showed an honest backend-unavailable/configured state, not a false green state.

Fixes:

- Audit now renders loading, explicit API errors, and empty state separately. It no longer hides a
  failed `/audit/events` request behind `Sin eventos`.
- Public API runtime check confirms `/audit/events?limit=1` returns at least one real event.
- Public API runtime check confirms `/documents?limit=1` returns real persisted documents.
- Public API runtime check confirms `/health/dashboard` returns `configured` with 18 components.

## Finding 2 — Responsive Layout

Status: real responsive robustness bug, fixed.

Symptoms:

- TestSprite could not observe tablet/mobile mode after viewport changes.
- The shell remained in desktop presentation during repeated waits.

Fixes:

- Mobile header and bottom navigation are now always rendered and controlled by CSS media queries.
- Default desktop sidebar is hidden by CSS under `920px` unless the drawer is open.
- Viewport detection now uses `matchMedia`, `window.resize`, `visualViewport.resize`, and a lightweight
  polling fallback so environments that do not fire the normal media-query event still update.

## Finding 3 — Hotkey 3

Status: real product mismatch, fixed.

Symptoms:

- TestSprite expected hotkey `3` to open DeepAgents.
- The app mapped `3` to Documents, while DeepAgents had no visible hotkey.

Fixes:

- Sidebar now labels DeepAgents with hotkey `3`.
- Global hotkey handler now maps `3` to DeepAgents.
- The UI upload plan now states explicitly: `1` Dashboard, `2` Chat, `3` DeepAgents, `9` Health.

## Runtime Preparation

- Frontend rebuilt with `npm run build`.
- Cognitive OS runtime restarted with `cognitive-os.sh restart`.
- Public frontend is reachable and contains no `cogos_qa` or `qaMode` markers.
- Kimi WebBridge is running and extension-connected, but no TestSprite tabs were visible in the
  current Kimi session.

## Next Rerun

Run a focal rerun for the 3 affected cases first:

- Navigation and Shell Routing: stable shell while navigating sections.
- Responsive Layout: desktop/tablet/mobile.
- Navigation and Shell Routing: keyboard shortcuts.

If those pass, run `Rerun All` for the full UI suite.
