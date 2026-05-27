# Cognitive OS — Frontend (UI) PRD for TestSprite

## 1. Product Identity

- **Name:** Cognitive OS
- **Type:** Local-first single-operator AI cognitive workstation
- **Frontend:** Next.js 16 App Router + React 19, **single-page application** with tab-based navigation
- **Public URL under test:** `https://cognitive.doctormanzur.com`
- **Backend public URL:** `https://cognitive-api.doctormanzur.com`

## 2. CRITICAL ARCHITECTURAL FACTS (read these before testing)

### 2.1 The app is a SINGLE-PAGE APPLICATION

There are **only two routes that exist server-side**:

- `/` (root) — the entire application UI
- `/manifest.webmanifest` — PWA manifest
- (and `/_next/*` for static assets and `/icons/*` for icons)

**Do NOT navigate to** `/dashboard`, `/health`, `/search`, `/settings`, `/mail`, `/chat`, `/agents`, etc. — those paths return **404 by design**.

All "views" are React tabs rendered conditionally inside `/`. Switch tabs by:

- Clicking sidebar items, OR
- Pressing hotkeys: `1` (Dashboard), `2` (Chat), `3` (DeepAgents), `4` (Document Analysis), `5` (Jobs), `6` (Approvals), `7` (LangSmith), `8` (Audit), `9` (Health), OR
- Pressing `Ctrl+K` to open the Command Palette and selecting a view.

### 2.2 Authentication is JWT in URL fragment or localStorage (no login form)

There is no email/password form. Preferred public-web auth is:

```text
https://cognitive.doctormanzur.com/#cogos_token=<JWT provided in extra instructions>
```

On load, the app persists the fragment value as `localStorage.cogos.token` and removes the token from the URL. The public frontend host automatically resolves the API base to `https://cognitive-api.doctormanzur.com`.

If your test framework seeds storage before navigation, use:

```js
localStorage.setItem('cogos.token', '<JWT provided in extra instructions>');
localStorage.setItem('cogos.api', 'https://cognitive-api.doctormanzur.com');
```

Then reload `/`. The stable connected state is the sidebar + contextual header + `<main data-cogos-active-tab="...">` with authenticated data. Without a JWT, protected backend calls return 401 and tabs show honest empty/error states. This is correct behavior and is **not** a bug.

### 2.3 Backend dependency

Every meaningful UI test depends on the backend at `cognitive-api.doctormanzur.com` answering. If the public backend returns 5xx, **the UI is not buggy** — report the failure as a backend issue.

## 3. Inventory of tabs (the entire navigation surface)

| Tab id              | Label              | Hotkey | Backend deps                                  |
|---------------------|--------------------|--------|-----------------------------------------------|
| `dashboard`         | Dashboard          | 1      | `/system/info`, `/system/readiness`, KPIs     |
| `chat`              | Chat               | 2      | `/chat/*`, `/threads/*`                       |
| `agents`            | DeepAgents         | 3      | `/deepagents/*`                               |
| `skills`            | Skills             |        | (read-only catalog)                           |
| `memory`            | Memoria            |        | `/knowledge`                                  |
| `assist`            | Asistente          |        | `/assist/*`                                   |
| `mail`              | Mail               |        | `/mail/*` (READ-ONLY for this test window)    |
| `documents`         | Documentos         |        | `/documents/*`                                |
| `documentAnalysis`  | Document Analysis  | 4      | `/document-analysis/*`                        |
| `jobs`              | Jobs               | 5      | `/jobs/*`                                     |
| `approvals`         | Aprobaciones       | 6      | `/approvals/*`                                |
| `googleOps`         | Google Ops         |        | OAuth proxies (read-only)                     |
| `research`          | Research           |        | `/research/*`                                 |
| `codeDirector`      | Code Director      |        | `/code-director/*`                            |
| `sandbox`           | Sandbox            |        | `/sandbox/*`                                  |
| `langsmith`         | LangSmith          | 7      | `/langsmith/*`                                |
| `audit`             | Audit log          | 8      | `/audit`                                      |
| `health`            | Health             | 9      | `/health`, `/system/info`, `/system/readiness`|
| `configuration`     | Sistema            |        | `/config`                                     |
| `settings`          | Conexión           |        | (local — token/api base configuration)        |

## 4. Critical user journeys (priority order)

