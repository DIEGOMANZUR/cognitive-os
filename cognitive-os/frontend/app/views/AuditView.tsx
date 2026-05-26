"use client";

import { useMemo, useState } from "react";

import type { ApiClient } from "../lib/api";
import { asArray } from "../lib/api";
import { EmptyState, ErrorPanel, Skeleton } from "../components/StatePrimitives";
import { usePolledFetch } from "../lib/hooks";
import type { AuditEvent } from "../lib/types";

export function AuditView({ client }: { client: ApiClient }) {
  const audit = usePolledFetch<AuditEvent[]>(client, "/audit/events?limit=300", 6000);
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    const list = asArray(audit.data);
    const q = filter.trim().toLowerCase();
    if (!q) return list;
    return list.filter((event) =>
      `${event.action} ${event.resource_type ?? ""} ${event.resource_id ?? ""} ${event.actor_id ?? ""}`
        .toLowerCase()
        .includes(q)
    );
  }, [audit.data, filter]);

  return (
    <section className="section">
      <div className="section-head">
        <h2>Audit log</h2>
        <div className="row">
          <input
            placeholder="Filtrar por acción / recurso / actor"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            style={{ minWidth: 260 }}
          />
          <span className={audit.error ? "badge danger" : "muted small"}>
            {audit.error ?? `${filtered.length} eventos`}
          </span>
          <button className="ghost" onClick={() => audit.refetch()} type="button">
            Refrescar
          </button>
        </div>
      </div>
      <div className="table-wrap" style={{ maxHeight: "70vh" }}>
        <table className="table">
          <thead>
            <tr>
              <th>Hora</th>
              <th>Actor</th>
              <th>Acción</th>
              <th>Recurso</th>
              <th>Metadata</th>
            </tr>
          </thead>
          <tbody>
            {audit.error && filtered.length === 0 && (
              <tr aria-label="Audit error placeholder row">
                <td className="small muted">—</td>
                <td>—</td>
                <td>
                  <code>audit.unavailable</code>
                </td>
                <td>
                  <span className="muted small">audit</span>
                </td>
                <td>
                  <pre style={{ margin: 0, maxHeight: 120 }}>
{JSON.stringify({ error: audit.error }, null, 2)}
                  </pre>
                </td>
              </tr>
            )}
            {audit.error && filtered.length === 0 && (
              <tr>
                <td colSpan={5}>
                  <ErrorPanel error={audit.error} onRetry={() => void audit.refetch()} />
                </td>
              </tr>
            )}
            {audit.loading && filtered.length === 0 && !audit.error && (
              <tr aria-label="Audit loading placeholder row">
                <td className="small muted">—</td>
                <td>—</td>
                <td>
                  <code>audit.loading</code>
                </td>
                <td>
                  <span className="muted small">audit</span>
                </td>
                <td>
                  <pre style={{ margin: 0, maxHeight: 120 }}>
{JSON.stringify({ status: "loading" }, null, 2)}
                  </pre>
                </td>
              </tr>
            )}
            {audit.loading && filtered.length === 0 && !audit.error && (
              <tr>
                <td colSpan={5}>
                  <Skeleton rows={4} />
                </td>
              </tr>
            )}
            {!audit.loading && !audit.error && filtered.length === 0 && (
              <tr aria-label="Audit empty placeholder row">
                <td className="small muted">—</td>
                <td>—</td>
                <td>
                  <code>audit.empty</code>
                </td>
                <td>
                  <span className="muted small">audit</span>
                </td>
                <td>
                  <pre style={{ margin: 0, maxHeight: 120 }}>
{JSON.stringify(
                      {
                        filter,
                        message:
                          "Sin eventos visibles para el filtro actual; la API respondió correctamente."
                      },
                      null,
                      2
                    )}
                  </pre>
                </td>
              </tr>
            )}
            {!audit.loading && !audit.error && filtered.length === 0 && (
              <tr>
                <td colSpan={5}>
                  <EmptyState
                    icon="audit"
                    title="Sin eventos visibles"
                    message="La API de auditoría respondió correctamente, pero no hay eventos para el filtro actual."
                  />
                </td>
              </tr>
            )}
            {filtered.map((event) => (
              <tr key={event.id}>
                <td className="small muted">
                  {new Date(event.created_at).toLocaleString()}
                </td>
                <td>{event.actor_id ?? "—"}</td>
                <td>
                  <code>{event.action}</code>
                </td>
                <td>
                  <span className="muted small">{event.resource_type ?? "—"}</span>
                  {event.resource_id && (
                    <>
                      <br />
                      <code className="small">{event.resource_id.slice(0, 16)}…</code>
                    </>
                  )}
                </td>
                <td>
                  <pre style={{ margin: 0, maxHeight: 120 }}>
                    {JSON.stringify(event.metadata_json, null, 2)}
                  </pre>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="audit-cards" aria-label="Audit events responsive cards">
        {filtered.map((event) => (
          <article key={`${event.id}-card`} className="metric-card">
            <span className="small muted">{new Date(event.created_at).toLocaleString()}</span>
            <strong>{event.action}</strong>
            <span className="small muted">
              {event.resource_type ?? "recurso"} · {event.resource_id ?? "sin id"}
            </span>
            <pre style={{ margin: 0, maxHeight: 120 }}>
              {JSON.stringify(event.metadata_json, null, 2)}
            </pre>
          </article>
        ))}
      </div>
    </section>
  );
}
