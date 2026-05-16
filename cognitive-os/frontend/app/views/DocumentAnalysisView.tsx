"use client";

import { useEffect, useState } from "react";

import type { ApiClient } from "../lib/api";
import { downloadBlob, errorMessage, statusClass } from "../lib/api";
import { useToast } from "../lib/toasts";
import type {
  DocumentAnalysisMode,
  DocumentAnalysisOutputFormat,
  DocumentAnalysisRunResponse,
  DocumentAnalysisStatusResponse
} from "../lib/types";

const MODE_OPTIONS: Array<{ id: DocumentAnalysisMode; label: string }> = [
  { id: "evidence_matrix", label: "Matriz evidencia" },
  { id: "timeline", label: "Timeline" },
  { id: "contradictions", label: "Contradicciones" },
  { id: "full_report", label: "Full report" },
  { id: "legal_draft_support", label: "Soporte borrador" },
  { id: "case_summary", label: "Resumen caso" }
];

const FORMAT_OPTIONS: Array<{ id: DocumentAnalysisOutputFormat; label: string }> = [
  { id: "json", label: "JSON" },
  { id: "markdown", label: "Markdown" },
  { id: "csv", label: "CSV (matriz/timeline/contra.)" },
  { id: "docx", label: "DOCX" }
];

const DOWNLOAD_OPTIONS: Array<{ filename: string; suffix: string }> = [
  { filename: "report.md", suffix: "download/markdown" },
  { filename: "result.json", suffix: "download/json" },
  { filename: "report.docx", suffix: "download/docx" },
  { filename: "evidence_matrix.csv", suffix: "download/csv/evidence_matrix" },
  { filename: "timeline.csv", suffix: "download/csv/timeline" },
  { filename: "contradictions.csv", suffix: "download/csv/contradictions" }
];

