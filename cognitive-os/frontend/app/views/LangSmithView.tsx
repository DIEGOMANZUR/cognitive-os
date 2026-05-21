"use client";

import { useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../lib/api";
import { asArray, errorMessage, statusClass } from "../lib/api";
import { EmptyState, ErrorPanel, Skeleton } from "../components/StatePrimitives";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type {
  LangSmithProject,
  LangSmithRun,
  LangSmithRunDetail,
  LangSmithStatus
} from "../lib/types";

export function LangSmithView({ client }: { client: ApiClient }) {
  const status = usePolledFetch<LangSmithStatus>(client, "/langsmith/status", 60000);
  const projects = usePolledFetch<LangSmithProject[]>(
    client,
    "/langsmith/projects",
    30000
  );
  const [project, setProject] = useState<string>("");
  const [errorOnly, setErrorOnly] = useState(false);

  useEffect(() => {
    if (!project && status.data?.project) setProject(status.data.project);
  }, [status.data, project]);

  const runsPath = useMemo(() => {
    const params = new URLSearchParams();
    if (project) params.set("project", project);
    if (errorOnly) params.set("error_only", "true");
    params.set("limit", "60");
    return `/langsmith/runs?${params.toString()}`;
  }, [project, errorOnly]);

  const runs = usePolledFetch<LangSmithRun[]>(client, runsPath, 8000);

  const [activeId, setActiveId] = useState<string | null>(null);
  const [detail, setDetail] = useState<LangSmithRunDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const toast = useToast();

  useEffect(() => {
    setDetail(null);
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      setLoadingDetail(true);
      try {
        const data = await client.get<LangSmithRunDetail>(`/langsmith/runs/${activeId}`);
        if (!cancelled) setDetail(data);
      } catch (caught) {
        if (!cancelled) toast.push(errorMessage(caught), "error");
      } finally {
        if (!cancelled) setLoadingDetail(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId, client, toast]);

  const langsmithUrl = useMemo(() => {
    const projectId = projects.data?.find((p) => p.name === project)?.id;
    if (!status.data?.endpoint) return null;
    const ui = status.data.endpoint.replace("api.smith.langchain.com", "smith.langchain.com");
    return projectId
      ? `${ui}/o/-/projects/p/${projectId}`
      : `${ui}/o/-/projects`;
  }, [projects.data, project, status.data]);

  return (
    <div className="stack">
      <section className="section">
        <div className="section-head">
          <h2>LangSmith · trazas en vivo</h2>
          <div className="row">
            <span
              className={status.data?.enabled ? "badge ok" : "badge warn"}
              title={status.data?.detail ?? ""}
            >
              {status.data?.enabled ? "tracing activo" : "tracing inactivo"}
            </span>
            {langsmithUrl && (
              <a className="badge info" href={langsmithUrl} target="_blank" rel="noreferrer">
                Abrir en LangSmith ↗
              </a>
            )}
          </div>
        </div>
        <p className="muted small">
          Las trazas se generan automáticamente desde cada LLM/Tool invocado por LangChain
          (Chat, DeepAgents research, Document Analysis). Si el ingest está bloqueado, los
          runs no aparecen pero el resto del sistema sigue operando — chequeá <code>/health/dashboard</code>.
        </p>
        <div className="row">
          <label className="stack" style={{ minWidth: 220 }}>
            <span className="muted small">Proyecto</span>
            <select value={project} onChange={(event) => setProject(event.target.value)}>
              {asArray(projects.data).map((option) => (
                <option key={option.id} value={option.name}>
                  {option.name}
                </option>
              ))}
              {project && !projects.data?.some((p) => p.name === project) && (
                <option value={project}>{project}</option>
              )}
            </select>
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={errorOnly}
              onChange={(event) => setErrorOnly(event.target.checked)}
            />
            <span>solo errores</span>
          </label>
          <button className="ghost" onClick={() => runs.refetch()} type="button">
            Refrescar
          </button>
        </div>
      </section>

      <div
        className="grid-2"
        style={{ gridTemplateColumns: "minmax(0, 1.2fr) minmax(0, 1.5fr)", gap: 14 }}
      >
        <section className="section" style={{ minHeight: 0 }}>
          <div className="section-head">
            <h2>Runs ({runs.data?.length ?? 0})</h2>
            {runs.error && <span className="badge danger">{runs.error}</span>}
          </div>
          <div className="table-wrap" style={{ maxHeight: "70vh" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Inicio</th>
                  <th>Nombre</th>
                  <th>Tipo</th>
                  <th>Estado</th>
                  <th>Latencia</th>
                </tr>
              </thead>
              <tbody>
                {runs.error && asArray(runs.data).length === 0 && (
                  <tr>
                    <td colSpan={5}>
                      <ErrorPanel error={runs.error} onRetry={() => void runs.refetch()} />
                    </td>
                  </tr>
                )}
                {runs.loading && asArray(runs.data).length === 0 && !runs.error && (
                  <tr>
                    <td colSpan={5}>
                      <Skeleton rows={4} />
                    </td>
                  </tr>
                )}
                {!runs.loading && !runs.error && asArray(runs.data).length === 0 && (
                  <tr>
                    <td colSpan={5}>
                      <EmptyState
                        icon="langsmith"
                        title="Sin runs todavía"
                        message="Cuando el orquestador disparé runs trazadas aparecerán aquí."
                      />
                    </td>
                  </tr>
                )}
                {asArray(runs.data).map((run) => (
                  <tr
                    key={run.id}
                    onClick={() => setActiveId(run.id)}
                    style={{
                      cursor: "pointer",
                      background:
                        activeId === run.id ? "var(--accent-soft)" : undefined
                    }}
                  >
                    <td className="small muted">
                      {run.start_time
                        ? new Date(run.start_time).toLocaleTimeString()
                        : "—"}
                    </td>
                    <td>
                      <strong>{run.name ?? "(sin nombre)"}</strong>
                    </td>
                    <td>
                      <span className="badge">{run.run_type ?? "?"}</span>
                    </td>
                    <td>
                      {run.error ? (
                        <span className="badge danger">error</span>
                      ) : run.status ? (
                        <span className={statusClass(run.status)}>{run.status}</span>
                      ) : (
                        <span className="muted small">—</span>
                      )}
                    </td>
                    <td>{run.latency_ms ? `${Math.round(run.latency_ms)} ms` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="section" style={{ minHeight: 0 }}>
          <div className="section-head">
            <h2>Detalle del run</h2>
            {activeId && (
              <code className="small">{activeId.slice(0, 8)}…</code>
            )}
          </div>
          {!activeId && <p className="muted small">Click en un run para ver inputs/outputs.</p>}
          {activeId && loadingDetail && <p className="muted small">Cargando…</p>}
          {detail && (
            <div className="stack" style={{ gap: 10 }}>
              <div className="row" style={{ gap: 6 }}>
                <span className="badge">{detail.run_type ?? "?"}</span>
                {detail.status && (
                  <span className={statusClass(detail.status)}>{detail.status}</span>
                )}
                {detail.total_tokens !== null && detail.total_tokens !== undefined && (
                  <span className="badge info">{detail.total_tokens} tokens</span>
                )}
                {detail.latency_ms && (
                  <span className="badge">{Math.round(detail.latency_ms)} ms</span>
                )}
              </div>
              {detail.error && (
                <div className="warn-box small">
                  <strong>Error:</strong>
                  <pre>{detail.error}</pre>
                </div>
              )}
              {detail.tags && detail.tags.length > 0 && (
                <div className="row" style={{ gap: 4 }}>
                  {detail.tags.map((tag) => (
                    <span key={tag} className="badge">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
              {detail.inputs && (
                <details open>
                  <summary>
                    <strong>Inputs</strong>
                  </summary>
                  <pre style={{ maxHeight: 240 }}>
                    {JSON.stringify(detail.inputs, null, 2)}
                  </pre>
                </details>
              )}
              {detail.outputs && (
                <details open>
                  <summary>
                    <strong>Outputs</strong>
                  </summary>
                  <pre style={{ maxHeight: 240 }}>
                    {JSON.stringify(detail.outputs, null, 2)}
                  </pre>
                </details>
              )}
              {detail.extra && (
                <details>
                  <summary className="muted small">Metadata extra</summary>
                  <pre style={{ maxHeight: 200 }}>
                    {JSON.stringify(detail.extra, null, 2)}
                  </pre>
                </details>
              )}
              {langsmithUrl && (
                <a
                  className="badge info"
                  href={`${langsmithUrl}/r/${detail.id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Ver run completo en LangSmith ↗
                </a>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
