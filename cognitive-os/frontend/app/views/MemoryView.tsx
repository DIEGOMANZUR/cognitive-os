"use client";

import { useEffect, useMemo, useState } from "react";

import type { ApiClient } from "../lib/api";
import { asArray, errorMessage, statusClass } from "../lib/api";
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
  const warnings = usePolledFetch<DeepAgentMemoryProposal[]>(
    client,
    "/deepagents/memory/warnings",
    15000
  );
  type ScorecardRow = {
    id: string;
    agent_role: string;
    tool_name: string;
    period_start: string;
    invoke_count: number;
    success_count: number;
    failure_count: number;
    reliability_score: number | null;
  };
  const scorecard = usePolledFetch<ScorecardRow[]>(
    client,
    "/deepagents/learning/tool-scorecard?days=14&limit=100",
    30000
  );
  type SkillPromotion = {
    proposal_id: string;
    status: string;
    proposed_by_agent: string;
    reason: string;
    skill_name?: string | null;
    route?: string | null;
    source_memory_id?: string | null;
    stats?: {
      success_count: number;
      failure_count: number;
      partial_count: number;
      failure_rate: number;
    } | null;
    created_at: string;
    decided_at?: string | null;
  };
  const skillPromotions = usePolledFetch<SkillPromotion[]>(
    client,
    "/deepagents/learning/skill-promotions",
    30000
  );
  type ReflectionProposal = {
    proposal_id: string;
    status: string;
    kind: string;
    scope: string;
    reason: string;
    proposed_content: string;
    evidence_message_ids: string[];
    evidence_quotes: string[];
    confidence: number | null;
    thread_id?: string | null;
    user_id?: string | null;
    created_at: string;
    decided_at?: string | null;
  };
  const reflections = usePolledFetch<ReflectionProposal[]>(
    client,
    "/deepagents/learning/reflection?days=14",
    30000
  );
  const [exported, setExported] = useState<unknown>(null);
  const [decidingProposalId, setDecidingProposalId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [consolidating, setConsolidating] = useState(false);
  const [extractingRecipes, setExtractingRecipes] = useState(false);
  const [scanningFailures, setScanningFailures] = useState(false);
  const [aggregatingScorecard, setAggregatingScorecard] = useState(false);
  const [evaluatingSkills, setEvaluatingSkills] = useState(false);
  const [reflectingNow, setReflectingNow] = useState(false);
  const [applyingPromotionId, setApplyingPromotionId] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    setExported(null);
  }, [scope]);

  const pendingRecipes = useMemo<DeepAgentMemoryProposal[]>(
    () => asArray(recipes.data).filter((p) => p.status === "pending"),
    [recipes.data]
  );
  const pendingWarnings = useMemo<DeepAgentMemoryProposal[]>(
    () => asArray(warnings.data).filter((p) => p.status === "pending"),
    [warnings.data]
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

  async function scanFailuresNow() {
    if (scanningFailures) return;
    setScanningFailures(true);
    try {
      await client.post("/deepagents/memory/warnings/scan-now", {});
      toast.push("Scanner de fallos encolado.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setScanningFailures(false);
    }
  }

  async function aggregateScorecardNow() {
    if (aggregatingScorecard) return;
    setAggregatingScorecard(true);
    try {
      await client.post("/deepagents/learning/tool-scorecard/aggregate-now", {});
      toast.push("Scorecard agregación encolada.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setAggregatingScorecard(false);
    }
  }

  async function evaluateSkillsNow() {
    if (evaluatingSkills) return;
    setEvaluatingSkills(true);
    try {
      await client.post("/deepagents/learning/skill-promotions/evaluate-now", {});
      toast.push("Promoter de skills encolado.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setEvaluatingSkills(false);
    }
  }

  async function approveSkillPromotion(id: string) {
    if (applyingPromotionId) return;
    setApplyingPromotionId(id);
    try {
      const response = await client.post<{ skill_slug?: string; already_existed?: boolean }>(
        `/deepagents/learning/skill-promotions/${id}/approve`,
        {}
      );
      const slug = response?.skill_slug ?? "skill";
      const already = response?.already_existed;
      toast.push(
        already
          ? `Skill ${slug} ya estaba materializado.`
          : `Skill ${slug} materializado.`,
        "success"
      );
      void skillPromotions.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setApplyingPromotionId(null);
    }
  }

  async function runReflectionNow() {
    if (reflectingNow) return;
    setReflectingNow(true);
    try {
      await client.post("/deepagents/learning/reflection/run-now", {});
      toast.push("Reflexión nocturna encolada.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setReflectingNow(false);
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
              Memoria activa · {scope} ({asArray(memory.data).length})
            </h3>
            <pre style={{ maxHeight: 320 }}>
              {memory.data ? JSON.stringify(memory.data, null, 2) : "Cargando…"}
            </pre>
          </div>
          <div className="stack">
            <h3>Propuestas pendientes ({asArray(proposals.data).length})</h3>
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
                  {asArray(proposals.data).length === 0 && (
                    <tr>
                      <td colSpan={5} className="muted">
                        Sin propuestas pendientes.
                      </td>
                    </tr>
                  )}
                  {asArray(proposals.data).map((proposal) => (
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

      {/* Fase 79.3 — Warnings (failure-recovery patterns). */}
      <section className="section" data-testid="warning-proposals-section">
        <div className="section-head">
          <h2>Warnings detectadas ({pendingWarnings.length})</h2>
          <div className="row">
            <button
              className="primary"
              disabled={scanningFailures}
              onClick={scanFailuresNow}
              type="button"
            >
              {scanningFailures ? "Encolando…" : "Escanear ahora"}
            </button>
            <button
              className="ghost"
              onClick={() => {
                void warnings.refetch();
              }}
              type="button"
            >
              Refrescar
            </button>
          </div>
        </div>
        <p className="muted small">
          Patrones <code>tool_failed → tool_succeeded</code> detectados en jobs recientes.
          El scanner auto-promueve después de 3 observaciones sin rechazos.
        </p>
        {warnings.data === undefined && <p className="muted">Cargando…</p>}
        {pendingWarnings.length === 0 && warnings.data !== undefined && (
          <p className="muted small">Sin warnings pendientes.</p>
        )}
        <div className="stack">
          {pendingWarnings.map((proposal) => (
            <article key={proposal.proposal_id} className="card">
              <header className="row" style={{ justifyContent: "space-between" }}>
                <div>
                  <strong>{proposal.proposed_by_agent}</strong>
                  <span className="muted small" style={{ marginLeft: 8 }}>
                    confianza {proposal.confidence?.toFixed(2) ?? "?"}
                  </span>
                </div>
                <span className={statusClass(proposal.status)}>{proposal.status}</span>
              </header>
              <p className="small" style={{ marginTop: 8 }}>{proposal.proposed_content}</p>
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
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Fase 79.4 — Tool effectiveness scorecard. */}
      <section className="section" data-testid="scorecard-section">
        <div className="section-head">
          <h2>Scorecard de tools ({scorecard.data?.length ?? 0})</h2>
          <div className="row">
            <button
              className="primary"
              disabled={aggregatingScorecard}
              onClick={aggregateScorecardNow}
              type="button"
            >
              {aggregatingScorecard ? "Encolando…" : "Agregar ahora"}
            </button>
            <button
              className="ghost"
              onClick={() => {
                void scorecard.refetch();
              }}
              type="button"
            >
              Refrescar
            </button>
          </div>
        </div>
        <p className="muted small">
          Confiabilidad por (agente, tool) — últimos 14 días.
          <code> reliability = 0.5·success + 0.3·downstream + 0.2·approval</code>
        </p>
        {scorecard.data === undefined && <p className="muted">Cargando…</p>}
        {scorecard.data && scorecard.data.length === 0 && (
          <p className="muted small">Sin datos aún. El aggregator corre diario a las 04:15 UTC.</p>
        )}
        {scorecard.data && scorecard.data.length > 0 && (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Agente</th>
                  <th>Tool</th>
                  <th style={{ textAlign: "right" }}>Score</th>
                  <th style={{ textAlign: "right" }}>OK/Fail</th>
                  <th>Periodo</th>
                </tr>
              </thead>
              <tbody>
                {scorecard.data.map((row) => {
                  const score = row.reliability_score;
                  const badge =
                    score === null || score === undefined
                      ? "—"
                      : score >= 0.85
                        ? `✅ ${score.toFixed(2)}`
                        : score <= 0.5
                          ? `⚠️ ${score.toFixed(2)}`
                          : score.toFixed(2);
                  return (
                    <tr key={row.id}>
                      <td>{row.agent_role}</td>
                      <td>
                        <code>{row.tool_name}</code>
                      </td>
                      <td style={{ textAlign: "right" }}>{badge}</td>
                      <td style={{ textAlign: "right" }}>
                        {row.success_count}/{row.failure_count}
                      </td>
                      <td className="muted small">
                        {row.period_start.slice(0, 10)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Fase 80 — Skill promotion proposals. */}
      <section className="section" data-testid="skill-promotions-section">
        <div className="section-head">
          <h2>Promociones a skill ({skillPromotions.data?.length ?? 0})</h2>
          <div className="row">
            <button
              className="primary"
              disabled={evaluatingSkills}
              onClick={evaluateSkillsNow}
              type="button"
            >
              {evaluatingSkills ? "Evaluando…" : "Evaluar ahora"}
            </button>
            <button
              className="ghost"
              onClick={() => {
                void skillPromotions.refetch();
              }}
              type="button"
            >
              Refrescar
            </button>
          </div>
        </div>
        <p className="muted small">
          Procedures con ≥3 éxitos y &lt;30% de fallos se proponen como skills YAML.
          Aprueba para materializar el archivo bajo{" "}
          <code>storage/deepagents/skills/user/_auto/</code>.
        </p>
        {skillPromotions.data === undefined && <p className="muted">Cargando…</p>}
        {skillPromotions.data && skillPromotions.data.length === 0 && (
          <p className="muted small">
            Sin promociones pendientes. El promoter corre diario a las 04:45 UTC.
          </p>
        )}
        {skillPromotions.data && skillPromotions.data.length > 0 && (
          <div className="stack">
            {skillPromotions.data.map((promo) => (
              <article
                key={promo.proposal_id}
                className="card"
                data-testid="skill-promotion-card"
              >
                <header className="row" style={{ justifyContent: "space-between" }}>
                  <div>
                    <strong>{promo.skill_name ?? "(sin nombre)"}</strong>
                    <span className="muted small" style={{ marginLeft: 8 }}>
                      {promo.route ?? "yaml"} · memoria origen{" "}
                      <code>{promo.source_memory_id?.slice(0, 8) ?? "—"}</code>
                    </span>
                  </div>
                  <span className={statusClass(promo.status)}>{promo.status}</span>
                </header>
                <p className="small" style={{ marginTop: 6 }}>
                  {promo.reason}
                </p>
                {promo.stats && (
                  <p className="small muted">
                    Éxitos: {promo.stats.success_count} · Fallos: {promo.stats.failure_count}
                    {" · "}
                    Failure rate: {(promo.stats.failure_rate * 100).toFixed(0)}%
                  </p>
                )}
                <div className="row" style={{ marginTop: 8 }}>
                  <button
                    className="primary"
                    disabled={
                      promo.status !== "pending" || applyingPromotionId !== null
                    }
                    onClick={() => approveSkillPromotion(promo.proposal_id)}
                    type="button"
                  >
                    {applyingPromotionId === promo.proposal_id
                      ? "Materializando…"
                      : "Aprobar (materializar)"}
                  </button>
                  <button
                    className="danger"
                    disabled={
                      promo.status !== "pending" || decidingProposalId !== null
                    }
                    onClick={() => reject(promo.proposal_id)}
                    type="button"
                  >
                    Rechazar
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {/* Fase 81 — Nightly reflection. */}
      <section className="section" data-testid="reflection-proposals-section">
        <div className="section-head">
          <h2>Reflexiones nocturnas ({reflections.data?.length ?? 0})</h2>
          <div className="row">
            <button
              className="primary"
              disabled={reflectingNow}
              onClick={runReflectionNow}
              type="button"
            >
              {reflectingNow ? "Encolando…" : "Reflexionar ahora"}
            </button>
            <button
              className="ghost"
              onClick={() => {
                void reflections.refetch();
              }}
              type="button"
            >
              Refrescar
            </button>
          </div>
        </div>
        <p className="muted small">
          Propuestas <code>preference</code> / <code>lesson</code> derivadas
          de la conversación, con quote literal del transcript original como
          evidencia.
        </p>
        {reflections.data === undefined && <p className="muted">Cargando…</p>}
        {reflections.data && reflections.data.length === 0 && (
          <p className="muted small">Sin reflexiones aún.</p>
        )}
        {reflections.data && reflections.data.length > 0 && (
          <div className="stack">
            {reflections.data.map((proposal) => (
              <article
                key={proposal.proposal_id}
                className="card"
                data-testid="reflection-proposal-card"
              >
                <header className="row" style={{ justifyContent: "space-between" }}>
                  <div>
                    <strong>{proposal.kind}</strong>
                    <span className="muted small" style={{ marginLeft: 8 }}>
                      conf {(proposal.confidence ?? 0).toFixed(2)} · scope{" "}
                      {proposal.scope}
                    </span>
                  </div>
                  <span className={statusClass(proposal.status)}>{proposal.status}</span>
                </header>
                <p className="small" style={{ marginTop: 6 }}>
                  {proposal.proposed_content}
                </p>
                {proposal.evidence_quotes && proposal.evidence_quotes.length > 0 && (
                  <details>
                    <summary className="small">
                      Evidencia ({proposal.evidence_quotes.length})
                    </summary>
                    <ul className="small">
                      {proposal.evidence_quotes.map((quote, idx) => (
                        <li key={idx}>
                          <em>“{quote}”</em>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                <div className="row" style={{ marginTop: 8 }}>
                  <button
                    className="primary"
                    disabled={
                      proposal.status !== "pending" || decidingProposalId !== null
                    }
                    onClick={() => approve(proposal.proposal_id)}
                    type="button"
                  >
                    Aprobar
                  </button>
                  <button
                    className="danger"
                    disabled={
                      proposal.status !== "pending" || decidingProposalId !== null
                    }
                    onClick={() => reject(proposal.proposal_id)}
                    type="button"
                  >
                    Rechazar
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
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
