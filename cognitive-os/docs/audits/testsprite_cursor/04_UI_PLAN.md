# 04 — UI SPA Full Plan

- Generated: `2026-05-26 02:46 UTC`
- Suite: **A — UI SPA FULL**
- Source JSON: `testsprite_tests/testsprite_frontend_test_plan.json`
- TestSprite MCP: plan generated/loaded in Cursor session

## Target

- Frontend: `https://cognitive.doctormanzur.com`
- Auth: seed `localStorage` (`cogos.token`, `cogos.api`) before navigation
- SPA: only navigate `/`; switch tabs via sidebar, hotkeys, Ctrl+K

## Cases

### TC001 — Stay signed in after saving a local JWT
- Category: `Global Shell`
- Priority: `High`
- Description: Verifies the operator can paste a local token, reload the app, and remain authenticated across sessions.
- Steps:
  - [action] Navigate to /
  - [action] Open settings
  - [action] Paste a valid local JWT into the token field
  - [action] Save the token
  - [action] Reload the app
  - [assertion] Verify the app remains connected after reload
  - [assertion] Verify the saved token state is still available

### TC002 — Bootstrap a local session from Settings
- Category: `Bootstrap local JWT`
- Priority: `High`
- Description: The operator can mint a local JWT in Settings and the session becomes connected for continued use.
- Steps:
  - [action] Navigate to /
  - [action] Open the settings view
  - [action] Mint a local JWT
  - [assertion] Verify the session is connected

### TC003 — Persist a pasted JWT across reload
- Category: `Bootstrap local JWT`
- Priority: `High`
- Description: The operator can paste a JWT, save it locally, reload the app, and remain connected afterward.
- Steps:
  - [action] Navigate to /
  - [action] Open the settings view
  - [action] Paste a valid JWT into the token field
  - [action] Save the token locally
  - [action] Reload the app
  - [assertion] Verify the session remains connected after reload

### TC004 — Send a chat message and receive a reply
- Category: `Chat / Threads`
- Priority: `High`
- Description: Verifies the operator can open chat, submit a message, and see a response appear in the conversation thread.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the chat view
  - [action] Type a message into the chat input
  - [action] Submit the message
  - [assertion] Verify the conversation shows the submitted message and a reply
  - [assertion] Verify the thread remains visible with the exchanged messages

### TC005 — Navigate the cockpit with global tabs
- Category: `Global Shell`
- Priority: `High`
- Description: Verifies the operator can use the cockpit's tab navigation to move between core views from the app root.
- Steps:
  - [action] Navigate to /
  - [action] Open the tab navigation
  - [action] Switch to the chat view
  - [action] Switch to the documents view
  - [action] Switch to the research view
  - [assertion] Verify the selected tab changes with each navigation step
  - [assertion] Verify each target view becomes visible

### TC006 — Review health status from the cockpit
- Category: `Health Dashboard`
- Priority: `High`
- Description: The operator can open the Health view and review the readiness state of core platform components.
- Steps:
  - [action] Navigate to /
  - [action] Open the health view
  - [assertion] Verify component status information is displayed
  - [assertion] Verify readiness indicators are displayed

### TC007 — Review health and readiness information
- Category: `Global Shell`
- Priority: `High`
- Description: Verifies the operator can inspect system health and readiness indicators from the cockpit.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the health view
  - [action] Review the health dashboard
  - [action] Review the configuration and readiness section
  - [assertion] Verify health status information is displayed
  - [assertion] Verify readiness or configuration visibility is present

### TC008 — Open a persisted chat thread and review its history
- Category: `Chat / Threads`
- Priority: `High`
- Description: Verifies the operator can view the thread list, open an existing thread, and see previously saved messages.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the chat view
  - [action] Review the available threads
  - [action] Open a conversation thread
  - [assertion] Verify the selected thread's message history is displayed
  - [assertion] Verify previous conversation content is visible

### TC009 — Run a live health verification
- Category: `Health Dashboard`
- Priority: `High`
- Description: The operator can trigger a live health probe and see the health view update with probe results.
- Steps:
  - [action] Navigate to /
  - [action] Open the health view
  - [action] Trigger a live verification probe
  - [assertion] Verify updated probe results are displayed
  - [assertion] Verify live verification feedback is visible

