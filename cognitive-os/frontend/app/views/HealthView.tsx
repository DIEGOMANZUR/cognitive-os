"use client";

import { useMemo } from "react";

import type { ApiClient } from "../lib/api";
import { statusClass } from "../lib/api";
import { Donut } from "../components/Charts";
import { Icon } from "../components/Icon";
import { usePolledFetch } from "../lib/hooks";
import type { HealthDashboardResponse } from "../lib/types";

const OK_STATUSES = new Set(["ok", "configured", "ready", "active"]);
const WARN_STATUSES = new Set(["disabled", "blocked", "pending", "queued", "unknown"]);

export function HealthView({ client }: { client: ApiClient }) {
  const dashboard = usePolledFetch<HealthDashboardResponse>(client, "/health/dashboard", 7000);

  const counts = useMemo(() => {
    const components = dashboard.data?.components ?? [];
    let ok = 0;
    let warn = 0;
    let danger = 0;
    for (const c of components) {
      if (OK_STATUSES.has(c.status)) ok += 1;
      else if (WARN_STATUSES.has(c.status)) warn += 1;
      else danger += 1;
    }
    return { ok, warn, danger, total: components.length };
  }, [dashboard.data]);

  const overall = dashboard.data?.status ?? "—";

  return (
    <div className="stack" style={{ gap: 18 }}>
      <header className="page-head">
        <div className="row" style={{ gap: 10, alignItems: "center" }}>
          <h1>Health dashboard</h1>
          <span
            className={`badge ${
              overall === "ok" ? "ok" : overall === "degraded" ? "warn" : "danger"
            }`}
          >
            <span
              className={`dot ${
                overall === "ok" ? "ok" : overall === "degraded" ? "warn" : "danger"
              } live`}
            />
            {overall}
          </span>
        </div>
        <span className="sub">
          {dashboard.data
            ? `actualizado a las ${new Date(dashboard.data.checked_at).toLocaleTimeString()} · ${counts.total} componentes monitorizados`
            : "Cargando estado del stack…"}
        </span>
      </header>

      <div className="grid-2">
        <section className="section">
          <div className="section-head">
            <h2>Distribución</h2>
            <button className="ghost small" onClick={() => dashboard.refetch()} type="button">
              <Icon name="refresh" size={13} /> Refrescar
            </button>
          </div>
          {counts.total > 0 ? (
            <Donut
              slices={[
                { name: "ok", value: counts.ok, color: "var(--ok)" },
                { name: "atención", value: counts.warn, color: "var(--warn)" },
                { name: "fallo", value: counts.danger, color: "var(--danger)" }
              ].filter((s) => s.value > 0)}
              centerValue={`${counts.ok}/${counts.total}`}
              centerSub="ok"
              label="Distribución de componentes por estado"
            />
          ) : (
            <div className="empty-state">
              <span className="empty-icon">
                <Icon name="health" size={18} />
              </span>
              <strong>Sin lecturas todavía</strong>
              <span className="empty-msg">
                El backend aún no respondió. Verificá tu JWT y la URL de la API.
              </span>
            </div>
          )}
        </section>

        <section className="section">
          <div className="section-head">
            <h2>Resumen rápido</h2>
          </div>
          <div className="grid">
            <Stat label="Componentes ok" value={counts.ok.toString()} tone="ok" icon="circleCheck" />
            <Stat label="En atención" value={counts.warn.toString()} tone="warn" icon="alert" />
            <Stat label="Con fallo" value={counts.danger.toString()} tone="danger" icon="circleX" />
            <Stat label="Total" value={counts.total.toString()} tone="info" icon="health" />
          </div>
        </section>
      </div>

      {dashboard.error && (
        <div className="warn-box row">
          <Icon name="alert" size={16} />
          <span>{dashboard.error}</span>
        </div>
      )}

      <section className="section">
        <div className="section-head">
          <h2>Componentes</h2>
          <span className="faint small">live polling cada 7s</span>
        </div>
        {dashboard.data ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Componente</th>
                  <th>Estado</th>
                  <th style={{ textAlign: "right" }}>Latencia</th>
                  <th>Detalle</th>
                  <th>Metadata</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.data.components.map((component) => (
                  <tr key={component.name}>
                    <td>
                      <strong>{component.name}</strong>
                    </td>
                    <td>
                      <span className={statusClass(component.status)}>{component.status}</span>
                    </td>
                    <td className="mono small faint" style={{ textAlign: "right" }}>
                      {component.latency_ms ? `${component.latency_ms} ms` : "—"}
                    </td>
                    <td className="small">{component.detail ?? "—"}</td>
                    <td>
                      {component.metadata &&
                      Object.keys(component.metadata).length > 0 ? (
                        <details>
                          <summary className="small muted">
                            ver metadata ({Object.keys(component.metadata).length})
                          </summary>
                          <ul className="small" style={{ margin: "6px 0 0", paddingLeft: "1rem" }}>
                            {Object.entries(component.metadata).map(([k, v]) => (
                              <li key={k}>
                                <code>{k}</code>:{" "}
                                <span className="muted">
                                  {typeof v === "string" ||
                                  typeof v === "number" ||
                                  typeof v === "boolean"
                                    ? String(v)
                                    : JSON.stringify(v)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </details>
                      ) : (
                        <span className="muted small">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="stack">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton skeleton-line" />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  icon
}: {
  label: string;
  value: string;
  tone: "ok" | "warn" | "danger" | "info";
  icon: Parameters<typeof Icon>[0]["name"];
}) {
  const color =
    tone === "ok"
      ? "var(--ok)"
      : tone === "warn"
        ? "var(--warn)"
        : tone === "danger"
          ? "var(--danger)"
          : "var(--info)";
  return (
    <div className="metric-card">
      <span className="spread">
        <span className="metric-label">{label}</span>
        <span style={{ color }} aria-hidden="true">
          <Icon name={icon} size={16} />
        </span>
      </span>
      <span className="metric-value" style={{ color }}>
        {value}
      </span>
    </div>
  );
}