For each, switch tab via hotkey or click sidebar item — **never** by changing the URL.

### J1 — Bootstrap

1. Open `/`. Confirm app shell renders (sidebar, contextual header, content area, `<main data-cogos-active-tab>`).
2. Authenticate via `#cogos_token=<JWT>` or seeded localStorage.
3. Reload `/`. Confirm authenticated data loads or protected views show explicit, non-crashing states.

### J2 — Health tab

1. Press hotkey `9` or click sidebar "Health".
2. Confirm cards render for: backend health, Postgres, Redis, Weaviate, Neo4j, Celery workers.
3. All should be green.

### J3 — Dashboard

1. Hotkey `1`.
2. Confirm KPI tiles render (counts, latencies).
3. No spinners stuck after 5 s.

### J4 — Chat

1. Hotkey `2`.
2. Type a short message: "hello, status please".
3. Send. Wait for response from the chat backend.
4. Verify message appears in thread view.

### J5 — DeepAgents

1. Hotkey `3`.
2. Confirm DeepAgents fleet loads or shows a commercial empty/error/loading state.
3. Open an agent card if available and verify detail content renders.

### J5b — Documents

1. Click sidebar "Documentos" or use `Ctrl+K`.
2. Confirm list of indexed documents loads (or "no documents" empty state).
3. Click the first document. Verify detail view renders.

### J6 — Search via Command Palette

1. Press `Ctrl+K` (or `Cmd+K`).
2. Confirm palette opens, type any tab name, press Enter, confirm navigation.

### J7 — Settings persistence

1. Click sidebar "Sistema" or "Conexión".
2. Toggle the theme (dark/light) if available, reload, confirm theme persisted.

### J8 — Audit

1. Hotkey `8`.
2. Confirm audit log table renders with at least one row (system boot or current session).

### J9 — Approvals

1. Hotkey `6`.
2. Confirm pending approvals list loads (may be empty — empty state is acceptable).

### J10 — Notifications panel

1. Use any visible notification entry point if present.
2. Confirm panel opens, lists notifications or shows empty state.

## 5. Out-of-scope — DO NOT trigger any of these

The following are gated by safety flags that are **currently false / dry-run** for this QA window:

| Forbidden action                                        | Where it lives                            |
|--------------------------------------------------------|-------------------------------------------|
| Send real email (SMTP)                                  | `mail` tab → any "Send" / "Approve send"  |
| Approve outbound message                                | `mail` tab, `approvals` tab               |
| DNS write against GoDaddy                               | `googleOps` / config                      |
| Browser automation that drives external sites           | `agents`, `sandbox`                       |
| Destructive filesystem actions (rm / overwrite)         | `sandbox`, `codeDirector`                 |
| Toggle ANY safety flag in the Configuration tab         | `configuration` tab                       |
| Rotate JWT secret or admin user IDs                     | `configuration` tab                       |

**Expected behavior when a forbidden flow is attempted:**

- Backend returns 4xx (Forbidden / `feature_disabled`) or a "dry-run preview" payload.
- It must NOT return 5xx.
- It must NOT execute the external side effect.

Tests that probe these guards (verifying the block fires) are encouraged. Tests that try to *bypass* them are out of scope.

## 6. UI quality acceptance criteria

- No unhandled JavaScript exceptions on any tab switch.
- No "Failed to load chunk" / hydration errors.
- All tabs reach a terminal state (data loaded OR empty state OR error toast) within 10 s.
- No mixed-content warnings (the whole app must be HTTPS).
- No fetches to `localhost:*` from the public origin.
- No CORS errors.
- Focus traps don't break (Command Palette, drawer and modal controls remain keyboard-accessible).
- `Ctrl+K` palette is keyboard-navigable.

## 7. Known cosmetic items (NOT bugs)

- The "Conexión" tab input shows `http://127.0.0.1:8000` as **placeholder** and as the **default value** before localStorage is seeded. Once `cogos.api` is set, the actual URL used is the public backend. This is the documented zero-friction default for the operator running locally and does not affect the public test session once the JWT seed is applied.
- A page reload may briefly show the dashboard skeleton — acceptable.

## 8. Reporting failures back to the operator

When you find a real bug, include:

- Tab/route triggered
- Hotkey used (or palette command)
- Screenshot at failure
- Network requests in flight (URLs + status)
- Console errors

The operator will fix and ask for a re-run.
