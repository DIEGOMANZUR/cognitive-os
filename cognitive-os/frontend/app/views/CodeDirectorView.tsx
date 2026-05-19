"use client";

import { useCallback, useRef, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type {
  CodeAdapterChoice,
  CodeBuildCreateResponse,
  CodeBuildEvent,
  CodeBuildPlan,
  PublicConfig
} from "../lib/types";

const ADAPTERS: { value: CodeAdapterChoice; label: string }[] = [
  { value: "claude_code", label: "Claude Code CLI" },
  { value: "codex", label: "Codex CLI" },
  { value: "kimi", label: "Kimi CLI" },
  { value: "deepagent", label: "DeepAgents (in-process)" }
];

const TERMINAL = new Set(["completed", "failed", "cancelled", "rejected"]);

interface TimelineEntry {
  kind: string;
  status?: string;
  message?: string | null;
  at: number;
}

export function CodeDirectorView({ client }: { client: ApiClient }) {
  const toast = useToast();
  const config = usePolledFetch<PublicConfig>(client, "/config/public", 60000);
  const sandboxEnabled = config.data?.enable_openshell_sandbox ?? false;
  const [objective, setObjective] = useState("");
  const [notes, setNotes] = useState("");
  const [adapter, setAdapter] = useState<CodeAdapterChoice>("claude_code");
  const [model, setModel] = useState("claude-opus-4-7");
  const [maxRuntime, setMaxRuntime] = useState(120);
  const [maxCalls, setMaxCalls] = useState(200);
  const [maxCostUsd, setMaxCostUsd] = useState<string>("");
  const [runTestsInSandbox, setRunTestsInSandbox] = useState(false);

  const [plan, setPlan] = useState<CodeBuildPlan | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [approvalId, setApprovalId] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [buildStatus, setBuildStatus] = useState<string>("idle");
  const [submitting, setSubmitting] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const closeStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStreaming(false);
  }, []);

  const submit = useCallback(async () => {
    if (objective.trim().length < 10) {
      toast.push("El objetivo debe tener al menos 10 caracteres.", "warning");
      return;
    }
    setSubmitting(true);
    setPlan(null);
    setTimeline([]);
    setBuildStatus("planning");
    try {
      const budget: Record<string, unknown> = {
        max_runtime_minutes: maxRuntime,
        max_total_llm_calls: maxCalls
      };
      const cost = maxCostUsd.trim();
      if (cost) budget.max_total_cost_usd = Number(cost);
      const body = {
        objective: objective.trim(),
        notes: notes.trim() || null,
        adapter_preference: { default_adapter: adapter, default_model: model || null },
        budget,
        run_tests_in_sandbox: runTestsInSandbox
      };
      const res = await client.post<CodeBuildCreateResponse>("/code-director/run", body);
      setPlan(res.plan);
      setJobId(res.job_id);
      setApprovalId(res.approval_id);
      setBuildStatus("awaiting_plan_approval");
      toast.push(
        `Plan listo (${res.plan.subtasks.length} subtareas). Aprueba la solicitud para arrancar — no se gasta nada hasta entonces.`,
        "success"
      );
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
      setBuildStatus("idle");
    } finally {
      setSubmitting(false);
    }
  }, [
    adapter,
    client,
    maxCalls,
    maxCostUsd,
    maxRuntime,
    model,
    notes,
    objective,
    runTestsInSandbox,
    toast
  ]);

  const watchBuild = useCallback(async () => {
    if (!jobId) return;
    closeStream();
    const controller = new AbortController();
    abortRef.current = controller;
    setStreaming(true);
    setTimeline([]);
    try {
      await client.streamCodeBuildEvents(
        jobId,
        (raw: Record<string, unknown>) => {
          const ev = raw as CodeBuildEvent;
          if (ev.event === "snapshot" && ev.status) {
            setBuildStatus(ev.status);
            return;
          }
          if (ev.event === "done") return;
          setTimeline((prev) => [
            ...prev,
            {
              kind: ev.event,
              status: ev.status,
              message: ev.message,
              at: Date.now()
            }
          ]);
          if (ev.status && TERMINAL.has(ev.status)) {
            setBuildStatus(ev.status);
          }
        },
        controller.signal
      );
    } catch (caught) {
      if ((caught as Error).name !== "AbortError") {
        toast.push(errorMessage(caught), "error");
      }
    } finally {
      setStreaming(false);
    }
  }, [client, closeStream, jobId, toast]);

  const downloadArtifact = useCallback(async () => {
    if (!jobId) return;
    try {
      const blob = await client.download(`/code-director/${jobId}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `code-build-${jobId.slice(0, 8)}.tar.gz`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }, [client, jobId, toast]);

  return (
    <section className="section">
      <div className="section-head">
        <h2>Code Director</h2>
        <span className={statusClass(buildStatus)}>{buildStatus}</span>
      </div>

      <p className="muted small">
        Describe la app. El director arma un plan, lo somete a aprobación humana
        y, al aprobarla, delega cada subtarea al coding agent que elijas. No se
        gasta ningún token hasta que apruebes el plan.
      </p>

      <div className="section">
        <div className="section-head">
          <h3>Objetivo</h3>
        </div>
        <textarea
          rows={5}
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          placeholder="Ej: app con backend FastAPI, dos RAGs (transacciones + PDFs), frontend Next.js con shadcn, auth JWT, tests pytest+vitest..."
          style={{ width: "100%" }}
        />
        <textarea
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notas opcionales (convenciones, estilo, restricciones)"
          style={{ width: "100%", marginTop: 8 }}
        />
        <div className="row" style={{ flexWrap: "wrap", gap: 12, marginTop: 8 }}>
          <label className="muted small">
            Coding agent
            <select
              value={adapter}
              onChange={(e) => setAdapter(e.target.value as CodeAdapterChoice)}
              style={{ marginLeft: 8 }}
            >
              {ADAPTERS.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>
          <label className="muted small">
            Modelo
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="claude-opus-4-7"
              style={{ marginLeft: 8, width: 180 }}
            />
          </label>
          <label className="muted small">
            Máx min
            <input
              type="number"
              min={1}
              max={1440}
              value={maxRuntime}
              onChange={(e) => setMaxRuntime(Number(e.target.value) || 120)}
              style={{ marginLeft: 8, width: 80 }}
            />
          </label>
          <label className="muted small">
            Máx llamadas
            <input
              type="number"
              min={1}
              max={5000}
              value={maxCalls}
              onChange={(e) => setMaxCalls(Number(e.target.value) || 200)}
              style={{ marginLeft: 8, width: 90 }}
            />
          </label>
          <label className="muted small">
            Máx USD
            <input
              type="number"
              min={0}
              step="0.5"
              value={maxCostUsd}
              onChange={(e) => setMaxCostUsd(e.target.value)}
              placeholder="opcional"
              style={{ marginLeft: 8, width: 90 }}
            />
          </label>
          <label
            className="muted small"
            title={
              sandboxEnabled
                ? ""
                : "ENABLE_OPENSHELL_SANDBOX=false en .env — sandbox no disponible."
            }
            style={{ opacity: sandboxEnabled ? 1 : 0.55 }}
          >
            <input
              type="checkbox"
              checked={sandboxEnabled && runTestsInSandbox}
              disabled={!sandboxEnabled}
              onChange={(e) => setRunTestsInSandbox(e.target.checked)}
              style={{ marginRight: 6 }}
            />
            Probar en sandbox{sandboxEnabled ? "" : " (off)"}
          </label>
          <button className="primary" onClick={submit} disabled={submitting} type="button">
            {submitting ? "Planificando…" : "Planificar build"}
          </button>
        </div>
      </div>

      {plan && (
        <div className="section">
          <div className="section-head">
            <h3>Plan ({plan.subtasks.length} subtareas)</h3>
            <span className="muted small">
              ~{plan.estimated_runtime_minutes} min · ~{plan.estimated_calls} llamadas
              {plan.estimated_cost_usd != null ? ` · ~$${plan.estimated_cost_usd}` : ""}
            </span>
          </div>
          {approvalId && (
            <div className="warn-box">
              <strong>Acción requerida:</strong> aprueba la solicitud{" "}
              <code>{approvalId.slice(0, 8)}</code> en la pestaña{" "}
              <em>Aprobaciones</em> para arrancar el build. El director no gasta
              tokens hasta que apruebes.
            </div>
          )}
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Rol</th>
                  <th>Agent</th>
                  <th>Modelo</th>
                  <th>Descripción</th>
                  <th>Depende de</th>
                </tr>
              </thead>
              <tbody>
                {plan.subtasks.map((s) => (
                  <tr key={s.subtask_id}>
                    <td>{s.subtask_id}</td>
                    <td>{s.role}</td>
                    <td>{s.adapter}</td>
                    <td>{s.model ?? "—"}</td>
                    <td className="small">{s.title}</td>
                    <td className="small">{s.depends_on.join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small" style={{ marginTop: 8 }}>
            {plan.rationale}
          </p>
          <div className="row" style={{ gap: 8, marginTop: 8 }}>
            <button
              className="ghost"
              onClick={watchBuild}
              disabled={streaming || !jobId}
              type="button"
            >
              {streaming ? "Siguiendo build…" : "Seguir build (tras aprobar)"}
            </button>
            {TERMINAL.has(buildStatus) && buildStatus !== "rejected" && (
              <button className="primary" onClick={downloadArtifact} type="button">
                Descargar tar.gz
              </button>
            )}
            {streaming && (
              <button className="ghost" onClick={closeStream} type="button">
                Cerrar stream
              </button>
            )}
          </div>
        </div>
      )}

      {timeline.length > 0 && (
        <div className="section">
          <div className="section-head">
            <h3>Timeline del build</h3>
            <span className={statusClass(buildStatus)}>{buildStatus}</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Evento</th>
                  <th>Estado</th>
                  <th>Mensaje</th>
                </tr>
              </thead>
              <tbody>
                {timeline.map((t, idx) => (
                  <tr key={idx}>
                    <td className="small">{t.kind}</td>
                    <td>
                      {t.status ? (
                        <span className={statusClass(t.status)}>{t.status}</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="small">{t.message ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
