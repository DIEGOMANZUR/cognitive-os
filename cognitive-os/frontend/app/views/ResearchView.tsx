"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type {
  ResearchEvent,
  ResearchRunRequestPayload,
  ResearchRunStatus,
  ResearchRunView,
  ResearchScoreView,
  ResearchSubtaskResultView,
  ResearchSubtaskView,
  ResearchSynthesisView
} from "../lib/types";

const TERMINAL_STATUSES = new Set<ResearchRunStatus>([
  "completed",
  "cancelled",
  "failed",
  "blocked"
]);

interface LiveState {
  status: ResearchRunStatus;
  subtasks: ResearchSubtaskView[];
  running: Set<string>;
  results: Map<string, ResearchSubtaskResultView>;
  synthesis: ResearchSynthesisView | null;
  score: ResearchScoreView | null;
  error: string | null;
}

function snapshotToLive(run: ResearchRunView): LiveState {
  const results = new Map<string, ResearchSubtaskResultView>();
  for (const result of run.results) results.set(result.subtask_id, result);
  return {
    status: run.status,
    subtasks: run.subtasks,
    running: new Set<string>(),
    results,
    synthesis: run.synthesis,
    score: run.score,
    error: run.error
  };
}

function emptyLive(): LiveState {
  return {
    status: "queued",
    subtasks: [],
    running: new Set<string>(),
    results: new Map<string, ResearchSubtaskResultView>(),
    synthesis: null,
    score: null,
    error: null
  };
}

