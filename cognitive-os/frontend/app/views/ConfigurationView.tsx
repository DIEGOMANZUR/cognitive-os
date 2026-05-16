"use client";

import { useMemo } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { HealthDashboardResponse, KnowledgeStats, PublicConfig } from "../lib/types";

const GROUPS: Array<{
  title: string;
  description: string;
  fields: Array<{
    label: string;
    extract: (config: PublicConfig) => string;
    danger?: (config: PublicConfig) => boolean;
  }>;
}> = [
  {
    title: "Entorno y seguridad",
    description: "Modo de ejecución y compuertas humanas.",
    fields: [
      { label: "ENVIRONMENT", extract: (c) => c.environment },
      {
        label: "TOOLS_READONLY_MODE",
        extract: (c) => String(c.tools_readonly_mode),
        danger: (c) => !c.tools_readonly_mode
      },
      {
        label: "REQUIRE_HUMAN_APPROVAL_FOR_EXTERNAL_ACTIONS",
        extract: (c) => String(c.require_human_approval_for_external_actions),
        danger: (c) => !c.require_human_approval_for_external_actions
      },
      { label: "ENABLE_EMAIL_SEND", extract: (c) => String(c.enable_email_send) },
      {
        label: "ENABLE_SOCIAL_POSTING",
        extract: (c) => String(c.enable_social_posting)
      }
    ]
  },
  {
    title: "Action Plane",
    description: "Acciones externas y guardrails visibles sin exponer secretos.",
    fields: [
      {
        label: "ENABLE_BROWSER_AUTOMATION",
        extract: (c) => String(c.enable_browser_automation)
      },
      {
        label: "BROWSER_PROVIDER · HEADLESS",
        extract: (c) => `${c.browser_automation_provider} · ${c.browser_headless_default}`
      },
      {
        label: "BROWSER_ALLOW_HEADED · VISION",
        extract: (c) => `${c.browser_allow_headed} · ${c.browser_allow_vision}`,
        danger: (c) => c.browser_allow_headed || c.browser_allow_vision
      },
      {
        label: "BROWSER_ALLOWED_DOMAINS",
        extract: (c) => String(c.browser_allowed_domains_count)
      },
      {
        label: "ENABLE_COMPUTER_ACTIONS",
        extract: (c) => String(c.enable_computer_actions)
      },
      {
        label: "COMPUTER_ROOTS · DRY_RUN",
        extract: (c) => `${c.computer_allowed_roots_count} · ${c.computer_organize_dry_run_only}`,
        danger: (c) => c.enable_computer_actions && !c.computer_organize_dry_run_only
      },
      {
        label: "ENABLE_DOCUMENT_GENERATION",
        extract: (c) => String(c.enable_document_generation)
      },
      {
        label: "DOCUMENT_ASSET_ROOTS",
        extract: (c) => String(c.document_asset_roots_count)
      }
    ]
  },
  {
    title: "Mail y DNS",
    description: "Correo personal, Gmail read-only y GoDaddy bajo aprobación.",
    fields: [
      { label: "MAIL_ENABLED", extract: (c) => String(c.mail_enabled) },
      { label: "MAIL_GODADDY_ENABLED", extract: (c) => String(c.mail_godaddy_enabled) },
      {
        label: "MAIL_REQUIRE_APPROVAL_FOR_SEND",
        extract: (c) => String(c.mail_require_approval_for_send),
        danger: (c) => !c.mail_require_approval_for_send
      },
      {
        label: "MAIL_POLL · FETCH_LIMIT",
        extract: (c) => `${c.mail_poll_interval_seconds}s · ${c.mail_fetch_max_per_folder}`
      },
      {
        label: "MAIL_IMAP_TIMEOUT · SMTP_TIMEOUT",
        extract: (c) => `${c.mail_imap_timeout_seconds}s · ${c.mail_smtp_timeout_seconds}s`
      },
      { label: "MAIL_GMAIL_LABEL", extract: (c) => c.mail_gmail_label },
      { label: "GMAIL_READ_ENABLED", extract: (c) => String(c.gmail_read_enabled) },
      {
        label: "GMAIL_SEND_ENABLED",
        extract: (c) => String(c.gmail_send_enabled),
        danger: (c) => c.gmail_send_enabled
      },
      { label: "GODADDY_ENABLED", extract: (c) => String(c.godaddy_enabled) },
      {
        label: "GODADDY_DRY_RUN · PROD_WRITES",
        extract: (c) => `${c.godaddy_dns_dry_run_only} · ${c.godaddy_allow_production_writes}`,
        danger: (c) => !c.godaddy_dns_dry_run_only || c.godaddy_allow_production_writes
      },
      {
        label: "GODADDY_ALLOWED_DOMAINS",
        extract: (c) => String(c.godaddy_allowed_domains_count)
      }
    ]
  },
  {
    title: "Google personal",
    description: "Maps, Calendar y Drive sin exponer claves ni tokens.",
    fields: [
      { label: "ENABLE_MAPS_ROUTING", extract: (c) => String(c.enable_maps_routing) },
      { label: "MAPS_DEFAULT_TRAVEL_MODE", extract: (c) => c.maps_default_travel_mode },
      { label: "ENABLE_GOOGLE_CALENDAR", extract: (c) => String(c.enable_google_calendar) },
      {
        label: "ENABLE_GOOGLE_CALENDAR_WRITE",
        extract: (c) => String(c.enable_google_calendar_write),
        danger: (c) => c.enable_google_calendar_write
      },
      { label: "ENABLE_GOOGLE_DRIVE", extract: (c) => String(c.enable_google_drive) },
      {
        label: "ENABLE_GOOGLE_DRIVE_WRITE",
        extract: (c) => String(c.enable_google_drive_write),
        danger: (c) => c.enable_google_drive_write
      },
      {
        label: "GOOGLE_DRIVE_UPLOAD_MAX_BYTES",
        extract: (c) => String(c.google_drive_upload_max_bytes)
      },
      {
        label: "GOOGLE_DRIVE_DELIVERABLES_FOLDER_NAME",
        extract: (c) => c.google_drive_deliverables_folder_name
      }
    ]
  },
  {
    title: "Modelos y embeddings",
    description: "Proveedores de LLM y vectores en uso ahora mismo.",
    fields: [
      {
        label: "PRIMARY_LLM_PROVIDER · MODEL",
        extract: (c) => `${c.primary_llm_provider} · ${c.primary_llm_model}`
      },
      {
        label: "EMBEDDINGS_PROVIDER · MODEL",
        extract: (c) =>
          `${c.embeddings_provider} · ${c.embeddings_model} (${c.embeddings_dimension}d)`
      },
      {
        label: "EMBEDDINGS_KEY_POOL_SIZE",
        extract: (c) => String(c.embeddings_key_pool_size)
      },
      { label: "RERANKER", extract: (c) => (c.reranker_enabled ? "on" : "off") },
      { label: "RERANKER_MODEL", extract: (c) => c.reranker_model }
    ]
  },
  {
    title: "Research Orchestrator y OpenHarness",
    description: "Modo de investigación profunda, presupuestos y fusión opcional.",
    fields: [
      {
        label: "ENABLE_RESEARCH_ORCHESTRATOR",
        extract: (c) => String(c.enable_research_orchestrator)
      },
      {
        label: "RESEARCH_PERSISTENCE_BACKEND",
        extract: (c) => c.research_persistence_backend,
        danger: (c) => c.environment === "production" && c.research_persistence_backend !== "postgres"
      },
      {
        label: "ENABLE_OPENHARNESS_RESEARCH",
        extract: (c) => String(c.enable_openharness_research)
      },
      {
        label: "OPENHARNESS_PIPELINE",
        extract: (c) => c.openharness_research_pipeline
      },
      {
        label: "OPENHARNESS_PRESET",
        extract: (c) => c.openharness_toolkit_preset,
        danger: (c) => c.enable_openharness_research && c.openharness_toolkit_preset !== "minimal"
      },
      {
        label: "OPENHARNESS_WORKSPACE_MODE",
        extract: (c) => c.openharness_workspace_mode
      },
      {
        label: "OPENHARNESS_WEB_TOOLS",
        extract: (c) => String(c.openharness_web_tools)
      }
    ]
  },
  {
    title: "Búsqueda web",
    description: "Multi-proveedor con dedup por URL canónica.",
    fields: [
      {
        label: "WEB_SEARCH_ENABLED",
        extract: (c) => String(c.web_search_enabled)
      },
      {
        label: "Providers configurados",
        extract: (c) =>
          c.web_search_providers.length ? c.web_search_providers.join(", ") : "—"
      }
    ]
  },
  {
    title: "DeepAgents",
    description: "Skills y memoria persistente con aprobación humana.",
    fields: [
      {
        label: "DEEPAGENTS_ENABLE_SKILLS",
        extract: (c) => String(c.deepagents_enable_skills)
      },
      {
        label: "DEEPAGENTS_ENABLE_MEMORY",
        extract: (c) => String(c.deepagents_enable_memory)
      },
      {
        label: "DEEPAGENTS_MEMORY_REQUIRE_APPROVAL",
        extract: (c) => String(c.deepagents_memory_require_approval),
        danger: (c) => !c.deepagents_memory_require_approval
      }
    ]
  },
  {
    title: "Asistente y canales",
    description: "APIs personales, recordatorios y Telegram.",
    fields: [
      {
        label: "ENABLE_PERSONAL_ASSISTANT_API",
        extract: (c) => String(c.enable_personal_assistant_api)
      },
      {
        label: "ENABLE_PERSONAL_REMINDER_DELIVERY",
        extract: (c) => String(c.enable_personal_reminder_delivery)
      },
      { label: "TELEGRAM_ENABLED", extract: (c) => String(c.telegram_enabled) },
      {
        label: "TELEGRAM_GMAIL_DIGEST_ENABLED",
        extract: (c) => String(c.telegram_gmail_digest_enabled)
      }
    ]
  },
  {
    title: "Observabilidad",
    description: "Trazas externas y control de acceso a LangSmith.",
    fields: [
      { label: "LANGSMITH_TRACING", extract: (c) => String(c.langsmith_tracing) },
      {
        label: "LANGSMITH_ENDPOINTS_REQUIRE_ADMIN",
        extract: (c) => String(c.langsmith_endpoints_require_admin),
        danger: (c) => c.environment === "production" && !c.langsmith_endpoints_require_admin
      }
    ]
  },
  {
    title: "Sandbox",
    description: "Ejecución de código en aislamiento. Bloqueado por defecto.",
    fields: [
      {
        label: "ENABLE_OPENSHELL_SANDBOX",
        extract: (c) => String(c.enable_openshell_sandbox)
      }
    ]
  }
];

