"use client";

import { useEffect, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { JobEventResponse, JobResponse } from "../lib/types";

const TYPE_OPTIONS = [
  "",
  "document_ingestion",
  "document_analysis",
  "deepagent_research",
  "openshell_sandbox",
  "deepagent_memory_consolidation",
  "health_check",
  "cleanup_old_jobs",
  "debug_fast"
];

const STATUS_OPTIONS = ["", "queued", "running", "completed", "failed", "cancelled", "waiting_approval"];

export function JobsView({ client }: { client: ApiClient }) {
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [cancelingJobId, setCancelingJobId] = useState<string | null>(null);
  const toast = useToast();
  const params = new URLSearchParams();
  if (type) params.set("job_type", type);
  if (status) params.set("job_status", status);
  params.set("limit", "100");

  const jobs = usePolledFetch<JobResponse[]>(client, `/jobs?${params.toString()}`, 4000);
  const events = usePolledFetch<JobEventResponse[]>(
    client,
    selectedJobId ? `/jobs/${selectedJobId}/events` : null,
    3000
  );

  useEffect(() => {
    if (selectedJobId && jobs.data && !jobs.data.find((job) => job.id === selectedJobId)) {
      setSelectedJobId(null);
    }
  }, [jobs.data, selectedJobId]);

  async function cancel(id: string) {
    if (cancelingJobId) return;
    setCancelingJobId(id);
    try {
      await client.post(`/jobs/${id}/cancel`, {});
      toast.push("Job cancelado.", "success");
      void jobs.refetch();
      if (selectedJobId === id) void events.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setCancelingJobId(null);
    }
  }

  return (
    <div className="grid-2" style={{ gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)" }}>
      <section className="section">
        <div className="section-head">
          <h2>Jobs</h2>
          <div className="row">
            <select value={type} onChange={(event) => setType(event.target.value)}>
              {TYPE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option || "Cualquier tipo"}
                </option>
              ))}
            </select>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option || "Cualquier estado"}
                </option>
              ))}
            </select>
            <button className="ghost" onClick={() => jobs.refetch()} type="button">
              Refrescar
            </button>
          </div>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>job_id</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th>Prog.</th>
                <th>Creado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(jobs.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">
                    Sin jobs para este filtro.
                  </td>
                </tr>
              )}
              {(jobs.data ?? []).map((job) => {
                const terminal = ["completed", "failed", "cancelled"].includes(job.status);
                return (
                  <tr
                    key={job.id}
                    style={
                      selectedJobId === job.id
                        ? { background: "var(--accent-soft)" }
                        : undefined
                    }
                  >
                    <td>
                      <code>{job.id.slice(0, 8)}…</code>
                    </td>
                    <td>{job.job_type}</td>
                    <td>
                      <span className={statusClass(job.status)}>{job.status}</span>
                    </td>
                    <td>
                      <progress max={100} value={job.progress} />
                      <span className="muted small"> {job.progress}%</span>
                    </td>
                    <td className="small muted">
                      {new Date(job.created_at).toLocaleString()}
                    </td>
                    <td>
                      <div className="row">
                        <button onClick={() => setSelectedJobId(job.id)} type="button">
                          Ver
                        </button>
                        <button
                          className="danger"
                          onClick={() => cancel(job.id)}
                          disabled={terminal || cancelingJobId !== null}
                          type="button"
                        >
                          Cancelar
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Eventos</h2>
          {selectedJobId && (
            <span className="muted small">
              <code>{selectedJobId.slice(0, 8)}…</code>
            </span>
          )}
        </div>
        {!selectedJobId && <p className="muted small">Seleccioná un job para ver sus eventos.</p>}
        {selectedJobId && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Hora</th>
                  <th>Evento</th>
                  <th>Estado</th>
                  <th>Mensaje</th>
                  <th>Metadata</th>
                </tr>
              </thead>
              <tbody>
                {(events.data ?? []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted">
                      Sin eventos registrados para este job.
                    </td>
                  </tr>
                )}
                {(events.data ?? []).map((event) => (
                  <tr key={event.id}>
                    <td className="small muted">
                      {new Date(event.created_at).toLocaleTimeString()}
                    </td>
                    <td>{event.event_type}</td>
                    <td>
                      <span className={statusClass(event.status)}>{event.status}</span>
                    </td>
                    <td className="small">{event.message ?? "—"}</td>
                    <td className="small">
                      {Object.keys(event.metadata_json).length > 0 ? (
                        <details>
                          <summary>Ver metadata</summary>
                          <pre>{JSON.stringify(event.metadata_json, null, 2)}</pre>
                        </details>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
