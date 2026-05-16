"use client";

import type { ApiClient } from "../lib/api";
import { statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import type { HealthDashboardResponse } from "../lib/types";

export function HealthView({ client }: { client: ApiClient }) {
  const dashboard = usePolledFetch<HealthDashboardResponse>(client, "/health/dashboard", 7000);

  return (
    <section className="section">
      <div className="section-head">
        <h2>Health dashboard</h2>
        {dashboard.data && (
          <span className={statusClass(dashboard.data.status)}>{dashboard.data.status}</span>
        )}
      </div>
      <div className="row">
        <span className="muted small">
          {dashboard.data
            ? `actualizado ${new Date(dashboard.data.checked_at).toLocaleTimeString()}`
            : "Cargando…"}
        </span>
        <button className="ghost" onClick={() => dashboard.refetch()} type="button">
          Refrescar
        </button>
      </div>
      {dashboard.error && <p className="badge danger">{dashboard.error}</p>}
      {dashboard.data && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Componente</th>
                <th>Estado</th>
                <th>Latencia</th>
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
                  <td>{component.latency_ms ? `${component.latency_ms} ms` : "—"}</td>
                  <td className="small">{component.detail ?? "—"}</td>
                  <td>
                    <pre style={{ margin: 0, maxHeight: 120 }}>
                      {JSON.stringify(component.metadata, null, 2)}
                    </pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
