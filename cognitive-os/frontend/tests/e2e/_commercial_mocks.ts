import type { Page, Route } from "@playwright/test";

const API_BASE = "http://127.0.0.1:8000";
const NOW = "2026-05-22T12:00:00Z";

type MockOptions = {
  healthStatus?: "ok" | "configured" | "degraded";
  malformedLists?: boolean;
  scenario?:
    | "empty"
    | "degraded"
    | "populated"
    | "pending_approval"
    | "failed_job"
    | "retryable_job"
    | "mail_digest_disabled"
    | "mail_digest_read_only"
    | "malformed_api_state"
    | "mobile_friendly_state";
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function health(status: "ok" | "configured" | "degraded") {
  const primaryStatus = status === "ok" ? "ok" : status === "configured" ? "configured" : "degraded";
  return {
    status,
    checked_at: new Date(NOW).toISOString(),
    components: [
      { name: "postgres", status: "ok", latency_ms: 4, detail: null, metadata: {} },
      { name: "redis", status: "ok", latency_ms: 3, detail: null, metadata: {} },
      {
        name: "primary_llm",
        status: primaryStatus,
        latency_ms: 12,
        detail:
          primaryStatus === "configured"
            ? "Provider is configured; live call skipped to avoid spend."
            : null,
        metadata: {},
      },
      {
        name: "operational_backlog",
        status: "ok",
        detail: "No stale operational backlog.",
        metadata: {
          approvals_pending: 0,
          approvals_stale: 0,
          jobs_stale: 0,
          action_requests_stuck: 0,
          beat_lag_minutes: 1,
        },
      },
      { name: "checkpointer", status: "ok", latency_ms: 1, detail: null, metadata: { backend: "postgres" } },
      { name: "langsmith", status: "configured", latency_ms: null, detail: "Tracing configured.", metadata: { project: "cognitive_os" } },
    ],
  };
}

const publicConfig = {
  environment: "local",
  operator_profile: "dedicated_local",
  local_autonomy_mode: "full",
  auto_approve_reversible_actions: true,
  code_director_budget_mode: "soft",
  web_search_enabled: true,
  tools_readonly_mode: false,
  require_human_approval_for_external_actions: false,
  enable_browser_automation: true,
  enable_computer_actions: true,
  enable_email_send: false,
  enable_social_posting: false,
  enable_document_generation: true,
  enable_research_orchestrator: true,
  research_persistence_backend: "postgres",
  enable_openharness_research: false,
  openharness_research_pipeline: "standard",
  openharness_toolkit_preset: "minimal",
  openharness_workspace_mode: "local",
  openharness_web_tools: false,
  enable_openshell_sandbox: false,
  enable_personal_assistant_api: true,
  enable_personal_reminder_delivery: false,
  enable_maps_routing: true,
  maps_default_travel_mode: "driving",
  enable_google_calendar: true,
  enable_google_calendar_write: true,
  enable_google_drive: true,
  enable_google_drive_write: true,
  google_drive_upload_max_bytes: 10485760,
  google_drive_deliverables_folder_name: "Cognitive OS Deliverables",
  telegram_enabled: true,
  telegram_gmail_digest_enabled: true,
  langsmith_tracing: true,
  langsmith_endpoints_require_admin: false,
  browser_automation_provider: "kimi_webbridge",
  browser_headless_default: false,
  browser_allow_headed: true,
  browser_allow_vision: true,
  browser_allowed_domains_count: 4,
  computer_allowed_roots_count: 2,
  computer_organize_dry_run_only: false,
  document_asset_roots_count: 2,
  gmail_read_enabled: true,
  gmail_send_enabled: false,
  mail_enabled: true,
  mail_godaddy_enabled: true,
  mail_require_approval_for_send: true,
  mail_background_sync_enabled: false,
  mail_poll_interval_seconds: 900,
  mail_fetch_max_per_folder: 50,
  mail_imap_timeout_seconds: 20,
  mail_smtp_timeout_seconds: 20,
  mail_gmail_label: "TODOS",
  godaddy_enabled: true,
  godaddy_dns_dry_run_only: true,
  godaddy_allow_production_writes: false,
  godaddy_allowed_domains_count: 1,
  reranker_enabled: true,
  reranker_model: "BAAI/bge-reranker-base",
  deepagents_enable_skills: true,
  deepagents_enable_subagents: true,
  deepagents_enable_memory: true,
  deepagents_memory_require_approval: true,
  failure_postmortem_auto_promote_enabled: true,
  embeddings_provider: "openai",
  embeddings_model: "text-embedding-3-large",
  embeddings_dimension: 3072,
  embeddings_key_pool_size: 1,
  primary_llm_provider: "openai",
  primary_llm_model: "gpt-5.5",
  web_search_providers: ["brave", "tavily"],
};

const capabilities = [
  {
    name: "browser_preview",
    status: "ready",
    summary: "Preview web read-only disponible para dedicated_local/full.",
    requires_approval: false,
    dry_run_only: false,
    reasons: [],
    metadata: { provider: "kimi_webbridge" },
  },
  {
    name: "browser_interactive",
    status: "ready",
    summary: "Kimi WebBridge/Edge real habilitable en el perfil local dedicado.",
    requires_approval: false,
    dry_run_only: false,
    reasons: [],
    metadata: { provider: "kimi_webbridge" },
  },
  {
    name: "computer_organize",
    status: "ready",
    summary: "Filesystem local dentro de raices permitidas.",
    requires_approval: false,
    dry_run_only: false,
    reasons: [],
    metadata: { roots: 2 },
  },
  {
    name: "mail",
    status: "configured",
    summary: "Mail normal read-only: digest, clasificacion y propuestas de texto.",
    requires_approval: true,
    dry_run_only: true,
    reasons: ["send disabled by contract"],
    metadata: { drafts: false, send: false },
  },
  {
    name: "godaddy_dns",
    status: "configured",
    summary: "DNS real bloqueado; dry-run por defecto.",
    requires_approval: true,
    dry_run_only: true,
    reasons: ["GODADDY_DNS_DRY_RUN_ONLY=true"],
    metadata: {},
  },
  {
    name: "kimi_webbridge",
    status: "ready",
    summary: "Puente local disponible cuando el proceso esta levantado.",
    requires_approval: false,
    dry_run_only: false,
    reasons: [],
    metadata: {},
  },
];

export async function seedMockAuth(page: Page) {
  await page.addInitScript((apiBase) => {
    window.localStorage.setItem("cogos.token", JSON.stringify("mock-commercial-jwt"));
    window.localStorage.setItem("cogos.token.source", JSON.stringify("manual"));
    window.localStorage.setItem("cogos.api", JSON.stringify(apiBase));
  }, API_BASE);
}

export async function installCommercialApiMocks(page: Page, options: MockOptions = {}) {
  const scenario = options.scenario ?? "pending_approval";
  const malformed = options.malformedLists || scenario === "malformed_api_state";
  const healthStatus = options.healthStatus ?? (scenario === "degraded" ? "degraded" : "ok");
  const listPayload: unknown = malformed ? {} : [];
  const mailDisabled = scenario === "mail_digest_disabled";
  const emptyState = scenario === "empty";

  await page.route(`${API_BASE}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === "/health") return json(route, { status: "ok" });
    if (path === "/health/dashboard") return json(route, health(healthStatus));
    if (path === "/health/verify") return json(route, health("ok"));
    if (path === "/config/public") {
      return json(route, publicConfig);
    }
    if (path === "/system/info") {
      return json(route, {
        service: "cognitive-os",
        environment: "local",
        git_commit: "mock",
        operator_profile: "dedicated_local",
      });
    }
    if (path === "/system/readiness") {
      return json(route, {
        operator_profile: "dedicated_local",
        local_autonomy_mode: "full",
        summary: "14/14 capacidades listas",
        target_capabilities_unlocked: 14,
        target_capabilities_total: 14,
        gaps: [],
      });
    }
    if (path === "/system/mcp") {
      return json(route, { enabled: true, declared_count: 0, servers: [] });
    }
    if (path === "/knowledge/stats") {
      return json(route, {
        documents: 0,
        pages: 0,
        chunks: 0,
        jobs_running: 0,
        jobs_completed: 0,
        jobs_failed: 0,
        approvals_pending: 0,
      });
    }
    if (path === "/actions/capabilities") {
      return json(route, capabilities);
    }
    if (path === "/mail/status") {
      return json(route, {
        enabled: !mailDisabled,
        default_sender: "diego@example.test",
        require_approval_for_send: true,
        allow_explicit_send: false,
        background_sync_enabled: false,
        digest_enabled: !mailDisabled,
        digest_hours_local: ["10", "20"],
        digest_timezone: "America/Santiago",
        digest_max_messages: 50,
        gmail_monitor_labels: ["TODOS", "SPAM"],
        accounts: [],
        reasons: mailDisabled ? ["MAIL_ENABLED=false fixture"] : [],
      });
    }
    if (path === "/mail/sync/dispatch") {
      return json(route, { task_id: "mail-sync-mock", status: "dispatched" });
    }
    if (path === "/mail/digest/preview") {
      if (mailDisabled) {
        return json(route, { detail: "MAIL_ENABLED=false fixture" }, 503);
      }
      return json(route, {
        generated_at: new Date(NOW).toISOString(),
        total_considered: 1,
        included_count: 1,
        excluded_spam_count: 0,
        important_count: 1,
        summary_text: "Resumen mock.",
        proposed_replies_text: "Respuesta propuesta mock.",
        messages: [],
        important_messages: [],
        artifact_markdown_path: null,
        artifact_json_path: null,
        warnings: [],
      });
    }
    if (path === "/jobs") {
      if (malformed) return json(route, listPayload);
      if (emptyState) return json(route, []);
      const status = scenario === "failed_job" || scenario === "retryable_job" ? "failed" : "running";
      const progress = status === "failed" ? 100 : 50;
      const jobType = scenario === "failed_job" ? "document_analysis" : "action_request";
      return json(route, [
        {
          id: "11111111-1111-4111-8111-111111111111",
          job_type: jobType,
          status,
          progress,
          metadata_json: { source: "mock", retryable: scenario === "retryable_job" },
          created_at: NOW,
          updated_at: "2026-05-22T12:01:00Z",
        },
      ]);
    }
    if (path.endsWith("/events")) {
      if (emptyState) return json(route, []);
      return json(route, [
        {
          id: "evt-1",
          job_id: "11111111-1111-4111-8111-111111111111",
          event_type:
            scenario === "retryable_job"
              ? "fixture_retry_available"
              : scenario === "failed_job"
                ? "fixture_failed"
                : "action_request_dispatch_submitted",
          status: scenario === "failed_job" || scenario === "retryable_job" ? "failed" : "ok",
          message:
            scenario === "retryable_job"
              ? "Fixture failure is retryable; rerun is available."
              : scenario === "failed_job"
                ? "Fixture job failed with visible diagnostics."
                : "Dispatch submitted",
          created_at: "2026-05-22T12:01:00Z",
          metadata_json: { retryable: scenario === "retryable_job" },
        },
      ]);
    }
    if (path === "/approvals") {
      if (emptyState || scenario !== "pending_approval") return json(route, []);
      return json(route, [
        {
          id: "22222222-2222-4222-8222-222222222222",
          requested_action: "execute_action_request:33333333-3333-4333-8333-333333333333",
          status: "pending",
          requester_user_id: "operator",
          requested_by: "operator",
          approver_user_id: null,
          args_redacted: { action_type: "computer_organize" },
          created_at: NOW,
          decided_at: null,
        },
      ]);
    }
    if (path.includes("/approvals/") && path.endsWith("/approve")) {
      return json(route, {
        id: "22222222-2222-4222-8222-222222222222",
        requested_action: "execute_action_request:33333333-3333-4333-8333-333333333333",
        status: "approved",
        requester_user_id: "operator",
        requested_by: "operator",
        approver_user_id: "operator",
        args_redacted: {},
        created_at: NOW,
        decided_at: "2026-05-22T12:02:00Z",
      });
    }
    if (path.includes("/actions/requests/") && path.endsWith("/dispatch")) {
      return json(route, { dispatched: true, task_id: "dispatch-mock", reason: null });
    }
    if (path === "/actions/requests") return json(route, listPayload);
    if (path === "/sandbox/openshell/status") return json(route, { enabled: false, status: "disabled" });
    if (path.endsWith("/status")) return json(route, { status: "ready", reason: null });
    if (path === "/audit/events") return json(route, listPayload);
    if (path === "/deepagents/learning/tool-scorecard") return json(route, listPayload);
    if (path.startsWith("/deepagents/learning/")) return json(route, listPayload);
    if (path.startsWith("/deepagents/") || path.startsWith("/assist/") || path.startsWith("/documents") || path.startsWith("/research/runs") || path.startsWith("/langsmith") || path.startsWith("/agents") || path.startsWith("/skills")) {
      return json(route, listPayload);
    }
    return json(route, request.method() === "GET" ? listPayload : {});
  });
}
