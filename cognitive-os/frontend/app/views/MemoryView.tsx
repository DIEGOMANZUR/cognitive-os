"use client";

import { useEffect, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { DeepAgentMemoryProposal } from "../lib/types";

type MemoryScope = "user" | "global" | "case" | "thread" | "agent";

const MEMORY_SCOPES: MemoryScope[] = ["user", "global", "case", "thread", "agent"];

export function MemoryView({ client }: { client: ApiClient }) {
  const [scope, setScope] = useState<MemoryScope>("user");
  const memoryPath = `/deepagents/memory?scope=${encodeURIComponent(scope)}`;
  const memory = usePolledFetch<Record<string, unknown>[]>(client, memoryPath, 12000);
  const proposals = usePolledFetch<DeepAgentMemoryProposal[]>(
    client,
    "/deepagents/memory/proposals",
    10000
  );
  const [exported, setExported] = useState<unknown>(null);
  const [decidingProposalId, setDecidingProposalId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [consolidating, setConsolidating] = useState(false);
  const toast = useToast();

  useEffect(() => {
    setExported(null);
  }, [scope]);

  async function approve(id: string) {
    if (decidingProposalId) return;
    setDecidingProposalId(id);
    try {
      await client.post(`/deepagents/memory/proposals/${id}/approve`, {});
      toast.push("Propuesta aprobada.", "success");
      void proposals.refetch();
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
      {exported !== null && (
        <section className="section">
          <h3>Export más reciente</h3>
          <pre>{JSON.stringify(exported, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}
