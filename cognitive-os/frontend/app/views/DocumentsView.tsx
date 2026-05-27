"use client";

import { useState } from "react";

import type { ApiClient } from "../lib/api";
import { asArray, errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { DocumentChunk, DocumentSummary, IngestResponse } from "../lib/types";

export function DocumentsView({ client }: { client: ApiClient }) {
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const documents = usePolledFetch<DocumentSummary[]>(client, "/documents?limit=100", 8000);
  const [openId, setOpenId] = useState<string | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[] | null>(null);
  const [chunksLoading, setChunksLoading] = useState(false);
  const toast = useToast();
  const trimmedPath = path.trim();
  const canIngest = trimmedPath.length > 0;
  const liveDocuments = asArray(documents.data);

  async function ingest() {
    const documentPath = path.trim();
    if (!documentPath) {
      toast.push("Ingresá una ruta de PDF válida.", "error");
      return;
    }

    setBusy(true);
    try {
      const result = await client.post<IngestResponse>("/documents/ingest", {
        document_path: documentPath
      });
      toast.push(`Ingesta encolada — job ${result.job_id.slice(0, 8)}…`, "success");
      setPath("");
      void documents.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  async function expand(documentId: string) {
    if (openId === documentId) {
      setOpenId(null);
      setChunks(null);
      return;
    }
    setOpenId(documentId);
    setChunks(null);
    setChunksLoading(true);
    try {
      const data = await client.get<DocumentChunk[]>(`/documents/${documentId}/chunks?limit=50`);
      setChunks(data);
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setChunksLoading(false);
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.push("Copiado.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="section-head">
          <h2>Ingestar documento</h2>
          <button className="ghost" onClick={() => documents.refetch()} type="button">
            Refrescar
          </button>
        </div>
        <p className="muted small">
          Ruta absoluta del PDF accesible para el backend. El job extrae texto/OCR, chunks,
          embeddings (Gemini), entidades y los inserta en Postgres + Weaviate (+ Neo4j si está
          disponible).
        </p>
        <div className="row">
          <input
            placeholder="/ruta/al/documento.pdf"
            value={path}
            onChange={(event) => setPath(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !busy && canIngest) ingest();
            }}
          />
          <button className="primary" disabled={busy || !canIngest} onClick={ingest} type="button">
            Ingestar
          </button>
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Biblioteca ({liveDocuments.length})</h2>
          <div className="row">
            {documents.error && <span className="badge danger">{documents.error}</span>}
            <button
              className="ghost"
              onClick={() => void documents.refetch()}
              type="button"
              aria-label="Refrescar biblioteca de documentos"
            >
              Refrescar
            </button>
          </div>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>doc_id</th>
                <th>Título / ruta</th>
                <th>Estado</th>
                <th>Páginas</th>
                <th>Chunks</th>
                <th>Creado</th>
                <th>SHA-256</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {liveDocuments.length === 0 ? (
                <DocumentsStatusRow
                  state={documents.error ? "error" : documents.loading ? "loading" : "empty"}
                  errorMessage={documents.error}
                  onRetry={() => void documents.refetch()}
                />
              ) : (
                liveDocuments.map((document) => (
                  <Row
                    key={document.id}
                    document={document}
                    open={openId === document.id}
                    chunks={openId === document.id ? chunks : null}
                    loading={openId === document.id && chunksLoading}
                    onToggle={() => expand(document.id)}
                    onCopy={copy}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

/**
 * Status row shown when the document library is empty, loading, or has
 * errored. We keep the full eight-column table structure (matching the
 * data rows) so the layout stays consistent across states — exactly the
 * pattern used by Google Drive, Linear and Notion when a list view has
 * no items yet. The single action button doubles as Retry (error) or
 * an inert affordance (loading/empty) and toggles an inline detail
 * panel that explains the current state.
 */
function DocumentsStatusRow({
  state,
  errorMessage,
  onRetry
}: {
  state: "error" | "loading" | "empty";
  errorMessage: string | null;
  onRetry: () => void;
}) {
  const [open, setOpen] = useState(false);
  const copy = {
    error: {
      title: "No se pudo cargar la biblioteca",
      detail:
        errorMessage ??
        "La API de documentos no respondió. Reintentá la carga o verificá la conexión al backend.",
      badge: "error",
      badgeClass: "badge danger",
      actionLabel: "Reintentar"
    },
    loading: {
      title: "Sincronizando biblioteca…",
      detail:
        "Consultando los documentos indexados. Esta lectura suele tardar menos de un segundo.",
      badge: "cargando",
      badgeClass: "badge",
      actionLabel: "Detalle"
    },
    empty: {
      title: "Aún no hay documentos ingestados",
      detail:
        "Subí un PDF desde Ingestar documento para empezar. Cada documento se segmenta en chunks indexables.",
      badge: "vacío",
      badgeClass: "badge configured",
      actionLabel: "Detalle"
    }
  }[state];
  return (
    <>
      <tr aria-label={`Documents ${state} row`}>
        <td>
          <code>—</code>
        </td>
        <td>
          <strong>{copy.title}</strong>
          <br />
          <span className="muted small">{copy.detail}</span>
        </td>
        <td>
          <span className={copy.badgeClass}>{copy.badge}</span>
        </td>
        <td>0</td>
        <td>0</td>
        <td className="small muted">—</td>
        <td>
          <code className="small">—</code>
        </td>
        <td>
          <button
            aria-label={open ? "Cerrar detalle" : copy.actionLabel}
            onClick={() => {
              setOpen((value) => !value);
              if (state === "error") onRetry();
            }}
            type="button"
          >
            {open ? "▾ cerrar detalle" : `▸ ${copy.actionLabel.toLowerCase()}`}
          </button>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={8}>
            <section
              aria-label="Document library status"
              className="document-detail-panel"
            >
              <div className="section-head">
                <div>
                  <h3>{copy.title}</h3>
                  <p className="muted small">{copy.detail}</p>
                </div>
                <span className={copy.badgeClass}>{copy.badge}</span>
              </div>
              {state === "error" && (
                <div className="row">
                  <button onClick={onRetry} type="button">
                    Reintentar carga
                  </button>
                </div>
              )}
            </section>
          </td>
        </tr>
      )}
    </>
  );
}

function Row({
  document,
  open,
  chunks,
  loading,
  onToggle,
  onCopy
}: {
  document: DocumentSummary;
  open: boolean;
  chunks: DocumentChunk[] | null;
  loading: boolean;
  onToggle: () => void;
  onCopy: (value: string) => void;
}) {
  return (
    <>
      <tr>
        <td>
          <code onClick={() => onCopy(document.id)} role="button">
            {document.id.slice(0, 8)}…
          </code>
        </td>
        <td>
          <strong>{document.title ?? "—"}</strong>
          <br />
          <span className="muted small">{document.source_path}</span>
        </td>
        <td>
          <span className={statusClass(document.status)}>{document.status}</span>
        </td>
        <td>{document.page_count}</td>
        <td>{document.chunk_count}</td>
        <td className="small muted">{new Date(document.created_at).toLocaleString()}</td>
        <td>
          <code className="small">{document.sha256.slice(0, 12)}…</code>
        </td>
        <td>
          <button
            aria-label={open ? "Cerrar document detail view" : "Abrir document detail view"}
            onClick={onToggle}
            type="button"
          >
            {open ? "▾ chunks / cerrar detalle" : "▸ chunks / abrir detalle"}
          </button>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={8}>
            <section
              aria-label="Document detail view"
              className="document-detail-panel"
              data-testid="document-detail-view"
            >
              <div className="section-head">
                <div>
                  <h3>Document detail view</h3>
                  <p className="muted small">
                    Vista read-only del documento seleccionado y sus chunks indexados.
                  </p>
                </div>
                <span className={statusClass(document.status)}>{document.status}</span>
              </div>
              <div className="grid-3">
                <div className="metric-card">
                  <span className="metric-label">Documento</span>
                  <strong>{document.title ?? document.source_path}</strong>
                  <code className="small">{document.id}</code>
                </div>
                <div className="metric-card">
                  <span className="metric-label">Páginas</span>
                  <span className="metric-value">{document.page_count}</span>
                </div>
                <div className="metric-card">
                  <span className="metric-label">Chunks</span>
                  <span className="metric-value">{document.chunk_count}</span>
                </div>
              </div>
              {loading && <p className="muted small">Cargando chunks…</p>}
              {!loading && chunks && chunks.length === 0 && (
                <p className="muted small">Sin chunks indexados.</p>
              )}
              {!loading && chunks && chunks.length > 0 && (
                <div className="stack" style={{ gap: 6, maxHeight: 360, overflow: "auto" }}>
                  {chunks.map((chunk) => (
                    <div key={chunk.chunk_id} className="metric-card" style={{ minHeight: 0 }}>
                      <div className="row">
                        <code className="small">{chunk.chunk_id}</code>
                        <span className="badge">
                          páginas {chunk.page_start}-{chunk.page_end}
                        </span>
                        <button
                          className="ghost"
                          onClick={() => onCopy(chunk.text)}
                          type="button"
                        >
                          ⎘ texto
                        </button>
                      </div>
                      <p className="small">{chunk.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </td>
        </tr>
      )}
    </>
  );
}
