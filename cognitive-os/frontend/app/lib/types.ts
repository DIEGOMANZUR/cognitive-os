export type Tab =
  | "dashboard"
  | "chat"
  | "agents"
  | "skills"
  | "memory"
  | "assist"
  | "googleOps"
  | "mail"
  | "documents"
  | "documentAnalysis"
  | "jobs"
  | "approvals"
  | "sandbox"
  | "research"
  | "codeDirector"
  | "langsmith"
  | "audit"
  | "health"
  | "configuration"
  | "settings";

export type ChatResponse = {
  thread_id: string;
  message: string;
  route: string;
  pending_human_review?: Record<string, unknown> | null;
};

export type JobResponse = {
  id: string;
  job_type: string;
  status: string;
  progress: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type JobEventResponse = {
  id: string;
  job_id: string;
  event_type: string;
  status: string;
  message: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type JobCancelResponse = {
  id: string;
  status: string;
  celery_task_id: string | null;
  celery_revoke_requested: boolean;
  celery_revoke_error: string | null;
};

export type ApprovalResponse = {
  id: string;
  requested_action: string;
  args_redacted: Record<string, unknown>;
  status: string;
  requested_by: string | null;
  approver_user_id: string | null;
  created_at: string;
  decided_at: string | null;
};

export type MailAccount = {
  id: string;
  label: string;
  kind: string;
  email_address: string;
  monitor_folders: string[];
  send_capable: boolean;
  is_default_sender: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type PersonalTaskStatus = "pending" | "in_progress" | "done" | "cancelled";

export type PersonalTask = {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  status: PersonalTaskStatus;
  priority: number;
  due_at: string | null;
  remind_at: string | null;
  completed_at: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type PersonalNote = {
  id: string;
  user_id: string;
  title: string;
  body_markdown: string;
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type MailStatus = {
  enabled: boolean;
  default_sender: string;
  require_approval_for_send: boolean;
  allow_explicit_send: boolean;
  background_sync_enabled: boolean;
  digest_enabled: boolean;
  digest_hours_local: string[];
  digest_timezone: string;
  digest_max_messages: number;
  gmail_monitor_labels: string[];
  accounts: MailAccount[];
  reasons: string[];
};

export type MailClassification = "important" | "normal" | "spam" | "promo" | "unknown";

export type MailMessageStatus =
  | "new"
  | "reply_proposed"
  | "pending_send"
  | "sent"
  | "ignored"
  | "failed";

export type MailMessage = {
  id: string;
  account_id: string;
  account_label: string | null;
  folder: string;
  uid: string;
  sender: string;
  recipients: string[];
  subject: string | null;
  snippet: string | null;
  received_at: string | null;
  classification: MailClassification;
  importance_score: number;
  proposed_reply_text: string | null;
  proposed_reply_rationale: string | null;
  status: MailMessageStatus;
  sent_at: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type MailSendResult = {
  message: MailMessage;
  send_log_id: string;
  sent: boolean;
};

export type MailSyncResult = {
  accounts_checked: number;
  fetched: number;
  inserted: number;
  skipped_existing: number;
  errors: string[];
};

export type MailSyncDispatchResponse = {
  task_id: string;
  status: string;
};

export type MailDigestMessage = {
  id: string;
  account_label: string | null;
  folder: string;
  sender: string;
  subject: string | null;
  snippet: string | null;
  received_at: string | null;
  classification: MailClassification;
  importance_score: number;
  proposed_reply_text: string | null;
  proposed_reply_rationale: string | null;
};

export type MailDigestResult = {
  generated_at: string;
  total_considered: number;
  included_count: number;
  excluded_spam_count: number;
  important_count: number;
  summary_text: string;
  proposed_replies_text: string;
  messages: MailDigestMessage[];
  important_messages: MailDigestMessage[];
  artifact_markdown_path: string | null;
  artifact_json_path: string | null;
  warnings: string[];
};

export type DeepAgentSkill = {
  name: string;
  description: string;
  version: string;
  risk_level: string;
  allowed_tools: string[];
};

export type DeepAgentMemoryProposal = {
  proposal_id: string;
  proposed_by_agent: string;
  scope: string;
  reason: string;
  proposed_content: string;
  sensitivity?: string;
  source_task_id?: string | null;
  status: string;
  approval_id?: string | null;
  created_at?: string;
  decided_at?: string | null;
  metadata?: Record<string, unknown>;
  // Fase 78: surfaced from `metadata_json` so the UI can render the
  // recipe section without spelunking through nested JSON.
  kind?: string;
  confidence?: number | null;
  payload?: Record<string, unknown>;
};

export type DocumentAnalysisMode =
  | "evidence_matrix"
  | "timeline"
  | "contradictions"
  | "full_report"
  | "legal_draft_support"
  | "case_summary";

export type DocumentAnalysisOutputFormat = "json" | "markdown" | "csv" | "docx";

export type DocumentAnalysisRunResponse = {
  status: string;
  task_id: string;
  job_id: string | null;
  result?: Record<string, unknown> | null;
};

export type DocumentAnalysisStatusResponse = {
  task_id: string;
  status: string;
  generated_files: string[];
  human_review_required: boolean;
  warnings: string[];
};

export type ComponentHealth = {
  name: string;
  status: string;
  detail: string | null;
  latency_ms: number | null;
  metadata: Record<string, unknown>;
};

export type HealthDashboardResponse = {
  status: string;
  checked_at: string;
  components: ComponentHealth[];
};

export type IngestResponse = {
  job_id: string;
  status: string;
};

export type DocumentSummary = {
  id: string;
  title: string | null;
  source_path: string;
  sha256: string;
  status: string;
  page_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
};

export type AuditEvent = {
  id: string;
  actor_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type KnowledgeStats = {
  documents: number;
  pages: number;
  chunks: number;
  jobs_running: number;
  jobs_completed: number;
  jobs_failed: number;
  approvals_pending: number;
};

export type MCPServerStatus = {
  name: string;
  transport: string;
  target: string;
  connected: boolean;
  tools_count: number;
  error?: string | null;
};

export type MCPInventory = {
  enabled: boolean;
  declared_count: number;
  servers: MCPServerStatus[];
};

export type ReadinessGap = {
  env_var: string;
  current_value: string;
  suggested_value: string;
  capability: string;
  severity: "info" | "suggestion" | "warning";
};

export type ReadinessReport = {
  operator_profile: string;
  local_autonomy_mode: string;
  summary: string;
  target_capabilities_unlocked: number;
  target_capabilities_total: number;
  gaps: ReadinessGap[];
};

export type PublicConfig = {
  environment: string;
  operator_profile: "strict" | "dedicated_local";
  local_autonomy_mode: "guarded" | "full";
  auto_approve_reversible_actions: boolean;
  code_director_budget_mode: "soft" | "hard";
  web_search_enabled: boolean;
  tools_readonly_mode: boolean;
  require_human_approval_for_external_actions: boolean;
  enable_browser_automation: boolean;
  enable_computer_actions: boolean;
  enable_email_send: boolean;
  enable_social_posting: boolean;
  enable_document_generation: boolean;
  enable_research_orchestrator: boolean;
  research_persistence_backend: string;
  enable_openharness_research: boolean;
  openharness_research_pipeline: string;
  openharness_toolkit_preset: string;
  openharness_workspace_mode: string;
  openharness_web_tools: boolean;
  enable_openshell_sandbox: boolean;
  enable_personal_assistant_api: boolean;
  enable_personal_reminder_delivery: boolean;
  enable_maps_routing: boolean;
  maps_default_travel_mode: string;
  enable_google_calendar: boolean;
  enable_google_calendar_write: boolean;
  enable_google_drive: boolean;
  enable_google_drive_write: boolean;
  google_drive_upload_max_bytes: number;
  google_drive_deliverables_folder_name: string;
  telegram_enabled: boolean;
  telegram_gmail_digest_enabled: boolean;
  langsmith_tracing: boolean;
  langsmith_endpoints_require_admin: boolean;
  browser_automation_provider: string;
  browser_headless_default: boolean;
  browser_allow_headed: boolean;
  browser_allow_vision: boolean;
  browser_allowed_domains_count: number;
  computer_allowed_roots_count: number;
  computer_organize_dry_run_only: boolean;
  document_asset_roots_count: number;
  gmail_read_enabled: boolean;
  gmail_send_enabled: boolean;
  mail_enabled: boolean;
  mail_godaddy_enabled: boolean;
  mail_require_approval_for_send: boolean;
  mail_background_sync_enabled: boolean;
  mail_poll_interval_seconds: number;
  mail_fetch_max_per_folder: number;
  mail_imap_timeout_seconds: number;
  mail_smtp_timeout_seconds: number;
  mail_gmail_label: string;
  godaddy_enabled: boolean;
  godaddy_dns_dry_run_only: boolean;
  godaddy_allow_production_writes: boolean;
  godaddy_allowed_domains_count: number;
  reranker_enabled: boolean;
  reranker_model: string;
  deepagents_enable_skills: boolean;
  deepagents_enable_subagents: boolean;
  deepagents_enable_memory: boolean;
  deepagents_memory_require_approval: boolean;
  embeddings_provider: string;
  embeddings_model: string;
  embeddings_dimension: number;
  embeddings_key_pool_size: number;
  primary_llm_provider: string;
  primary_llm_model: string;
  web_search_providers: string[];
};

export type ActionCapabilityStatus = {
  name: string;
  status: "disabled" | "blocked" | "configured" | "ready";
  summary: string;
  requires_approval: boolean;
  dry_run_only: boolean;
  reasons: string[];
  metadata: Record<string, unknown>;
};

export type ActionRequestStatus =
  | "previewed"
  | "blocked"
  | "pending_approval"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "rejected"
  | "cancelled";

export type ActionType =
  | "computer_organize"
  | "browser_navigation"
  | "gmail_query"
  | "godaddy_dns_change"
  | "document_generate"
  | "browser_preview"
  | "browser_interactive"
  | "calendar_create_event"
  | "drive_upload_file"
  | "drive_ensure_folder"
  | "drive_organize_files";

export type ActionRequestView = {
  id: string;
  action_type: ActionType;
  status: ActionRequestStatus;
  requested_by: string | null;
  approval_id: string | null;
  job_id: string | null;
  payload_redacted: Record<string, unknown>;
  preview: Record<string, unknown>;
  result: Record<string, unknown>;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type ActionDispatchResponse = {
  action_request: ActionRequestView;
  dispatched: boolean;
  reason: string | null;
};

export type MapsStatus = {
  status: "disabled" | "blocked" | "ready";
  reason: string | null;
  default_travel_mode: "driving" | "walking" | "bicycling" | "transit";
};

export type RouteStep = {
  instruction: string;
  distance_meters: number;
};

export type RoutePlan = {
  origin: string;
  destination: string;
  travel_mode: "driving" | "walking" | "bicycling" | "transit";
  distance_meters: number;
  duration_seconds: number;
  distance_text: string;
  duration_text: string;
  static_duration_seconds: number | null;
  static_duration_text: string | null;
  traffic_delay_seconds: number | null;
  traffic_delay_text: string | null;
  traffic_severity: "unknown" | "none" | "light" | "moderate" | "heavy";
  traffic_aware: boolean;
  departure_time: string | null;
  arrival_time: string | null;
  route_advice: string;
  google_maps_url: string;
  route_labels: string[];
  alternative_count: number;
  steps: RouteStep[];
  intermediates: string[];
};

export type CalendarStatus = {
  status: "disabled" | "blocked" | "ready";
  reason: string | null;
  calendar_id: string;
  write_enabled: boolean;
  missing_scopes?: string[];
};

export type CalendarEvent = {
  event_id: string;
  summary: string;
  start: string;
  end: string;
  all_day: boolean;
  location: string | null;
  html_link: string | null;
};

export type FreeBusySlot = {
  start: string;
  end: string;
};

export type FreeBusyCalendar = {
  calendar_id: string;
  busy: FreeBusySlot[];
  errors: string[];
};

export type FreeBusyResult = {
  time_min: string;
  time_max: string;
  calendars: FreeBusyCalendar[];
  busy_count: number;
};

export type DriveStatus = {
  status: "disabled" | "blocked" | "ready";
  reason: string | null;
  write_enabled: boolean;
  upload_max_bytes: number;
  deliverables_folder_name: string;
  missing_scopes?: string[];
};

export type DriveFile = {
  file_id: string;
  name: string;
  mime_type: string;
  modified_time: string | null;
  size_bytes: number | null;
  web_view_link: string | null;
  owner: string | null;
  is_folder: boolean;
  parent_ids: string[];
};

export type DriveFolderPreview = {
  status: "preview" | "blocked" | "ready" | "created";
  reason: string | null;
  folder_name: string;
  folder: DriveFile | null;
};

export type DriveOrganizeOperation = {
  file: DriveFile;
  target_folder_name: string;
  target_folder_id: string | null;
  removed_parent_ids: string[];
  status: "planned" | "moved" | "skipped";
  reason: string | null;
};

export type DriveOrganizePreview = {
  status: "preview" | "blocked" | "completed";
  reason: string | null;
  query: string;
  target_folder_name: string;
  dry_run: boolean;
  operation_count: number;
  operations: DriveOrganizeOperation[];
};

export type StreamEvent = {
  event: string;
  thread_id?: string;
  node?: string;
  payload?: unknown;
  message?: string;
  route?: string;
  pending_human_review?: Record<string, unknown> | null;
  detail?: string;
};

export type Theme = "dark" | "light";

export type ToastTone = "info" | "success" | "warning" | "error";
export type Toast = {
  id: number;
  tone: ToastTone;
  message: string;
};

export type ThreadMessage = {
  type: string;
  content: string;
};

export type ThreadResponse = {
  thread_id: string;
  values: Record<string, unknown> & {
    messages?: ThreadMessage[];
    active_route?: string;
    pending_human_review?: Record<string, unknown> | null;
    agent_result?: Record<string, unknown> | null;
  };
};

export type ThreadSummary = {
  thread_id: string;
  last_active_at: string | null;
  last_route: string | null;
  last_message_preview: string | null;
};

export type DocumentChunk = {
  chunk_id: string;
  chunk_index: number;
  page_start: number;
  page_end: number;
  sha256: string;
  text: string;
};

export type SkillDetail = {
  name: string;
  description: string;
  version: string;
  risk_level: string;
  allowed_tools: string[];
  path: string;
  enabled: boolean;
  content: string;
};

export type AgentPolicy = {
  allow_local_rag: boolean;
  allow_neo4j_read: boolean;
  allow_web: boolean;
  allow_workspace_write: boolean;
  allow_shell: boolean;
  allow_browser: boolean;
  allow_email: boolean;
  allow_social_posting: boolean;
  allow_delete: boolean;
};

export type AgentStats = {
  total_jobs: number;
  running: number;
  completed: number;
  failed: number;
  last_active_at: string | null;
};

export type AgentSummary = {
  name: string;
  kind: string;
  description: string;
  job_type: string;
  policy: AgentPolicy;
  tools: string[];
  skills: string[];
  memory_enabled: boolean;
  requires_approval_for_drafts: boolean;
  web_search_enabled: boolean;
  stats: AgentStats;
};

export type LangSmithStatus = {
  enabled: boolean;
  project: string;
  endpoint: string;
  detail: string | null;
};

export type LangSmithProject = {
  id: string;
  name: string;
  run_count: number | null;
};

export type LangSmithRun = {
  id: string;
  name: string | null;
  run_type: string | null;
  status: string | null;
  start_time: string | null;
  end_time: string | null;
  latency_ms: number | null;
  error: string | null;
  total_tokens: number | null;
  parent_run_id: string | null;
};

export type LangSmithRunDetail = LangSmithRun & {
  inputs: Record<string, unknown> | null;
  outputs: Record<string, unknown> | null;
  extra: Record<string, unknown> | null;
  tags: string[] | null;
};

// ---- Research Orchestrator ----------------------------------------------

export type ResearchRunStatus =
  | "queued"
  | "planning"
  | "researching"
  | "synthesizing"
  | "scoring"
  | "completed"
  | "cancelled"
  | "failed"
  | "blocked";

export type ResearchRunRequestPayload = {
  query: string;
  time_budget_seconds?: number;
  max_subtasks?: number;
  web_allowed?: boolean;
  user_id?: string | null;
};

export type ResearchSubtaskView = {
  subtask_id: string;
  query: string;
  rationale?: string | null;
};

export type ResearchCitationView = {
  doc_id?: string | null;
  chunk_id?: string | null;
  url?: string | null;
  title?: string | null;
  snippet?: string | null;
};

export type ResearchSubtaskResultView = {
  subtask_id: string;
  status: "ok" | "failed" | "timeout" | "cancelled" | "blocked";
  answer?: string;
  findings?: string[];
  citations?: ResearchCitationView[];
  uncertainty_notes?: string[];
  duration_ms?: number;
};

export type ResearchSynthesisView = {
  answer: string;
  findings: string[];
  citations: ResearchCitationView[];
  uncertainty_notes: string[];
  used_sources: string[];
};

export type ResearchScoreView = {
  score: number;
  rubric: Record<string, number>;
  reasons: string[];
};

export type ResearchRunView = {
  run_id: string;
  status: ResearchRunStatus;
  request: ResearchRunRequestPayload;
  subtasks: ResearchSubtaskView[];
  results: ResearchSubtaskResultView[];
  synthesis: ResearchSynthesisView | null;
  score: ResearchScoreView | null;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
};

export type ResearchEventKind =
  | "run_started"
  | "plan_ready"
  | "subtask_started"
  | "subtask_finished"
  | "synthesis_ready"
  | "score_ready"
  | "run_completed"
  | "run_cancelled"
  | "run_failed"
  | "run_blocked"
  | "snapshot"
  | "done"
  | "error";

export type ResearchEvent = {
  event: ResearchEventKind;
  run_id: string;
  timestamp?: string;
  payload?: Record<string, unknown>;
  detail?: string;
};

// ---- workflow.v1 contract -----------------------------------------------

export type WorkflowActionType =
  | "computer_organize"
  | "godaddy_dns_change"
  | "document_generate"
  | "browser_preview"
  | "browser_interactive"
  | "calendar_create_event"
  | "drive_upload_file"
  | "drive_ensure_folder"
  | "drive_organize_files";

export type WorkflowSource = {
  exported_at: string;
  exported_by: string | null;
  source_action_request_id: string | null;
};

export type WorkflowDocument = {
  workflow_version: "1.0";
  action_type: WorkflowActionType;
  payload: Record<string, unknown>;
  preview?: Record<string, unknown> | null;
  source?: WorkflowSource | null;
  notes?: string | null;
  metadata?: Record<string, unknown>;
};

export type WorkflowImportResult = {
  action_request: {
    id: string;
    action_type: string;
    status: string;
  };
  dry_run: boolean;
  notes: string | null;
};

// ---- Code Director ----

export type CodeAdapterChoice =
  | "claude_code"
  | "codex"
  | "kimi"
  | "deepagent";

export type CodeSubtaskSpec = {
  subtask_id: string;
  title: string;
  description: string;
  role: "planner" | "coder" | "reviewer" | "tester";
  adapter: CodeAdapterChoice;
  model: string | null;
  depends_on: string[];
  expected_paths: string[];
};

export type CodeBuildPlan = {
  workspace_dir: string;
  subtasks: CodeSubtaskSpec[];
  estimated_runtime_minutes: number;
  estimated_calls: number;
  estimated_cost_usd: number | null;
  rationale: string;
};

export type CodeBuildCreateResponse = {
  job_id: string;
  approval_id: string;
  build_id: string;
  plan: CodeBuildPlan;
  detail: string;
};

export type CodeBuildStatusResponse = {
  job_id: string;
  build_id: string | null;
  status: string;
  plan: CodeBuildPlan | null;
  result: Record<string, unknown> | null;
};

export type CodeBuildEvent = {
  event: string;
  job_id?: string;
  status?: string;
  message?: string | null;
  payload?: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  detail?: string;
};