export function ResearchView({ client }: { client: ApiClient }) {
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [maxSubtasks, setMaxSubtasks] = useState(3);
  const [timeBudget, setTimeBudget] = useState(120);
  const [webAllowed, setWebAllowed] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [live, setLive] = useState<LiveState>(() => emptyLive());
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const runs = usePolledFetch<ResearchRunView[]>(client, "/research/runs?limit=30", 5000);

  const closeStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStreaming(false);
  }, []);

  useEffect(() => closeStream, [closeStream]);

  const openStream = useCallback(
    async (runId: string, initialSnapshot?: ResearchRunView) => {
      closeStream();
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      setLive(initialSnapshot ? snapshotToLive(initialSnapshot) : emptyLive());

      try {
        await client.streamResearchEvents(
          runId,
          (event: ResearchEvent) => {
            setLive((prev) => reduceLive(prev, event));
          },
          controller.signal
        );
      } catch (caught) {
        if ((caught as Error).name !== "AbortError") {
          toast.push(errorMessage(caught), "error");
        }
      } finally {
        setStreaming(false);
        void runs.refetch();
      }
    },
    [client, closeStream, runs, toast]
  );

  const selectRun = useCallback(
    async (runId: string) => {
      setSelectedRunId(runId);
      // Fetch a fresh snapshot so historical runs render too.
      try {
        const snap = await client.get<ResearchRunView>(`/research/runs/${runId}`);
        if (TERMINAL_STATUSES.has(snap.status)) {
          // No streaming — just render the snapshot.
          closeStream();
          setLive(snapshotToLive(snap));
        } else {
          await openStream(runId, snap);
        }
      } catch (caught) {
        toast.push(errorMessage(caught), "error");
      }
    },
    [client, closeStream, openStream, toast]
  );

  const startRun = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed) {
      toast.push("Escribí una pregunta para investigar.", "warning");
      return;
    }
    try {
      const payload: ResearchRunRequestPayload = {
        query: trimmed,
        time_budget_seconds: timeBudget,
        max_subtasks: maxSubtasks,
        web_allowed: webAllowed
      };
      const run = await client.post<ResearchRunView>("/research/runs", payload);
      toast.push(`Run iniciado: ${run.run_id}`, "success");
      void runs.refetch();
      setSelectedRunId(run.run_id);
      void openStream(run.run_id, run);
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }, [client, openStream, query, runs, maxSubtasks, timeBudget, toast, webAllowed]);

  const cancelRun = useCallback(async () => {
    if (!selectedRunId) return;
    try {
      await client.post(`/research/runs/${selectedRunId}/cancel`, {});
      toast.push("Cancelación solicitada.", "warning");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }, [client, selectedRunId, toast]);

  const orderedSubtasks = useMemo(() => live.subtasks, [live.subtasks]);
  const isTerminal = TERMINAL_STATUSES.has(live.status);

  return (
    <section className="section">
      <div className="section-head">
        <h2>Investigación</h2>
        {/* Fase 72 I: ocultar el badge "queued" pre-run para no mentir. */}
        {(live.subtasks.length > 0 || live.error || live.synthesis) && (
          <span className={statusClass(live.status)}>{live.status}</span>
        )}
      </div>

      <div className="research-grid">
        <aside>
          <h3 className="muted small">Runs recientes</h3>
          <div className="research-run-list">
            {(runs.data ?? []).length === 0 && (
              <p className="muted small">Aún no hay runs.</p>
            )}
            {(runs.data ?? []).map((r) => (
              <button
                key={r.run_id}
                className={`research-run-item${r.run_id === selectedRunId ? " active" : ""}`}
                type="button"
                onClick={() => void selectRun(r.run_id)}
              >
                <span className={statusClass(r.status)}>{r.status}</span>
                <span className="small">{r.request.query.slice(0, 80)}</span>
                {r.finished_at && (
                  <span className="muted small">
                    {new Date(r.finished_at).toLocaleString()}
                  </span>
                )}
              </button>
            ))}
          </div>
        </aside>

        <div className="research-detail">
          <div className="section">
            <div className="section-head">
              <h3>Nueva investigación</h3>
              {streaming && (
                <button className="ghost" type="button" onClick={closeStream}>
                  Cerrar stream
                </button>
              )}
            </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
              <textarea
                rows={2}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Pregunta a investigar…"
                style={{ flex: 1, minWidth: 280 }}
              />
            </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
              <label className="muted small">
                Subtareas
                <input
                  type="number"
                  min={1}
                  max={4}
                  value={maxSubtasks}
                  onChange={(event) =>
                    setMaxSubtasks(Math.max(1, Math.min(4, Number(event.target.value) || 1)))
                  }
                  style={{ marginLeft: 8, width: 60 }}
                />
              </label>
              <label className="muted small">
                Tiempo (s)
                <input
                  type="number"
                  min={30}
                  max={600}
                  step={30}
                  value={timeBudget}
                  onChange={(event) =>
                    setTimeBudget(Math.max(30, Math.min(600, Number(event.target.value) || 30)))
                  }
                  style={{ marginLeft: 8, width: 80 }}
                />
              </label>
              <label className="muted small">
                <input
                  type="checkbox"
                  checked={webAllowed}
                  onChange={(event) => setWebAllowed(event.target.checked)}
                  style={{ marginRight: 6 }}
                />
                Permitir web
              </label>
              <button
                className="primary"
                type="button"
                onClick={() => void startRun()}
                disabled={streaming || !query.trim()}
              >
                Iniciar
              </button>
              {selectedRunId && !isTerminal && (
                <button
                  className="danger"
                  type="button"
                  onClick={() => void cancelRun()}
                  disabled={isTerminal}
                >
                  Cancelar run
                </button>
              )}
            </div>
          </div>

          {orderedSubtasks.length > 0 && (
            <div className="section">
              <div className="section-head">
                <h3>Plan ({orderedSubtasks.length} subtareas)</h3>
                {streaming && <span className="badge warn">streaming</span>}
              </div>
              <div className="research-subtasks">
                {orderedSubtasks.map((subtask) => (
                  <SubtaskCard
                    key={subtask.subtask_id}
                    subtask={subtask}
                    running={live.running.has(subtask.subtask_id)}
                    result={live.results.get(subtask.subtask_id) ?? null}
                  />
                ))}
              </div>
            </div>
          )}

          {live.synthesis && (
            <div className="section">
              <div className="section-head">
                <h3>Síntesis</h3>
                {live.score !== null && (
                  <span className="badge ok">score {live.score.score.toFixed(2)}</span>
                )}
              </div>
              <p className="research-answer">{live.synthesis.answer}</p>
              {live.synthesis.findings.length > 0 && (
                <>
                  <h4 className="muted small">Hallazgos</h4>
                  <ul className="research-findings">
                    {live.synthesis.findings.slice(0, 12).map((finding, idx) => (
                      <li key={idx}>{finding}</li>
                    ))}
                  </ul>
                </>
              )}
              {live.synthesis.citations.length > 0 && (
                <>
                  <h4 className="muted small">Citas</h4>
                  <div className="research-citations">
                    {live.synthesis.citations.slice(0, 10).map((c, idx) => (
                      <span key={idx}>
                        {c.title ? `${c.title} — ` : ""}
                        {c.url ?? c.doc_id ?? "(sin fuente)"}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {live.error && (
            <div className="warn-box">
              <strong>Error:</strong> {live.error}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function SubtaskCard({
  subtask,
  running,
  result
}: {
  subtask: ResearchSubtaskView;
  running: boolean;
  result: ResearchSubtaskResultView | null;
}) {
  let classSuffix = "";
  if (running) classSuffix = " is-running";
  else if (result?.status === "ok") classSuffix = " is-ok";
  else if (result) classSuffix = " is-failed";

  return (
    <div className={`research-subtask-card${classSuffix}`}>
      <div className="research-subtask-header">
        <span>{subtask.subtask_id}</span>
        {running && <span className="research-spinner" aria-label="ejecutando" />}
        {result && <span className={statusClass(result.status)}>{result.status}</span>}
      </div>
      <p className="small">{subtask.query}</p>
      {subtask.rationale && <p className="muted small">{subtask.rationale}</p>}
      {result?.answer && <p className="research-answer">{result.answer}</p>}
      {result?.findings && result.findings.length > 0 && (
        <ul className="research-findings">
          {result.findings.slice(0, 6).map((finding, idx) => (
            <li key={idx}>{finding}</li>
          ))}
        </ul>
      )}
      {result?.uncertainty_notes && result.uncertainty_notes.length > 0 && (
        <p className="muted small">{result.uncertainty_notes.join(" · ")}</p>
      )}
    </div>
  );
}

function reduceLive(prev: LiveState, event: ResearchEvent): LiveState {
  const payload = event.payload ?? {};
  switch (event.event) {
    case "run_started":
      return { ...prev, status: "researching" };
    case "plan_ready": {
      const subtasks = (payload.subtasks as ResearchSubtaskView[] | undefined) ?? [];
      return { ...prev, status: "researching", subtasks };
    }
    case "subtask_started": {
      const id = String(payload.subtask_id ?? "");
      if (!id) return prev;
      const running = new Set(prev.running);
      running.add(id);
      return { ...prev, running };
    }
    case "subtask_finished": {
      const result = payload.result as ResearchSubtaskResultView | undefined;
      if (!result) return prev;
      const running = new Set(prev.running);
      running.delete(result.subtask_id);
      const results = new Map(prev.results);
      results.set(result.subtask_id, result);
      return { ...prev, running, results };
    }
    case "synthesis_ready": {
      const synthesis = payload.synthesis as ResearchSynthesisView | undefined;
      return { ...prev, status: "synthesizing", synthesis: synthesis ?? null };
    }
    case "score_ready": {
      const score = payload.score as ResearchScoreView | undefined;
      return { ...prev, status: "scoring", score: score ?? null };
    }
    case "run_completed":
      return { ...prev, status: "completed" };
    case "run_cancelled":
      return { ...prev, status: "cancelled" };
    case "run_failed":
      return {
        ...prev,
        status: "failed",
        error: typeof payload.error === "string" ? payload.error : prev.error
      };
    case "run_blocked":
      return { ...prev, status: "blocked" };
    case "snapshot": {
      const view = payload as unknown as ResearchRunView;
      if (view && view.run_id) return snapshotToLive(view);
      return prev;
    }
    case "done":
      return prev;
    case "error":
      return { ...prev, error: event.detail ?? prev.error };
    default:
      return prev;
  }
}
