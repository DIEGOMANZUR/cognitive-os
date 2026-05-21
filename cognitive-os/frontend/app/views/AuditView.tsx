"use client";

import { useMemo, useState } from "react";

import type { ApiClient } from "../lib/api";
import { asArray } from "../lib/api";
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
          <span className="muted small">{filtered.length} eventos</span>
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
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  Sin eventos.
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
    </section>
  );
}