### TC010 — Start a document analysis run
- Category: `Document Analysis Agent`
- Priority: `High`
- Description: Verifies the operator can launch a document analysis workflow and see progress until analysis artifacts appear.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the document analysis view
  - [action] Start an analysis run
  - [assertion] Verify progress updates are displayed
  - [assertion] Verify generated analysis artifacts appear

### TC011 — Start and review a research run
- Category: `Research / DeepAgents / OpenHarness`
- Priority: `High`
- Description: Verifies that an operator can open Research, start a run, and see streamed progress and final citations/results.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the research view
  - [action] Start a research run
  - [assertion] Verify run progress updates are displayed
  - [assertion] Verify synthesized results with citations are displayed

### TC012 — View document statistics in the documents area
- Category: `Documents + Ingestion`
- Priority: `High`
- Description: Verifies the operator can open documents and see indexed content counts and ingestion status information.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the documents view
  - [assertion] Verify document statistics are displayed
  - [assertion] Verify ingestion state or indexed content counts are visible

### TC013 — Review readiness in the configuration view
- Category: `Configuration / Readiness`
- Priority: `High`
- Description: Verify that an operator can open Configuration and see readiness, public configuration, and unlocked capability information.
- Steps:
  - [action] Navigate to /login
  - [action] Fill in the username field with {{LOGIN_USER}}
  - [action] Fill in the password field with {{LOGIN_PASSWORD}}
  - [action] Submit the login form
  - [action] Click the configuration view tab
  - [assertion] Verify readiness information is displayed
  - [assertion] Verify unlocked capability information is displayed

### TC014 — Review queued jobs and open job details
- Category: `Jobs + Approvals + Action Requests`
- Priority: `High`
- Description: Verifies that an operator can inspect jobs, open a job entry, and see its current status and progress.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the jobs view
  - [action] Open a job in the list
  - [assertion] Verify job details are displayed
  - [assertion] Verify job status and progress are displayed

### TC015 — Open a view from the command palette
- Category: `Configuration / Readiness`
- Priority: `High`
- Description: Verify that an operator can use the command palette to jump from the cockpit to another view.
- Steps:
  - [action] Navigate to /login
  - [action] Fill in the username field with {{LOGIN_USER}}
  - [action] Fill in the password field with {{LOGIN_PASSWORD}}
  - [action] Submit the login form
  - [action] Open the command palette
  - [action] Search for the documents view
  - [action] Select the matching result
  - [assertion] Verify the documents view is displayed

### TC016 — Open a document record from the document list
- Category: `Documents + Ingestion`
- Priority: `High`
- Description: Verifies the operator can browse the document list and open a record to inspect its details.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the documents view
  - [action] Review the document list
  - [action] Open a document record
  - [assertion] Verify the document detail view is displayed
  - [assertion] Verify record details are visible

### TC017 — Use the command palette to reach chat
- Category: `Configuration / Readiness`
- Priority: `High`
- Description: Verify that an operator can open the command palette and navigate directly to Chat.
- Steps:
  - [action] Navigate to /login
  - [action] Fill in the username field with {{LOGIN_USER}}
  - [action] Fill in the password field with {{LOGIN_PASSWORD}}
  - [action] Submit the login form
  - [action] Open the command palette
  - [action] Search for the chat view
  - [action] Select the matching result
  - [assertion] Verify the chat view is displayed

### TC018 — Approve a pending item and review dispatch progress
- Category: `Jobs + Approvals + Action Requests`
- Priority: `High`
- Description: Verifies that an operator can approve a pending approval and then see the associated dispatch progress update.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the approvals view
  - [action] Open a pending approval item
  - [action] Approve the item
  - [assertion] Verify dispatch progress is displayed
  - [assertion] Verify the approval no longer appears as pending

### TC019 — Open the code director run workflow
- Category: `Code Director`
- Priority: `High`
- Description: Verifies the operator can open Code Director and start a new run from the cockpit.
- Steps:
  - [action] Navigate to /
  - [action] Click the Code Director view
  - [action] Start a run
  - [assertion] Verify a run progress view is displayed

### TC020 — Review completed document analysis results
- Category: `Document Analysis Agent`
- Priority: `High`
- Description: Verifies the operator can inspect a finished analysis and see citations, quality scoring, and findings.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the document analysis view
  - [action] Open a completed analysis
  - [assertion] Verify citations are displayed
  - [assertion] Verify a quality score and findings are visible

