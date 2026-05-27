# 06 — E2E Integrated Plan

> **Actualización 2026-05-26:** este archivo es evidencia histórica de auditoría. El flujo vigente ya no usa TopBar: la autenticación pública es por `#cogos_token` o `localStorage.cogos.token`, la API se resuelve automáticamente por host y el shell estable se valida con `<main data-cogos-active-tab="...">`. Las menciones a TopBar debajo se conservan solo como contexto histórico.

- Generated: `2026-05-26 02:46 UTC`
- Suite: **C — E2E INTEGRATED**
- Source: manual blueprint (TestSprite MCP has no dedicated E2E plan tool)

## Target

- UI: `https://cognitive.doctormanzur.com`
- API: `https://cognitive-api.doctormanzur.com`
- Auth: localStorage seed + Bearer JWT for API probes

## Cases

### TE2E001 — Public UI auth seed + Connected TopBar
- Priority: `High`
- Description: Seed localStorage on https://cognitive.doctormanzur.com/, reload, verify Connected.

### TE2E002 — Health tab reflects public backend
- Priority: `High`
- Description: Open Health tab; verify dashboard cards match GET /health/dashboard.

### TE2E003 — Jobs tab lists jobs from API
- Priority: `High`
- Description: Jobs tab shows list or honest empty state; no 401 after seed.

### TE2E004 — Approvals tab read-only list
- Priority: `High`
- Description: Approvals tab loads pending items or empty state.

### TE2E005 — Chat roundtrip or controlled failure
- Priority: `High`
- Description: Send short message; accept LLM latency or actionable degraded UI.

### TE2E006 — Documents list/detail or empty
- Priority: `Medium`
- Description: Documents tab reaches terminal state <=10s.

### TE2E007 — Document Analysis controlled start
- Priority: `Medium`
- Description: Start safe analysis mode or verify disabled/degraded banner.

### TE2E008 — Research controlled start
- Priority: `Medium`
- Description: Do not run long research unless budget allows; verify UI guard.

### TE2E009 — Mail read-only surface
- Priority: `High`
- Description: Mail tab has no send/draft; messages read-only or empty.

### TE2E010 — Action Plane preview/request guard
- Priority: `High`
- Description: Preview/request flows stop before side effect in dedicated_local/full.

### TE2E011 — MCP status in System/Settings
- Priority: `Medium`
- Description: MCP inventory renders degraded/disabled honestly.

### TE2E012 — Code Director plan-only
- Priority: `Medium`
- Description: Plan visible; no destructive execution.

### TE2E013 — Zero-friction dedicated_local/full
- Priority: `High`
- Description: No redundant approval friction for reversible local actions.

### TE2E014 — No localhost fetch from public origin
- Priority: `High`
- Description: Network panel: no fetch to localhost/127.0.0.1 after seed.

### TE2E015 — No CORS/mixed-content
- Priority: `High`
- Description: Console free of CORS/mixed-content on core tabs.
