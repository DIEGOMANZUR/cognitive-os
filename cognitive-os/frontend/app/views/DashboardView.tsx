"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "../lib/api";
import { asArray, errorMessage, statusClass } from "../lib/api";
import { AreaChart, BarList, Donut, Sparkline } from "../components/Charts";
import { Icon } from "../components/Icon";
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

const TREND_LENGTH = 24;

function relativeTime(iso: string): string {
  if (!iso) return "—";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return iso;
  const diff = Math.max(0, Date.now() - ts);
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

function useSeries(value: number | null | undefined): number[] {
  const ref = useRef<number[]>([]);
  if (typeof value === "number" && !Number.isNaN(value)) {
    const next = [...ref.current, value];
    ref.current = next.slice(-TREND_LENGTH);
  }
  return ref.current;
}

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
  const jobs = usePolledFetch<JobResponse[]>(client, authed ? "/jobs?limit=20" : null, 5000);
  const approvals = usePolledFetch<ApprovalResponse[]>(client, authed ? "/approvals" : null, 10000);
  const audit = usePolledFetch<AuditEvent[]>(client, authed ? "/audit/events?limit=15" : null, 12000);
  const config = usePolledFetch<PublicConfig>(client, authed ? "/config/public" : null, 60000);
  const toast = useToast();
  const hydrated = useHydrated();

  const pendingApprovals = useMemo(
    () => asArray(approvals.data).filter((approval) => approval.status === "pending"),
    [approvals.data]
  );
  const runningJobs = useMemo(
    () => asArray(jobs.data).filter((job) => ["queued", "running"].includes(job.status)),
    [jobs.data]
  );

  // ---- Trend buffers (kept in component refs so we don't need a backend
  // time-series endpoint just for sparklines).
  const jobsRunningSeries = useSeries(stats.data?.jobs_running);
  const approvalsSeries = useSeries(stats.data?.approvals_pending);
  const docsSeries = useSeries(stats.data?.documents);
  // `configured` is wired-but-unverified — NOT a verified ok. Counting it as
  // ok would paint the dashboard green dishonestly (AUDIT-2026-B).
  const okComponents = health.data
    ? health.data.components.filter((c) => ["ok", "ready", "active"].includes(c.status)).length
    : null;
  const componentsSeries = useSeries(okComponents);

  // Latency series — derived from the live `components` list. We compute the
  // top-5 slowest each tick and append into a per-component ring buffer.
  const latencyBuffersRef = useRef<Record<string, number[]>>({});
  useEffect(() => {
    const components = health.data?.components ?? [];
    for (const c of components) {
      if (c.latency_ms == null) continue;
      const buf = latencyBuffersRef.current[c.name] ?? [];
      const next = [...buf, c.latency_ms].slice(-TREND_LENGTH);
      latencyBuffersRef.current[c.name] = next;
    }
  }, [health.data]);

  const slowestSeries = useMemo(() => {
    const components = health.data?.components ?? [];
    return components
      .filter((c) => typeof c.latency_ms === "number")
      .sort((a, b) => (b.latency_ms ?? 0) - (a.latency_ms ?? 0))
      .slice(0, 3)
      .map((c) => ({
        name: c.name,
        data: latencyBuffersRef.current[c.name] ?? [c.latency_ms ?? 0]
      }));
  }, [health.data]);

  const jobMix = useMemo(() => {
    const counts = { running: 0, queued: 0, completed: 0, failed: 0, other: 0 } as Record<string, number>;
    for (const job of asArray(jobs.data)) {
      if (counts[job.status] !== undefined) counts[job.status] += 1;
      else counts.other += 1;
    }
    return [
      { name: "running", value: counts.running, color: "var(--info)" },
      { name: "queued", value: counts.queued, color: "var(--warn)" },
      { name: "completed", value: counts.completed, color: "var(--ok)" },
      { name: "failed", value: counts.failed, color: "var(--danger)" }
    ];
  }, [jobs.data]);

  const totalJobs = jobMix.reduce((s, slice) => s + slice.value, 0);

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

  const overallStatus = health.data?.status ?? "—";
  const componentsCount = health.data?.components.length ?? 0;
  const componentsOk = okComponents ?? 0;
  // NOTE: the smoke spec asserts on the literal "X/Y componentes ok" substring.
  // Keep this exact phrasing.
  const overallSub = health.data
    ? `${componentsOk}/${componentsCount} componentes ok`
    : "Consultando…";

  const deltaJobs = jobsRunningSeries.length >= 2
    ? jobsRunningSeries[jobsRunningSeries.length - 1] - jobsRunningSeries[0]
    : 0;
  const deltaApprovals = approvalsSeries.length >= 2
    ? approvalsSeries[approvalsSeries.length - 1] - approvalsSeries[0]
    : 0;

  return (
    <div className="stack" style={{ gap: 18 }}>
      <header className="page-head">
        <div className="row" style={{ gap: 10, alignItems: "center" }}>
          <h1>Operations Dashboard</h1>
          <span
            className={`badge ${overallStatus === "ok" ? "ok" : overallStatus === "degraded" ? "warn" : "danger"}`}
            aria-label={`Estado global: ${overallStatus}`}
          >
            <span
              className={`dot ${overallStatus === "ok" ? "ok" : overallStatus === "degraded" ? "warn" : "danger"} live`}
            />
            Estado global · {overallStatus}
          </span>
        </div>
        <span className="sub">
          Estado en vivo de tu Cognitive OS · {overallSub}
        </span>
      </header>

      <section className="section">
        <div className="section-head">
          <h2>Acciones rápidas</h2>
          <div className="toolbar">
            <button onClick={() => onNavigate("chat")} type="button">
              <Icon name="chat" size={14} /> Abrir Chat
            </button>
            <button onClick={() => onNavigate("documents")} type="button">
              <Icon name="documents" size={14} /> Ingestar PDF
            </button>
            <button onClick={() => onNavigate("documentAnalysis")} type="button">
              <Icon name="documentAnalysis" size={14} /> Lanzar análisis
            </button>
            <button onClick={() => onNavigate("googleOps")} type="button">
              <Icon name="googleOps" size={14} /> Google Ops
            </button>
            <button className="primary" onClick={triggerConsolidation} disabled={busy} type="button">
              <Icon name="sparkle" size={14} /> Consolidar memoria
            </button>
          </div>
        </div>

        <div className="grid">
          <MetricCard
            label="Documentos"
            value={stats.data?.documents ?? "…"}
            sub={`${stats.data?.pages ?? 0} páginas · ${stats.data?.chunks ?? 0} chunks`}
            series={docsSeries}
            icon="documents"
          />
          <MetricCard
            label="Jobs activos"
            value={stats.data?.jobs_running ?? "…"}
            sub={`${stats.data?.jobs_completed ?? 0} completados · ${stats.data?.jobs_failed ?? 0} fallidos`}
            series={jobsRunningSeries}
            delta={deltaJobs}
            icon="jobs"
          />
          <MetricCard
            label="Aprobaciones"
            value={stats.data?.approvals_pending ?? "…"}
            sub="Acciones HITL en cola"
            series={approvalsSeries}
            delta={deltaApprovals}
            highlight={Boolean(stats.data?.approvals_pending)}
            icon="approvals"
          />
          <MetricCard
            label="Componentes ok"
            value={
              health.data ? `${componentsOk}/${componentsCount}` : "…"
            }
            sub={`status global · ${overallStatus}`}
            series={componentsSeries}
            icon="health"
          />
        </div>
      </section>

      <div className="grid-2">
        <section className="section">
          <div className="section-head">
            <h2>Componentes</h2>
            <button className="ghost small" onClick={() => onNavigate("health")} type="button">
              Detalle <Icon name="arrowRight" size={12} />
            </button>
          </div>
          {health.data ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Componente</th>
                    <th>Estado</th>
                    <th style={{ textAlign: "right" }}>Latencia</th>
                  </tr>
                </thead>
                <tbody>
                  {health.data.components.map((component) => (
                    <tr key={component.name}>
                      <td className="mono small">{component.name}</td>
                      <td>
                        <span className={statusClass(component.status)}>{component.status}</span>
                      </td>
                      <td className="mono small faint" style={{ textAlign: "right" }}>
                        {component.latency_ms ? `${component.latency_ms} ms` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <SkeletonRows rows={6} />
          )}
        </section>

        <section className="section">
          <div className="section-head">
            <h2>Mix de jobs</h2>
            <button className="ghost small" onClick={() => onNavigate("jobs")} type="button">
              Ver todos <Icon name="arrowRight" size={12} />
            </button>
          </div>
          {totalJobs > 0 ? (
            <Donut
              slices={jobMix.filter((s) => s.value > 0)}
              centerValue={totalJobs.toString()}
              centerSub="jobs"
              label="Distribución de jobs por estado"
            />
          ) : jobs.data ? (
            <EmptyState
              title="Sin jobs todavía"
              text="Cuando dispares un análisis o un research, el mix aparece acá."
            />
          ) : (
            <SkeletonRows rows={4} />
          )}
        </section>
      </div>

      <section className="section">
        <div className="section-head">
          <h2>Latencia de servicios</h2>
          <span className="faint small">últimos {TREND_LENGTH} polls · top 3 más lentos</span>
        </div>
        {slowestSeries.length > 0 ? (
          <AreaChart series={slowestSeries} yLabel="ms" formatter={(v) => `${Math.round(v)} ms`} />
        ) : (
          <EmptyState
            title="Aún no hay muestras"
            text="El gráfico se llena después de unos polls del health dashboard."
          />
        )}
      </section>

      <div className="grid-2">
        <section className="section">
          <div className="section-head">
            <h2>Aprobaciones pendientes</h2>
            <button className="ghost small" onClick={() => onNavigate("approvals")} type="button">
              Ver todas <Icon name="arrowRight" size={12} />
            </button>
          </div>
          {pendingApprovals.length === 0 ? (
            <EmptyState
              icon="approvals"
              title="Sin aprobaciones pendientes"
              text="Cuando un agente proponga una acción sensible aparecerá aquí."
            />
          ) : (
            <div className="stack">
              {pendingApprovals.slice(0, 6).map((approval) => (
                <button
                  key={approval.id}
                  className="ghost"
                  type="button"
                  onClick={() => onNavigate("approvals")}
                  style={{
                    justifyContent: "flex-start",
                    padding: "11px 12px",
                    border: "1px solid rgba(251, 191, 69, 0.4)",
                    background: "var(--warn-soft)",
                    textAlign: "left"
                  }}
                >
                  <span className="notif-mark warn" aria-hidden="true">
                    <Icon name="alert" size={14} />
                  </span>
                  <span className="stack" style={{ gap: 2, alignItems: "flex-start", flex: 1 }}>
                    <strong>{approval.requested_action}</strong>
                    <span className="muted small">
                      {approval.requested_by ?? "local"} · {hydrated ? relativeTime(approval.created_at) : "—"}
                    </span>
                  </span>
                  <Icon name="chevronRight" size={14} />
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="section">
          <div className="section-head">
            <h2>Audit log</h2>
            <button className="ghost small" onClick={() => onNavigate("audit")} type="button">
              Ver todo <Icon name="arrowRight" size={12} />
            </button>
          </div>
          {asArray(audit.data).length === 0 ? (
            <EmptyState
              icon="audit"
              title="Sin eventos registrados"
              text="Toda acción del operador o del agente se registra aquí."
            />
          ) : (
            <ul className="stack small" style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {asArray(audit.data).slice(0, 12).map((event) => (
                <li key={event.id} className="row" style={{ gap: 8, padding: "4px 0" }}>
                  <span className="dot info" aria-hidden="true" />
                  <code>{event.action}</code>
                  <span className="muted ellipsis">
                    {event.resource_type ?? "—"} · {hydrated ? relativeTime(event.created_at) : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {runningJobs.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>Jobs en ejecución</h2>
            <span className="badge info">
              <span className="dot info live" /> {runningJobs.length} corriendo
            </span>
          </div>
          <BarList
            items={runningJobs.slice(0, 8).map((job) => ({
              label: `${job.job_type} · ${job.id.slice(0, 8)}`,
              value: job.progress,
              tone: "info"
            }))}
            max={100}
            formatter={(v) => `${v}%`}
          />
        </section>
      )}

      <section className="section">
        <div className="section-head">
          <h2>Configuración activa</h2>
          <button className="ghost small" onClick={() => onNavigate("settings")} type="button">
            Modificar <Icon name="arrowRight" size={12} />
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
          <EmptyState
            icon="key"
            title="Sesión sin autenticar"
            text="El cockpit intentará activar un JWT local automático. Si lo cambiaste manualmente, revisá Conexión."
          />
        ) : (
          <SkeletonRows rows={3} />
        )}
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  series,
  delta,
  highlight,
  icon
}: {
  label: string;
  value: number | string;
  sub: string;
  series?: number[];
  delta?: number;
  highlight?: boolean;
  icon?: Parameters<typeof Icon>[0]["name"];
}) {
  const arrow = delta && delta !== 0 ? (delta > 0 ? "▲" : "▼") : "·";
  const tone = !delta ? "faint" : delta > 0 ? "ok" : "warn";
  return (
    <div className={`metric-card${highlight ? " is-alert" : ""}`}>
      <span className="spread">
        <span className="metric-label">{label}</span>
        {icon && (
          <span className="faint" aria-hidden="true">
            <Icon name={icon} size={15} />
          </span>
        )}
      </span>
      <span className="metric-value">{value}</span>
      <span className="spread" style={{ alignItems: "flex-end", gap: 8 }}>
        <span className="metric-sub">{sub}</span>
        {series && series.length > 1 && (
          <Sparkline data={series} width={88} height={24} />
        )}
      </span>
      {typeof delta === "number" && delta !== 0 && (
        <span className={`small ${tone === "ok" ? "" : "danger-text"}`} style={{ fontFamily: "var(--mono)" }}>
          {arrow} {Math.abs(delta)} en ventana
        </span>
      )}
    </div>
  );
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="stack" style={{ gap: 3 }}>
      <span className="faint small" style={{ textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {label}
      </span>
      <code>{value}</code>
    </div>
  );
}

function EmptyState({
  title,
  text,
  icon
}: {
  title: string;
  text: string;
  icon?: Parameters<typeof Icon>[0]["name"];
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon ?? "inbox"} size={18} />
      </span>
      <strong>{title}</strong>
      <span className="empty-msg">{text}</span>
    </div>
  );
}

function SkeletonRows({ rows }: { rows: number }) {
  return (
    <div className="stack">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton skeleton-line" />
      ))}
    </div>
  );
}
