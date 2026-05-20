"use client";

import { useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { DeepAgentMemoryProposal } from "../lib/types";

type MemoryScope = "user" | "global" | "case" | "thread" | "agent";

const MEMORY_SCOPES: MemoryScope[] = ["user", "global", "case", "thread", "agent"];

type RecipeStep = {
  step?: number;
  tool?: string;
  purpose?: string;
  input_pattern?: string;
};

type RecipePayload = {
  recipe?: {
    title?: string;
    summary?: string;
    steps?: RecipeStep[];
    estimated_runtime_seconds?: number;
    tags?: string[];
  };
  job_id?: string;
  job_type?: string;
  tool_call_count?: number;
  duration_seconds?: number;
};

function readRecipePayload(proposal: DeepAgentMemoryProposal): RecipePayload | null {
  // Fase 78 returns the structured recipe at the proposal's top-level
  // `payload`. Older proposal rows wrote it under `metadata.payload`, so
  // fall back there to avoid breaking the UI mid-migration.
  const direct = proposal.payload;
  if (direct && typeof direct === "object" && "recipe" in direct) {
    return direct as RecipePayload;
  }
  const meta = proposal.metadata;
  if (meta && typeof meta === "object" && "payload" in meta) {
    const nested = (meta as Record<string, unknown>).payload;
    if (nested && typeof nested === "object") {
      return nested as RecipePayload;
    }
  }
  return null;
}

export function MemoryView({ client }: { client: ApiClient }) {
  const [scope, setScope] = useState<MemoryScope>("user");
  const memoryPath = `/deepagents/memory?scope=${encodeURIComponent(scope)}`;
  const memory = usePolledFetch<Record<string, unknown>[]>(client, memoryPath, 12000);
  const proposals = usePolledFetch<DeepAgentMemoryProposal[]>(
    client,
    "/deepagents/memory/proposals",
    10000
  );
  const recipes = usePolledFetch<DeepAgentMemoryProposal[]>(
    client,
    "/deepagents/memory/recipes",
    15000
  );
  const [exported, setExported] = useState<unknown>(null);
  const [decidingProposalId, setDecidingProposalId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [consolidating, setConsolidating] = useState(false);
  const [extractingRecipes, setExtractingRecipes] = useState(false);
  const toast = useToast();

  useEffect(() => {
    setExported(null);
  }, [scope]);

  const pendingRecipes = useMemo<DeepAgentMemoryProposal[]>(
    () => (recipes.data ?? []).filter((p) => p.status === "pending"),
    [recipes.data]
  );

  async function approve(id: string) {
    if (decidingProposalId) return;
    setDecidingProposalId(id);
    try {
      await client.post(`/deepagents/memory/proposals/${id}/approve`, {});
      toast.push("Propuesta aprobada.", "success");
      void proposals.refetch();
      void recipes.refetch();
      void memory.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setDecidingProposalId(null);
    }
  }

  async function reject(id: string) {
    if (decidingProposalId) return;
    setDecidingProposalId(id);
    try {
      await client.post(`/deepagents/memory/proposals/${id}/reject`, {
        reason: "Rejected from panel"
      });
      toast.push("Propuesta rechazada.", "warning");
      void proposals.refetch();
      void recipes.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setDecidingProposalId(null);
    }
  }

  async function exportMemory() {
    if (exporting) return;
    setExporting(true);
    setExported(null);
    try {
      const data = await client.post<unknown>("/deepagents/memory/export", { scope });
      setExported(data);
      toast.push("Memoria exportada.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setExporting(false);
    }
  }

  async function consolidate() {
    if (consolidating) return;
    setConsolidating(true);
    try {
      await client.post("/deepagents/memory/consolidate/run", {});
      toast.push("Consolidación encolada.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setConsolidating(false);
    }
  }

  async function extractRecipesNow() {
    if (extractingRecipes) return;
    setExtractingRecipes(true);
    try {
      await client.post("/deepagents/memory/recipes/extract-now", {});
      toast.push("Extractor de recetas encolado.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setExtractingRecipes(false);
    }
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="section-head">
          <h2>DeepAgents Memory</h2>
          <div className="row">
            <select value={scope} onChange={(event) => setScope(event.target.value as MemoryScope)}>
              {MEMORY_SCOPES.map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
            <button disabled={exporting} onClick={exportMemory} type="button">
              {exporting ? "Exportando…" : "Exportar scope"}
            </button>
            <button className="primary" disabled={consolidating} onClick={consolidate} type="button">
              {consolidating ? "Encolando…" : "Consolidar ahora"}
            </button>
            <button
              className="ghost"
              onClick={() => {
                void memory.refetch();
                void proposals.refetch();
                void recipes.refetch();
              }}
              type="button"
            >
              Refrescar
            </button>
          </div>
        </div>
        <div className="grid-2">
          <div className="stack">
            <h3>
              Memoria activa · {scope} ({(memory.data ?? []).length})
            </h3>
            <pre style={{ maxHeight: 320 }}>
              {memory.data ? JSON.stringify(memory.data, null, 2) : "Cargando…"}
            </pre>
          </div>
          <div className="stack">
            <h3>Propuestas pendientes ({(proposals.data ?? []).length})</h3>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Agente</th>
                    <th>Scope</th>
                    <th>Contenido</th>
                    <th>Estado</th>
                    <th>Decisión</th>
                  </tr>
                </thead>
                <tbody>
                  {(proposals.data ?? []).length === 0 && (
                    <tr>
                      <td colSpan={5} className="muted">
                        Sin propuestas pendientes.
                      </td>
                    </tr>
                  )}
                  {(proposals.data ?? []).map((proposal) => (
                    <tr key={proposal.proposal_id}>
                      <td>{proposal.proposed_by_agent}</td>
                      <td>{proposal.scope}</td>
                      <td className="small">{proposal.proposed_content}</td>
                      <td>
                        <span className={statusClass(proposal.status)}>{proposal.status}</span>
                      </td>
                      <td>
                        <div className="row">
                          <button
                            className="primary"
                            disabled={proposal.status !== "pending" || decidingProposalId !== null}
                            onClick={() => approve(proposal.proposal_id)}
                            type="button"
                          >
                            Aprobar
                          </button>
                          <button
                            className="danger"
                            disabled={proposal.status !== "pending" || decidingProposalId !== null}
                            onClick={() => reject(proposal.proposal_id)}
                            type="button"
                          >
                            Rechazar
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      {/* Fase 78 — Recetas propuestas por el extractor (kind=procedure). */}
      <section className="section" data-testid="recipe-proposals-section">
        <div className="section-head">
          <h2>Recetas propuestas ({pendingRecipes.length})</h2>
          <div className="row">
            <button
              className="primary"
              disabled={extractingRecipes}
              onClick={extractRecipesNow}
              type="button"
            >
              {extractingRecipes ? "Encolando…" : "Extraer ahora"}
            </button>
            <button
              className="ghost"
              onClick={() => {
                void recipes.refetch();
              }}
              type="button"
            >
              Refrescar
            </button>
          </div>
        </div>
        <p className="muted small">
          Distiladas automáticamente de jobs exitosos con ≥5 tool calls. Aprueba para
          materializarlas como memoria activa <code>kind=procedure</code>.
        </p>
        {recipes.data === undefined && <p className="muted">Cargando…</p>}
        {pendingRecipes.length === 0 && recipes.data !== undefined && (
          <p className="muted small">
            Sin recetas pendientes. El extractor corre cada 30 min sobre jobs nuevos.
          </p>
        )}
        <div className="stack">
          {pendingRecipes.map((proposal) => {
            const payload = readRecipePayload(proposal);
            const recipe = payload?.recipe ?? {};
            const steps = recipe.steps ?? [];
            return (
              <article
                key={proposal.proposal_id}
                className="card"
                data-testid="recipe-proposal-card"
              >
                <header className="row" style={{ justifyContent: "space-between" }}>
                  <div>
                    <strong>{recipe.title ?? "Receta sin título"}</strong>
                    <span className="muted small" style={{ marginLeft: 8 }}>
                      {proposal.proposed_by_agent} · {payload?.tool_call_count ?? "?"} tools ·
                      {" "}
                      {payload?.duration_seconds ?? "?"}s
                    </span>
                  </div>
                  <span className={statusClass(proposal.status)}>{proposal.status}</span>
                </header>
                {recipe.summary && (
                  <p className="small" style={{ marginTop: 8 }}>
                    {recipe.summary}
                  </p>
                )}
                {steps.length > 0 && (
                  <ol className="small" style={{ marginTop: 6 }}>
                    {steps.slice(0, 6).map((step, idx) => (
                      <li key={idx}>
                        <code>{step.tool ?? "?"}</code>
                        {step.purpose ? ` — ${step.purpose}` : ""}
                      </li>
                    ))}
                  </ol>
                )}
                <div className="row" style={{ marginTop: 8 }}>
                  <button
                    className="primary"
                    disabled={proposal.status !== "pending" || decidingProposalId !== null}
                    onClick={() => approve(proposal.proposal_id)}
                    type="button"
                  >
                    Aprobar
                  </button>
                  <button
                    className="danger"
                    disabled={proposal.status !== "pending" || decidingProposalId !== null}
                    onClick={() => reject(proposal.proposal_id)}
                    type="button"
                  >
                    Rechazar
                  </button>
                  <details>
                    <summary className="small">Ver JSON</summary>
                    <pre style={{ maxHeight: 260 }}>
                      {JSON.stringify(payload, null, 2)}
                    </pre>
                  </details>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {exported !== null && (
        <section className="section">
          <h3>Export más reciente</h3>
          <pre>{JSON.stringify(exported, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}