### TC021 — Use the command palette to reach research
- Category: `Configuration / Readiness`
- Priority: `High`
- Description: Verify that an operator can open the command palette and navigate directly to Research.
- Steps:
  - [action] Navigate to /login
  - [action] Fill in the username field with {{LOGIN_USER}}
  - [action] Fill in the password field with {{LOGIN_PASSWORD}}
  - [action] Submit the login form
  - [action] Open the command palette
  - [action] Search for the research view
  - [action] Select the matching result
  - [assertion] Verify the research view is displayed

### TC022 — Jump to core views from the command palette
- Category: `Global Shell`
- Priority: `Medium`
- Description: Verifies the operator can use the command palette to navigate directly to chat, documents, and research views.
- Steps:
  - [action] Navigate to /
  - [action] Open the command palette
  - [action] Select the chat destination
  - [action] Open the command palette again
  - [action] Select the documents destination
  - [action] Open the command palette again
  - [action] Select the research destination
  - [assertion] Verify the requested view becomes visible after each selection

### TC023 — Review code director run outcome
- Category: `Code Director`
- Priority: `Medium`
- Description: Verifies the operator can open a started Code Director run and review its final outcome and artifacts.
- Steps:
  - [action] Navigate to /
  - [action] Click the Code Director view
  - [action] Start a run
  - [action] Open the created run
  - [assertion] Verify the run outcome is displayed
  - [assertion] Verify run artifacts are displayed

### TC024 — Sync mail in read-only mode and review classified messages
- Category: `Mail (Read-Only)`
- Priority: `Medium`
- Description: Verifies that an operator can trigger a mail sync, then review classified messages and proposals without sending mail.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the mail view
  - [action] Trigger a read-only mail sync
  - [assertion] Verify synchronized mail items are displayed
  - [assertion] Verify classified messages and proposals are displayed

### TC025 — Switch between cockpit views from the root
- Category: `Configuration / Readiness`
- Priority: `Medium`
- Description: Verify that an operator can move between major cockpit views from the app root after logging in.
- Steps:
  - [action] Navigate to /login
  - [action] Fill in the username field with {{LOGIN_USER}}
  - [action] Fill in the password field with {{LOGIN_PASSWORD}}
  - [action] Submit the login form
  - [action] Click the documents view tab
  - [action] Click the health view tab
  - [action] Click the configuration view tab
  - [assertion] Verify the configuration view is displayed

### TC026 — Review drive search results
- Category: `Google Ops (Maps/Calendar/Drive)`
- Priority: `Medium`
- Description: Verifies the operator can search drive content from Google Ops and see matching items with their metadata.
- Steps:
  - [action] Navigate to /
  - [action] Click the Google Ops view
  - [action] Search drive content using a common query
  - [assertion] Verify drive search results are displayed
  - [assertion] Verify result metadata is displayed

### TC027 — Review a proposed mail reply without sending
- Category: `Mail (Read-Only)`
- Priority: `Medium`
- Description: Verifies that an operator can open a message in mail and inspect the suggested reply text while remaining in read-only mode.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the mail view
  - [action] Open a message
  - [assertion] Verify message details are displayed
  - [assertion] Verify proposed reply text is displayed

### TC028 — Approve or reject a memory proposal
- Category: `Memory & Skills`
- Priority: `Medium`
- Description: Verifies the operator can review a memory proposal and complete an approval or rejection decision.
- Steps:
  - [action] Navigate to /
  - [action] Click the memory view
  - [action] Open a proposal for review
  - [action] Approve or reject the proposal
  - [assertion] Verify the proposal decision is reflected in the learning state

### TC029 — Open Research from the command palette
- Category: `Research / DeepAgents / OpenHarness`
- Priority: `Medium`
- Description: Verifies that the operator can use the command palette to jump into Research from the cockpit root.
- Steps:
  - [action] Navigate to /
  - [action] Open the command palette
  - [action] Choose the research view
  - [assertion] Verify the research view is displayed
  - [assertion] Verify research controls are available

