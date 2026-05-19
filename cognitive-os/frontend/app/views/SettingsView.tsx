"use client";

import { useEffect, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type {
  ActionCapabilityStatus,
  ActionRequestView,
  PublicConfig,
  ReadinessReport,
  Theme
} from "../lib/types";

export function SettingsView({
  client,
  apiBase,
  setApiBase,
  token,
  setToken,
  theme,
  setTheme
}: {
  client: ApiClient;
  apiBase: string;
  setApiBase: (value: string) => void;
  token: string;
  setToken: (value: string) => void;
  theme: Theme;
  setTheme: (value: Theme) => void;
}) {
  const config = usePolledFetch<PublicConfig>(client, "/config/public", 30000);
  const readiness = usePolledFetch<ReadinessReport>(
    client,
    "/system/readiness",
    60000
  );
  const capabilities = usePolledFetch<ActionCapabilityStatus[]>(
    client,
    "/actions/capabilities",
    30000
  );
  const actionRequests = usePolledFetch<ActionRequestView[]>(
    client,
    "/actions/requests?limit=5",
    10000
  );
  const [apiDraft, setApiDraft] = useState(apiBase);
  const [tokenDraft, setTokenDraft] = useState(token);
  const toast = useToast();

  useEffect(() => setApiDraft(apiBase), [apiBase]);
  useEffect(() => setTokenDraft(token), [token]);

  function commit() {
    setApiBase(apiDraft.trim() || "http://127.0.0.1:8000");
    setToken(tokenDraft.trim());
    toast.push("Config local aplicada.", "success");
  }

  return (
    <div className="grid-2">
      <section className="section stack">
        <h2>Conexión</h2>
        <label className="stack">
          <span className="muted small">API base</span>
          <input value={apiDraft} onChange={(event) => setApiDraft(event.target.value)} />
        </label>
        <label className="stack">
          <span className="muted small">JWT sin prefijo Bearer</span>
          <input
            value={tokenDraft}
            onChange={(event) => setTokenDraft(event.target.value)}
            type="password"
          />
        </label>
        <div className="row">
          <button className="primary" onClick={commit} type="button">
            Guardar
          </button>
          <button
            onClick={async () => {
              try {
                const text = await navigator.clipboard.readText();
                if (text) setTokenDraft(text);
              } catch (caught) {
                toast.push(errorMessage(caught), "error");
              }
            }}
            type="button"
          >
            Pegar desde portapapeles
          </button>
        </div>
        <h3>Tema</h3>
        <div className="row">
          <button
            className={theme === "dark" ? "primary" : ""}
            onClick={() => setTheme("dark")}
            type="button"
          >
            Oscuro
          </button>
          <button
            className={theme === "light" ? "primary" : ""}
            onClick={() => setTheme("light")}
            type="button"
          >
            Claro
          </button>
        </div>
      </section>

      {readiness.data && readiness.data.gaps.length > 0 && (
        <section className="section stack">
          <div className="section-head">
            <h2>Capacidades bloqueadas por <code>.env</code></h2>
            <span className="muted small">
              {readiness.data.target_capabilities_unlocked}/
              {readiness.data.target_capabilities_total} activas
            </span>
          </div>
          <p className="muted small">{readiness.data.summary}</p>
          <ol className="small" style={{ paddingLeft: "1.2rem", margin: 0 }}>
            {readiness.data.gaps.map((gap) => (
              <li key={gap.env_var} style={{ marginBottom: "0.4rem" }}>
                <code>{gap.env_var}</code>: <code>{gap.current_value}</code>
                {" → "}
                <code>{gap.suggested_value}</code>
                <br />
                <span className="muted">{gap.capability}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="section stack">
        <h2>Configuración del backend</h2>
        <p className="muted small">
          Solo lectura. Para cambiar estos flags, edita <code>.env</code> y reinicia API/worker.
        </p>
        {config.data ? (
          <div className="grid-2 small">
            <Item label="Entorno" value={config.data.environment} />
            <Item
              label="Perfil de operador"
              value={
                config.data.operator_profile === "dedicated_local"
                  ? "dedicated_local (sin fricción)"
                  : "strict (multi-tenant)"
              }
            />
            <Item
              label="auto_approve_reversibles"
              value={String(config.data.auto_approve_reversible_actions)}
            />
            <Item
              label="code_director_budget"
              value={config.data.code_director_budget_mode}
            />
            <Item
              label="tools_readonly_mode"
              value={String(config.data.tools_readonly_mode)}
            />
            <Item
              label="approval_for_external"
              value={String(config.data.require_human_approval_for_external_actions)}
            />
            <Item
              label="enable_email_send"
              value={String(config.data.enable_email_send)}
            />
            <Item
              label="enable_social_posting"
              value={String(config.data.enable_social_posting)}
            />
            <Item
              label="enable_browser_automation"
              value={String(config.data.enable_browser_automation)}
            />
            <Item
              label="enable_computer_actions"
              value={String(config.data.enable_computer_actions)}
            />
            <Item
              label="enable_openshell_sandbox"
              value={String(config.data.enable_openshell_sandbox)}
            />
            <Item
              label="enable_document_generation"
              value={String(config.data.enable_document_generation)}
            />
            <Item
              label="google_maps"
              value={`${config.data.enable_maps_routing ? "on" : "off"} · ${config.data.maps_default_travel_mode}`}
            />
            <Item
              label="google_calendar"
              value={`read ${config.data.enable_google_calendar} · write ${config.data.enable_google_calendar_write}`}
            />
            <Item
              label="google_drive"
              value={`read ${config.data.enable_google_drive} · write ${config.data.enable_google_drive_write} · ${config.data.google_drive_deliverables_folder_name}`}
            />
            <Item
              label="mail"
              value={`${config.data.mail_enabled ? "on" : "off"} · GoDaddy ${config.data.mail_godaddy_enabled ? "on" : "off"} · approval ${config.data.mail_require_approval_for_send}`}
            />
            <Item
              label="mail_timeouts"
              value={`${config.data.mail_imap_timeout_seconds}s IMAP · ${config.data.mail_smtp_timeout_seconds}s SMTP`}
            />
            <Item
              label="gmail"
              value={`read ${config.data.gmail_read_enabled} · send ${config.data.gmail_send_enabled}`}
            />
            <Item
              label="godaddy"
              value={`enabled ${config.data.godaddy_enabled} · dry_run ${config.data.godaddy_dns_dry_run_only}`}
            />
            <Item
              label="openharness"
              value={`${config.data.enable_openharness_research ? "on" : "off"} · ${config.data.openharness_toolkit_preset} · ${config.data.openharness_research_pipeline}`}
            />
            <Item label="research_store" value={config.data.research_persistence_backend} />
            <Item
              label="langsmith"
              value={`tracing ${config.data.langsmith_tracing} · admin ${config.data.langsmith_endpoints_require_admin}`}
            />
            <Item label="reranker" value={config.data.reranker_enabled ? "on" : "off"} />
            <Item label="reranker_model" value={config.data.reranker_model} />
            <Item
              label="web_search"
              value={
                config.data.web_search_enabled
                  ? config.data.web_search_providers.join(" + ") || "sin providers"
                  : "off"
              }
            />
            <Item
              label="embeddings"
              value={`${config.data.embeddings_provider} · ${config.data.embeddings_model} (${config.data.embeddings_dimension}d, pool ${config.data.embeddings_key_pool_size})`}
            />
            <Item
              label="primary_llm"
              value={`${config.data.primary_llm_provider} · ${config.data.primary_llm_model}`}
            />
            <Item
              label="deepagents_skills"
              value={config.data.deepagents_enable_skills ? "on" : "off"}
            />
            <Item
              label="deepagents_subagents"
              value={config.data.deepagents_enable_subagents ? "on" : "off"}
            />
            <Item
              label="deepagents_memory"
              value={config.data.deepagents_enable_memory ? "on" : "off"}
            />
            <Item
              label="memory_require_approval"
              value={String(config.data.deepagents_memory_require_approval)}
            />
          </div>
        ) : (
          <p className="muted small">Cargando…</p>
        )}
        <hr style={{ borderColor: "var(--line)", width: "100%" }} />
        <h3>Action Plane</h3>
        {capabilities.data ? (
          <div className="stack" style={{ gap: 8 }}>
            {capabilities.data.map((capability) => (
              <div
                key={capability.name}
                className="row"
                style={{
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: 12
                }}
              >
                <div className="stack" style={{ gap: 2 }}>
                  <strong>{capability.name}</strong>
                  <span className="muted small">{capability.summary}</span>
                  {capability.reasons.length > 0 && (
                    <code style={{ overflowWrap: "anywhere" }}>
                      {capability.reasons.join(" · ")}
                    </code>
                  )}
                </div>
                <span className={statusClass(capability.status)}>
                  {capability.status}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted small">Cargando capacidades…</p>
        )}
        <h3>Solicitudes recientes</h3>
        {actionRequests.error ? (
          <p className="muted small">{actionRequests.error}</p>
        ) : actionRequests.data ? (
          <div className="stack" style={{ gap: 8 }}>
            {actionRequests.data.length === 0 && (
              <p className="muted small">Sin solicitudes registradas.</p>
            )}
            {actionRequests.data.map((request) => (
              <div
                key={request.id}
                className="row"
                style={{
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: 12
                }}
              >
                <div className="stack" style={{ gap: 2 }}>
                  <strong>{request.action_type}</strong>
                  <span className="muted small">
                    creada {new Date(request.created_at).toLocaleString()}
                    {request.job_id ? ` · job ${request.job_id.slice(0, 8)}` : ""}
                    {request.approval_id ? ` · approval ${request.approval_id.slice(0, 8)}` : ""}
                  </span>
                  {request.error && (
                    <code style={{ overflowWrap: "anywhere" }}>{request.error}</code>
                  )}
                </div>
                <span className={statusClass(request.status)}>{request.status}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted small">Cargando solicitudes…</p>
        )}
        <hr style={{ borderColor: "var(--line)", width: "100%" }} />
        <h3>Observabilidad</h3>
        <p className="small">
          LangSmith dashboard:&nbsp;
          <a
            href="https://smith.langchain.com/o/-/projects"
            target="_blank"
            rel="noreferrer"
          >
            smith.langchain.com
          </a>
        </p>
        <p className="muted small">
          Las trazas se cargan en el proyecto <code>cognitive_os</code>. Para
          desactivarlo poné <code>LANGSMITH_TRACING=false</code> en <code>.env</code>.
        </p>
      </section>
    </div>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div className="stack" style={{ gap: 2 }}>
      <span className="muted small">{label}</span>
      <code style={{ overflowWrap: "anywhere" }}>{value}</code>
    </div>
  );
}
