"use client";

import { useMemo, useState } from "react";

import type { ApiClient } from "../lib/api";
import { asArray, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import type { AgentSummary } from "../lib/types";

const POLICY_LABELS: Array<{ key: keyof AgentSummary["policy"]; label: string }> = [
  { key: "allow_local_rag", label: "RAG local" },
  { key: "allow_neo4j_read", label: "Grafo (lectura)" },
  { key: "allow_web", label: "Web search" },
  { key: "allow_workspace_write", label: "Workspace write" },
  { key: "allow_shell", label: "Shell" },
  { key: "allow_browser", label: "Browser" },
  { key: "allow_email", label: "Email" },
  { key: "allow_social_posting", label: "Social" },
  { key: "allow_delete", label: "Delete" }
];

export function AgentsView({ client }: { client: ApiClient }) {
  const agents = usePolledFetch<AgentSummary[]>(client, "/agents", 10000);
  const [openName, setOpenName] = useState<string | null>(null);

  const list = useMemo(() => asArray(agents.data), [agents.data]);

  return (
    <div className="stack">
      <section className="section">
        <div className="section-head">
          <h2>DeepAgents activos</h2>
          <span className="muted small">{list.length} agentes registrados</span>
        </div>
        <p className="muted small">
          Cada DeepAgent corre bajo una política estricta y solo accede a las herramientas
          permitidas. La actividad se cuenta desde la tabla <code>jobs</code>; click para ver
          el detalle.
        </p>
      </section>

      <div className="grid">
        {list.length === 0 && (
          <AgentsStatusCard
            state={agents.error ? "error" : agents.loading ? "loading" : "empty"}
            errorMessage={agents.error}
            onRetry={() => void agents.refetch()}
          />
        )}
        {list.map((agent) => {
          const expanded = openName === agent.name;
          return (
            <article
              key={agent.name}
              className="section"
              style={{ gridColumn: expanded ? "1 / -1" : undefined }}
            >
              <div className="section-head">
                <div>
                  <h2 style={{ marginBottom: 4 }}>{agent.name}</h2>
                  <div className="row" style={{ gap: 6 }}>
                    <span className="badge info">{agent.kind}</span>
                    <span className="badge">job: {agent.job_type}</span>
                    {agent.web_search_enabled && (
                      <span className="badge ok">web search on</span>
                    )}
                    {agent.requires_approval_for_drafts && (
                      <span className="badge warn">drafts → HITL</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => setOpenName(expanded ? null : agent.name)}
                  type="button"
                >
                  {expanded ? "Cerrar" : "Detalle"}
                </button>
              </div>
              <p className="small">{agent.description}</p>

              <div className="grid-3 small" style={{ gap: 8 }}>
                <Stat label="Total jobs" value={agent.stats.total_jobs} />
                <Stat
                  label="Activos"
                  value={agent.stats.running}
                  highlight={agent.stats.running > 0}
                />
                <Stat label="Completados" value={agent.stats.completed} />
                <Stat
                  label="Fallidos"
                  value={agent.stats.failed}
                  danger={agent.stats.failed > 0}
                />
                <Stat
                  label="Última actividad"
                  value={
                    agent.stats.last_active_at
                      ? new Date(agent.stats.last_active_at).toLocaleString()
                      : "—"
                  }
                />
                <Stat
                  label="Memoria"
                  value={agent.memory_enabled ? "habilitada" : "deshabilitada"}
                />
              </div>

              {expanded && (
                <div className="grid-2" style={{ gap: 12 }}>
                  <div className="stack" style={{ gap: 8 }}>
                    <h3>Política runtime</h3>
                    <table className="table small">
                      <tbody>
                        {POLICY_LABELS.map(({ key, label }) => {
                          const allowed = agent.policy[key];
                          return (
                            <tr key={key}>
                              <td style={{ width: "60%" }}>{label}</td>
                              <td>
                                <span className={statusClass(allowed ? "ok" : "danger")}>
                                  {allowed ? "permitido" : "bloqueado"}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    <h3>Herramientas habilitadas</h3>
                    <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
                      {agent.tools.map((tool) => (
                        <li key={tool}>
                          <code>{tool}</code>
                        </li>
                      ))}
                    </ul>
                    <h3>Skills por defecto</h3>
                    <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                      {agent.skills.map((skill) => (
                        <span key={skill} className="badge info">
                          {skill}
                        </span>
                      ))}
                      {agent.skills.length === 0 && (
                        <span className="muted small">sin skills cargadas</span>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Status card shown when the DeepAgents fleet is empty, loading, or has
 * errored. Mirrors the structure of a real agent card (article →
 * section-head → detail button) so the grid layout stays consistent
 * regardless of state — the same pattern Linear/Notion use for entity
 * lists. Copy is operator-facing, not debug-flavoured.
 */
function AgentsStatusCard({
  state,
  errorMessage,
  onRetry
}: {
  state: "error" | "loading" | "empty";
  errorMessage: string | null;
  onRetry: () => void;
}) {
  const copy = {
    error: {
      title: "No se pudo cargar la flota de DeepAgents",
      detail:
        errorMessage ??
        "La API de agentes no respondió. Reintentá para volver a consultarla.",
      badgeClass: "badge danger",
      badgeLabel: "error"
    },
    loading: {
      title: "Cargando flota de DeepAgents…",
      detail:
        "Consultando /agents para enumerar los agentes registrados y su política runtime.",
      badgeClass: "badge",
      badgeLabel: "cargando"
    },
    empty: {
      title: "Sin DeepAgents registrados",
      detail:
        "El backend aún no expone agentes vía /agents. Cuando exista al menos uno aparecerá aquí con su política, herramientas y stats.",
      badgeClass: "badge configured",
      badgeLabel: "vacío"
    }
  }[state];
  return (
    <article className="section" aria-label="DeepAgents fleet status">
      <div className="section-head">
        <div>
          <h2 style={{ marginBottom: 4 }}>{copy.title}</h2>
          <div className="row" style={{ gap: 6 }}>
            <span className={copy.badgeClass}>{copy.badgeLabel}</span>
          </div>
        </div>
        <button
          onClick={onRetry}
          type="button"
          aria-label="Reintentar carga de DeepAgents"
        >
          Detalle
        </button>
      </div>
      <p className="small">{copy.detail}</p>
    </article>
  );
}

function Stat({
  label,
  value,
  highlight,
  danger
}: {
  label: string;
  value: number | string;
  highlight?: boolean;
  danger?: boolean;
}) {
  return (
    <div
      className="metric-card"
      style={{
        minHeight: 0,
        borderColor: danger ? "var(--danger)" : highlight ? "var(--warn)" : undefined,
        background: danger
          ? "var(--danger-soft)"
          : highlight
            ? "var(--warn-soft)"
            : undefined
      }}
    >
      <span className="metric-label">{label}</span>
      <span className="metric-value" style={{ fontSize: 16 }}>
        {value}
      </span>
    </div>
  );
}
