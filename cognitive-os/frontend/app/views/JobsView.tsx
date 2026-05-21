"use client";

import { useEffect, useState } from "react";

import type { ApiClient } from "../lib/api";
import { asArray, errorMessage, statusClass } from "../lib/api";
import { Icon } from "../components/Icon";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { JobCancelResponse, JobEventResponse, JobResponse } from "../lib/types";

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
      const result = await client.post<JobCancelResponse>(`/jobs/${id}/cancel`, {});
      if (result.celery_revoke_error) {
        toast.push(`Cancelación falló: ${result.celery_revoke_error}`, "error");
      } else if (result.celery_revoke_requested) {
        toast.push("Job cancelado y Celery recibió revoke.", "success");
      } else {
        toast.push("Job marcado como cancelado; no había task id de Celery.", "success");
      }
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
          <div className="stack" style={{ gap: 2 }}>
            <h2>Jobs</h2>
            <span className="faint small">
              {asArray(jobs.data).length} resultados · live polling cada 4s
            </span>
          </div>
          <div className="row">
            <span className="field-icon faint" aria-hidden="true">
              <Icon name="filter" size={14} />
            </span>
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
            <button className="ghost small" onClick={() => jobs.refetch()} type="button">
              <Icon name="refresh" size={13} /> Refrescar
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
              {asArray(jobs.data).length === 0 && (
                <tr>
                  <td colSpan={6}>
                    <div className="empty-state">
                      <span className="empty-icon">
                        <Icon name="jobs" size={18} />
                      </span>
                      <strong>Sin jobs para este filtro</strong>
                      <span className="empty-msg">
                        Cambiá filtros o lanzá una acción desde el Dashboard.
                      </span>
                    </div>
                  </td>
                </tr>
              )}
              {asArray(jobs.data).map((job) => {
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
                        <button className="small" onClick={() => setSelectedJobId(job.id)} type="button">
                          <Icon name="search" size={12} /> Ver
                        </button>
                        <button
                          className="danger small"
                          onClick={() => cancel(job.id)}
                          disabled={terminal || cancelingJobId !== null}
                          type="button"
                        >
                          <Icon name="close" size={12} /> Cancelar
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
        {!selectedJobId && (
          <div className="empty-state">
            <span className="empty-icon">
              <Icon name="audit" size={18} />
            </span>
            <strong>Seleccioná un job</strong>
            <span className="empty-msg">
              Hacé click en <code>Ver</code> en cualquier fila para inspeccionar sus eventos en
              vivo.
            </span>
          </div>
        )}
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
                {asArray(events.data).length === 0 && (
                  <tr>
                    <td colSpan={5}>
                      <span className="muted small">Sin eventos registrados para este job.</span>
                    </td>
                  </tr>
                )}
                {asArray(events.data).map((event) => (
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