### TC030 — Review maps and calendar readiness
- Category: `Google Ops (Maps/Calendar/Drive)`
- Priority: `Medium`
- Description: Verifies the operator can open Google Ops and confirm the read-only maps and calendar status information needed for operational review.
- Steps:
  - [action] Navigate to /
  - [action] Click the Google Ops view
  - [assertion] Verify maps status information is displayed
  - [assertion] Verify calendar status information is displayed

### TC031 — Keep the active tab after reloading
- Category: `Configuration / Readiness`
- Priority: `Medium`
- Description: Verify that an operator's selected cockpit tab persists after a page reload.
- Steps:
  - [action] Navigate to /login
  - [action] Fill in the username field with {{LOGIN_USER}}
  - [action] Fill in the password field with {{LOGIN_PASSWORD}}
  - [action] Submit the login form
  - [action] Click the configuration view tab
  - [action] Reload the page
  - [assertion] Verify the configuration view remains displayed

### TC032 — Generate a mail digest preview
- Category: `Mail (Read-Only)`
- Priority: `Medium`
- Description: Verifies that an operator can generate a digest preview in mail and inspect the suggested summary text.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the mail view
  - [action] Generate a digest preview
  - [assertion] Verify a digest preview is displayed
  - [assertion] Verify suggested summary text is displayed

### TC033 — Review MCP inventory in Settings
- Category: `MCP Inventory`
- Priority: `Medium`
- Description: The operator can open Settings and inspect the MCP server inventory with connection and tool information.
- Steps:
  - [action] Navigate to /
  - [action] Open the settings view
  - [assertion] Verify MCP server inventory is displayed
  - [assertion] Verify connection status and tool counts are displayed

### TC034 — See blocked capability information
- Category: `Configuration / Readiness`
- Priority: `Medium`
- Description: Verify that an operator can review the blocked or unavailable capability information from the readiness area.
- Steps:
  - [action] Navigate to /login
  - [action] Fill in the username field with {{LOGIN_USER}}
  - [action] Fill in the password field with {{LOGIN_PASSWORD}}
  - [action] Submit the login form
  - [action] Click the configuration view tab
  - [assertion] Verify blocked capability information is displayed

### TC035 — Review action request state in Jobs
- Category: `Jobs + Approvals + Action Requests`
- Priority: `Medium`
- Description: Verifies that an operator can open the jobs view and inspect action request state and idempotency-related status information.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the jobs view
  - [action] Open the action requests section
  - [assertion] Verify action requests are displayed
  - [assertion] Verify request state and status details are displayed

### TC036 — Review memory proposals and warnings
- Category: `Memory & Skills`
- Priority: `Medium`
- Description: Verifies the operator can open Memory and inspect learning proposals and warnings for review.
- Steps:
  - [action] Navigate to /
  - [action] Click the memory view
  - [assertion] Verify learning proposals are displayed
  - [assertion] Verify warnings are displayed

### TC037 — Review skill scorecards
- Category: `Memory & Skills`
- Priority: `Medium`
- Description: Verifies the operator can open Skills and inspect the current scorecard and promotion status.
- Steps:
  - [action] Navigate to /
  - [action] Click the skills view
  - [assertion] Verify tool scorecard information is displayed
  - [assertion] Verify skill promotion status is displayed

### TC038 — Reject an invalid pasted JWT
- Category: `Bootstrap local JWT`
- Priority: `Low`
- Description: The operator sees an invalid-token validation state when attempting to save a malformed JWT in Settings.
- Steps:
  - [action] Navigate to /
  - [action] Open the settings view
  - [action] Paste an invalid JWT into the token field
  - [action] Save the token locally
  - [assertion] Verify a token validation error is visible

### TC039 — Use the drive search empty state
- Category: `Google Ops (Maps/Calendar/Drive)`
- Priority: `Low`
- Description: Verifies the operator can search Google Ops drive content with a query that returns no matches and see a clear empty state.
- Steps:
  - [action] Navigate to /
  - [action] Click the Google Ops view
  - [action] Search drive content using a rare query
  - [assertion] Verify an empty state message is displayed

### TC040 — See empty-state guidance in mail when no items are available
- Category: `Mail (Read-Only)`
- Priority: `Low`
- Description: Verifies that the mail view shows an empty-state message when there are no messages to review.
- Steps:
  - [action] Navigate to /
  - [action] Switch to the mail view
  - [assertion] Verify an empty-state message is displayed
