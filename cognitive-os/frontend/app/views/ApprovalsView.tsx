"use client";

import { useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { ActionDispatchResponse, ApprovalResponse } from "../lib/types";

export function ApprovalsView({ client }: { client: ApiClient }) {
  const approvals = usePolledFetch<ApprovalResponse[]>(client, "/approvals", 5000);
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const toast = useToast();

  async function decide(id: string, action: "approve" | "reject") {
    if (decidingId) return;
    setDecidingId(id);
    try {
      const approval = await client.post<ApprovalResponse>(`/approvals/${id}/${action}`, {});
      if (action === "approve" && approval.requested_action.startsWith("execute_action_request:")) {
        const actionRequestId = approval.requested_action.replace("execute_action_request:", "");
        try {
          const dispatch = await client.post<ActionDispatchResponse>(
            `/actions/requests/${actionRequestId}/dispatch`,
            {}
          );
          toast.push(
            dispatch.dispatched
              ? "Aprobación aprobada y acción despachada."
              : `Aprobación aprobada. ${dispatch.reason ?? "La acción no fue despachada."}`,
            dispatch.dispatched ? "success" : "warning"
          );
        } catch (dispatchError) {
          toast.push(
            `Aprobación aprobada, pero no se pudo despachar: ${errorMessage(dispatchError)}`,
            "warning"
          );
        }
      } else {
        toast.push(`Aprobación ${action === "approve" ? "aprobada" : "rechazada"}.`, "success");
      }
      void approvals.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setDecidingId(null);
    }
  }

  return (
    <section className="section">
      <div className="section-head">
        <h2>Aprobaciones humanas</h2>
        <div className="row">
          <span className="muted small">
            {(approvals.data ?? []).filter((a) => a.status === "pending").length} pendientes
          </span>
          <button className="ghost" onClick={() => approvals.refetch()} type="button">
            Refrescar
          </button>
        </div>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Acción</th>
              <th>Argumentos redactados</th>
              <th>Solicitante</th>
              <th>Estado</th>
              <th>Decisión</th>
            </tr>
          </thead>
          <tbody>
            {(approvals.data ?? []).length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  Sin aprobaciones registradas.
                </td>
              </tr>
            )}
            {(approvals.data ?? []).map((approval) => (
              <tr key={approval.id}>
                <td>
                  <strong>{approval.requested_action}</strong>
                  <p className="muted small">
                    creada {new Date(approval.created_at).toLocaleString()}
                  </p>
                </td>
                <td>
                  <pre>{JSON.stringify(approval.args_redacted, null, 2)}</pre>
                </td>
                <td>{approval.requested_by ?? "local"}</td>
                <td>
                  <span className={statusClass(approval.status)}>{approval.status}</span>
                  {approval.decided_at && (
                    <p className="muted small">
                      decidida {new Date(approval.decided_at).toLocaleString()}
                      {approval.approver_user_id ? ` por ${approval.approver_user_id}` : null}
                    </p>
                  )}
                </td>
                <td>
                  <div className="row">
                    <button
                      className="primary"
                      disabled={approval.status !== "pending" || decidingId !== null}
                      onClick={() => decide(approval.id, "approve")}
                      type="button"
                    >
                      Aprobar
                    </button>
                    <button
                      className="danger"
                      disabled={approval.status !== "pending" || decidingId !== null}
                      onClick={() => decide(approval.id, "reject")}
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
    </section>
  );
}