function parseDocIds(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function DocumentAnalysisView({ client }: { client: ApiClient }) {
  const [query, setQuery] = useState("");
  const [docIds, setDocIds] = useState("");
  const [threadId, setThreadId] = useState("manual-panel");
  const [modes, setModes] = useState<DocumentAnalysisMode[]>(["evidence_matrix"]);
  const [outputFormats, setOutputFormats] = useState<DocumentAnalysisOutputFormat[]>([
    "json",
    "markdown",
    "csv"
  ]);
  const [response, setResponse] = useState<DocumentAnalysisRunResponse | null>(null);
  const [polledStatus, setPolledStatus] = useState<DocumentAnalysisStatusResponse | null>(null);
  const toast = useToast();
  const parsedDocIds = parseDocIds(docIds);
  const canRun = query.trim().length > 0 && parsedDocIds.length > 0 && modes.length > 0;
  const generatedFiles = polledStatus?.generated_files ?? [];
  const availableDownloads = DOWNLOAD_OPTIONS.filter((option) =>
    generatedFiles.includes(option.filename)
  );

  function toggle<T>(value: T, list: T[], setter: (next: T[]) => void) {
    setter(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  async function run() {
    const parsed = parseDocIds(docIds);
    const trimmedQuery = query.trim();
    if (!trimmedQuery || parsed.length === 0 || modes.length === 0) {
      toast.push("Ingresa una consulta, al menos un doc_id válido y un modo de análisis.", "error");
      return;
    }

    setPolledStatus(null);
    setResponse(null);
    try {
      const result = await client.post<DocumentAnalysisRunResponse>("/document-analysis/run", {
        task_id: crypto.randomUUID(),
        thread_id: threadId.trim() || "manual-panel",
        user_id: null,
        case_id: null,
        doc_ids: parsed,
        query: trimmedQuery,
        modes,
        output_formats: outputFormats.length ? outputFormats : ["json", "markdown"]
      });
      setResponse(result);
      toast.push(`Análisis encolado: ${result.task_id.slice(0, 8)}…`, "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }

  useEffect(() => {
    if (!response?.task_id) return;
    let cancelled = false;
    let elapsed = 0;
    const poll = async () => {
      if (cancelled) return;
      try {
        const status = await client.get<DocumentAnalysisStatusResponse>(
          `/document-analysis/${response.task_id}`
        );
        if (!cancelled) setPolledStatus(status);
      } catch {
        // Result not yet written; keep polling
      }
      elapsed += 5;
      if (!cancelled && elapsed < 60 * 30) {
        setTimeout(() => void poll(), 5000);
      }
    };
    void poll();
    return () => {
      cancelled = true;
    };
  }, [client, response?.task_id]);

  async function handleDownload(suffix: string, filename: string) {
    if (!response?.task_id) return;
    try {
      const blob = await client.download(`/document-analysis/${response.task_id}/${suffix}`);
      await downloadBlob(blob, filename);
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }

  return (
    <div className="grid-2" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.2fr)" }}>
      <section className="section stack">
        <div className="section-head">
          <h2>Document Analysis</h2>
          <span className="muted small">Evidence Ledger + matriz + timeline + contradicciones</span>
        </div>
        <input
          placeholder="thread_id"
          value={threadId}
          onChange={(event) => setThreadId(event.target.value)}
        />
        <textarea
          placeholder="doc_ids (UUIDs separados por coma)"
          value={docIds}
          onChange={(event) => setDocIds(event.target.value)}
        />
        <textarea
          placeholder="Pregunta o instrucción para el análisis"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div>
          <span className="muted small">Modos:</span>
          <div className="toolbar">
            {MODE_OPTIONS.map((mode) => (
              <label key={mode.id} className="check">
                <input
                  type="checkbox"
                  checked={modes.includes(mode.id)}
                  onChange={() => toggle(mode.id, modes, setModes)}
                />
                <span>{mode.label}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <span className="muted small">Formatos:</span>
          <div className="toolbar">
            {FORMAT_OPTIONS.map((format) => (
              <label key={format.id} className="check">
                <input
                  type="checkbox"
                  checked={outputFormats.includes(format.id)}
                  onChange={() => toggle(format.id, outputFormats, setOutputFormats)}
                />
                <span>{format.label}</span>
              </label>
            ))}
          </div>
        </div>
        <button className="primary" disabled={!canRun} onClick={run} type="button">
          Ejecutar
        </button>
      </section>

      <section className="section stack">
        <div className="section-head">
          <h2>Resultado</h2>
          {response && (
            <span className="muted small">
              task <code>{response.task_id.slice(0, 8)}…</code>
            </span>
          )}
        </div>
        {!response && <p className="muted small">Sin análisis solicitado.</p>}
        {response && (
          <>
            <p>
              status:{" "}
              <span className={statusClass(response.status)}>{response.status}</span>
              {response.job_id && (
                <>
                  {" · "}job_id: <code>{response.job_id.slice(0, 8)}…</code>
                </>
              )}
            </p>
            {polledStatus ? (
              <>
                <p>
                  análisis:{" "}
                  <span className={statusClass(polledStatus.status)}>{polledStatus.status}</span>
                  {polledStatus.human_review_required && (
                    <>
                      {" "}· <span className="badge warn">requiere revisión humana</span>
                    </>
                  )}
                </p>
                {polledStatus.warnings.length > 0 && (
                  <>
                    <strong>Advertencias</strong>
                    <ul className="small">
                      {polledStatus.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </>
                )}
                <strong>Archivos generados</strong>
                {generatedFiles.length > 0 ? (
                  <ul className="small">
                    {generatedFiles.map((file) => (
                      <li key={file}>
                        <code>{file}</code>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted small">El backend no reportó archivos exportados.</p>
                )}
                {availableDownloads.length > 0 ? (
                  <div className="toolbar">
                    {availableDownloads.map((option) => (
                      <button
                        key={option.filename}
                        onClick={() => handleDownload(option.suffix, option.filename)}
                        type="button"
                      >
                        {option.filename}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="muted small">
                    Las descargas se habilitan solo para archivos generados por el backend.
                  </p>
                )}
              </>
            ) : (
              <p className="muted">Esperando que Celery escriba el resultado…</p>
            )}
          </>
        )}
      </section>
    </div>
  );
}
