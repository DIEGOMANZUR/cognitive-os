"use client";

import { useMemo, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch, useHydrated } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type {
  ApprovalResponse,
  AuditEvent,
  HealthDashboardResponse,
  JobResponse,
  KnowledgeStats,
  PublicConfig,
  Tab
} from "../lib/types";

export function DashboardView({
  client,
  onNavigate
}: {
  client: ApiClient;
  onNavigate: (tab: Tab) => void;
}) {
  const authed = Boolean(client.authToken);
  const stats = usePolledFetch<KnowledgeStats>(client, authed ? "/knowledge/stats" : null, 8000);
  const health = usePolledFetch<HealthDashboardResponse>(
    client,
    authed ? "/health/dashboard" : null,
    15000
  );
  const jobs = usePolledFetch<JobResponse[]>(client, authed ? "/jobs?limit=8" : null, 5000);
  const approvals = usePolledFetch<ApprovalResponse[]>(client, authed ? "/approvals" : null, 10000);
  const audit = usePolledFetch<AuditEvent[]>(client, authed ? "/audit/events?limit=15" : null, 12000);
  const config = usePolledFetch<PublicConfig>(client, authed ? "/config/public" : null, 60000);
  const toast = useToast();
  const hydrated = useHydrated();

  const pendingApprovals = useMemo(
    () => (approvals.data ?? []).filter((approval) => approval.status === "pending"),
    [approvals.data]
  );
  const runningJobs = useMemo(
    () =>
      (jobs.data ?? []).filter((job) => ["queued", "running"].includes(job.status)),
    [jobs.data]
  );

  const [busy, setBusy] = useState(false);
  async function triggerConsolidation() {
    setBusy(true);
    try {
      await client.post("/deepagents/memory/consolidate/run", {});
      toast.push("Memoria DeepAgents consolidada (job dispatched).", "success");
      void jobs.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack" style={{ gap: 18 }}>
      <section className="section">
        <div className="section-head">
          <h2>Operations Dashboard</h2>
          <div className="row">
            <button onClick={() => onNavigate("chat")} type="button">
              Abrir Chat
            </button>
            <button onClick={() => onNavigate("documents")} type="button">
              Ingestar PDF
            </button>
            <button onClick={() => onNavigate("documentAnalysis")} type="button">
              Lanzar análisis
            </button>
            <button onClick={() => onNavigate("googleOps")} type="button">
              Google Ops
            </button>
            <button onClick={triggerConsolidation} disabled={busy} type="button">
              Consolidar memoria
            </button>
          </div>
        </div>
        <div className="grid">
          <MetricCard
            label="Documentos"
            value={stats.data?.documents ?? "…"}
            sub={`${stats.data?.pages ?? 0} páginas · ${stats.data?.chunks ?? 0} chunks`}
          />
          <MetricCard
            label="Jobs activos"
            value={stats.data?.jobs_running ?? "…"}
            sub={`${stats.data?.jobs_completed ?? 0} completados · ${stats.data?.jobs_failed ?? 0} fallidos`}
          />
          <MetricCard
            label="Aprobaciones pendientes"
            value={stats.data?.approvals_pending ?? "…"}
            sub="Acciones HITL en cola"
            highlight={Boolean(stats.data?.approvals_pending)}
          />
          <MetricCard
            label="Estado global"
            value={health.data?.status ?? "…"}
            sub={
              health.data
                ? `${health.data.components.filter((c) => c.status === "ok" || c.status === "configured").length}/${health.data.components.length} componentes ok`
                : "Consultando…"
            }
          />
        </div>
      </section>

      <div className="grid-2">
        <section className="section">
          <div className="section-head">
            <h2>Componentes</h2>
            <button className="ghost" onClick={() => onNavigate("health")} type="button">
              Detalle →
            </button>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Componente</th>
                  <th>Estado</th>
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
                    <td>{component.latency_ms ? `${component.latency_ms} ms` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="section">
          <div className="section-head">
            <h2>Jobs recientes</h2>
            <button className="ghost" onClick={() => onNavigate("jobs")} type="button">
              Ver todos →
            </button>
          </div>
          {runningJobs.length === 0 && (jobs.data ?? []).length === 0 && (
            <p className="muted small">Sin jobs todavía.</p>
          )}
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Estado</th>
                  <th>Prog.</th>
                  <th>Hace</th>
                </tr>
              </thead>
              <tbody>
                {(jobs.data ?? []).slice(0, 8).map((job) => (
                  <tr key={job.id}>
                    <td>{job.job_type}</td>
                    <td>
                      <span className={statusClass(job.status)}>{job.status}</span>
                    </td>
                    <td>{job.progress}%</td>
                    <td>{hydrated ? relativeTime(job.updated_at) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div className="grid-2">
        <section className="section">
          <div className="section-head">
            <h2>Aprobaciones pendientes</h2>
            <button className="ghost" onClick={() => onNavigate("approvals")} type="button">
              Ver todas →
            </button>
          </div>
          {pendingApprovals.length === 0 ? (
            <p className="muted small">Sin aprobaciones pendientes.</p>
          ) : (
            <ul className="stack">
              {pendingApprovals.slice(0, 5).map((approval) => (
                <li key={approval.id} className="warn-box">
                  <strong>{approval.requested_action}</strong>
                  <p className="muted small">
                    Solicitada por {approval.requested_by ?? "local"} ·{" "}
                    {hydrated ? relativeTime(approval.created_at) : "—"}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="section">
          <div className="section-head">
            <h2>Audit log</h2>
            <button className="ghost" onClick={() => onNavigate("audit")} type="button">
              Ver todo →
            </button>
          </div>
          {(audit.data ?? []).length === 0 ? (
            <p className="muted small">Sin eventos auditados aún.</p>
          ) : (
            <ul className="stack small">
              {(audit.data ?? []).slice(0, 12).map((event) => (
                <li key={event.id}>
                  <code>{event.action}</code>{" "}
                  <span className="muted">
                    {event.resource_type ?? "—"} ·{" "}
                    {hydrated ? relativeTime(event.created_at) : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="section">
        <div className="section-head">
          <h2>Configuración activa</h2>
          <button className="ghost" onClick={() => onNavigate("settings")} type="button">
            Modificar →
          </button>
        </div>
        {config.data ? (
          <div className="grid-3 small">
            <ConfigItem label="Entorno" value={config.data.environment} />
            <ConfigItem label="Read-only mode" value={String(config.data.tools_readonly_mode)} />
            <ConfigItem
              label="Aprobación humana"
              value={String(config.data.require_human_approval_for_external_actions)}
            />
            <ConfigItem
              label="Web search"
              value={
                config.data.web_search_enabled
                  ? `${config.data.web_search_providers.join(", ") || "ningún provider"}`
                  : "off"
              }
            />
            <ConfigItem
              label="Embeddings"
              value={`${config.data.embeddings_provider} · ${config.data.embeddings_model} (${config.data.embeddings_dimension}d, pool=${config.data.embeddings_key_pool_size})`}
            />
            <ConfigItem
              label="Primary LLM"
              value={`${config.data.primary_llm_provider} · ${config.data.primary_llm_model}`}
            />
            <ConfigItem label="Reranker" value={config.data.reranker_enabled ? "on" : "off"} />
            <ConfigItem label="DeepAgents skills" value={config.data.deepagents_enable_skills ? "on" : "off"} />
            <ConfigItem
              label="Memory require approval"
              value={String(config.data.deepagents_memory_require_approval)}
            />
          </div>
        ) : !authed ? (
          <p className="muted small">Inicia sesión (JWT en el TopBar) para ver la configuración activa.</p>
        ) : (
          <p className="muted small">Cargando…</p>
        )}
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  highlight
}: {
  label: string;
  value: number | string;
  sub: string;
  highlight?: boolean;
}) {
  return (
    <div
      className="metric-card"
      style={highlight ? { borderColor: "var(--warn)", background: "var(--warn-soft)" } : undefined}
    >
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
      <span className="metric-sub">{sub}</span>
    </div>
  );
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="stack" style={{ gap: 2 }}>
      <span className="muted small">{label}</span>
      <code>{value}</code>
    </div>
  );
}

function relativeTime(iso: string): string {
  if (!iso) return "—";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return iso;
  const now = Date.now();
  const diff = Math.max(0, now - ts);
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h`;
  const days = Math.round(hours / 24);
  return `${days}d`;
}