export function ConfigurationView({ client }: { client: ApiClient }) {
  const config = usePolledFetch<PublicConfig>(client, "/config/public", 30000);
  const stats = usePolledFetch<KnowledgeStats>(client, "/knowledge/stats", 12000);
  const health = usePolledFetch<HealthDashboardResponse>(client, "/health/dashboard", 15000);
  const toast = useToast();

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      toast.push("Copiado.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }

  const componentMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const c of health.data?.components ?? []) map[c.name] = c.status;
    return map;
  }, [health.data]);

  return (
    <div className="stack">
      <section className="section">
        <div className="section-head">
          <h2>Configuración del sistema</h2>
          <span className="muted small">Solo lectura · sourced from `.env`</span>
        </div>
        <p className="muted small">
          Para cambiar una flag editá <code>.env</code> y reiniciá la API y los workers Celery.
          Las claves de API quedan en <code>SecretStr</code> y no se exponen acá.
        </p>
        {config.error && <p className="badge danger">{config.error}</p>}
      </section>

      <div className="grid">
        <article className="metric-card">
          <span className="metric-label">Documentos</span>
          <span className="metric-value">{stats.data?.documents ?? "…"}</span>
          <span className="metric-sub">
            {stats.data?.pages ?? 0} páginas · {stats.data?.chunks ?? 0} chunks
          </span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Components</span>
          <span className="metric-value">
            {Object.values(componentMap).filter((s) => s === "ok" || s === "configured").length}
            /{health.data?.components.length ?? "…"}
          </span>
          <span className="metric-sub">healthy / total</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Postgres saver</span>
          <span className="metric-value" style={{ fontSize: 16 }}>
            {(health.data?.components.find((c) => c.name === "checkpointer")?.metadata
              ?.backend as string) ?? "?"}
          </span>
          <span className="metric-sub">backend del checkpointer</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">LangSmith</span>
          <span className="metric-value" style={{ fontSize: 16 }}>
            {componentMap.langsmith ?? "?"}
          </span>
          <span className="metric-sub">
            {(health.data?.components.find((c) => c.name === "langsmith")?.metadata
              ?.project as string) ?? "—"}
          </span>
        </article>
      </div>

      {config.data && (
        <div className="grid">
          {GROUPS.map((group) => (
            <article key={group.title} className="section">
              <div className="section-head">
                <h2>{group.title}</h2>
              </div>
              <p className="muted small" style={{ margin: 0 }}>
                {group.description}
              </p>
              <table className="table small">
                <tbody>
                  {group.fields.map((field) => {
                    const value = field.extract(config.data!);
                    const danger = field.danger?.(config.data!) ?? false;
                    return (
                      <tr key={field.label}>
                        <td style={{ width: "55%" }}>
                          <code className="small">{field.label}</code>
                        </td>
                        <td>
                          <span className={statusClass(danger ? "danger" : "ok")}>
                            {value}
                          </span>
                        </td>
                        <td style={{ width: 30 }}>
                          <button
                            className="ghost"
                            onClick={() => copy(value)}
                            title="Copiar"
                            type="button"
                          >
                            ⎘
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </article>
          ))}
        </div>
      )}

      <section className="section">
        <h2>Salud actual de cada componente</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Componente</th>
                <th>Estado</th>
                <th>Detalle</th>
                <th>Latencia</th>
              </tr>
            </thead>
            <tbody>
              {(health.data?.components ?? []).map((component) => (
                <tr key={component.name}>
                  <td>{component.name}</td>
                  <td>
                    <span className={statusClass(component.status)}>{component.status}</span>
                  </td>
                  <td className="small muted">{component.detail ?? "—"}</td>
                  <td>{component.latency_ms ? `${component.latency_ms} ms` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
