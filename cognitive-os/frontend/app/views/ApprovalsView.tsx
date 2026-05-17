"use client";

import { useRef, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type {
  ActionDispatchResponse,
  ApprovalResponse,
  WorkflowDocument,
  WorkflowImportResult
} from "../lib/types";

const ACTION_REQUEST_PREFIX = "execute_action_request:";

function extractActionRequestId(requestedAction: string): string | null {
  if (!requestedAction.startsWith(ACTION_REQUEST_PREFIX)) return null;
  const id = requestedAction.slice(ACTION_REQUEST_PREFIX.length).trim();
  return id || null;
}

function downloadJson(filename: string, payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json"
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function ApprovalsView({ client }: { client: ApiClient }) {
  const approvals = usePolledFetch<ApprovalResponse[]>(client, "/approvals", 5000);
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [busyWorkflowId, setBusyWorkflowId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const toast = useToast();

  async function exportWorkflow(actionRequestId: string) {
    if (busyWorkflowId) return;
    setBusyWorkflowId(actionRequestId);
    try {
      const doc = await client.get<WorkflowDocument>(
        `/actions/requests/${actionRequestId}/workflow`
      );
      downloadJson(`workflow-${actionRequestId.slice(0, 8)}.json`, doc);
      toast.push("Workflow exportado.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusyWorkflowId(null);
    }
  }

  function triggerImport() {
    fileInputRef.current?.click();
  }

  async function handleImportFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Reset the input so the same file can be re-selected later if needed.
    event.target.value = "";
    if (!file) return;
    let parsed: WorkflowDocument;
    try {
      const text = await file.text();
      parsed = JSON.parse(text) as WorkflowDocument;
    } catch (caught) {
      toast.push(`Archivo inválido: ${errorMessage(caught)}`, "error");
      return;
    }
    if (parsed.workflow_version !== "1.0") {
      toast.push(`workflow_version no soportado: ${String(parsed.workflow_version)}`, "error");
      return;
    }
    try {
      const result = await client.post<WorkflowImportResult>(
        "/actions/requests/from-workflow",
        parsed
      );
      toast.push(
        `Workflow importado → ActionRequest ${result.action_request.id.slice(0, 8)}`,
        "success"
      );
      void approvals.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }

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
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            style={{ display: "none" }}
            onChange={handleImportFile}
          />
          <button
            className="ghost"
            type="button"
            onClick={triggerImport}
            title="Importar workflow.v1 JSON"
          >
            Importar workflow
          </button>
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
                  <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
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
                    {(() => {
                      const actionRequestId = extractActionRequestId(approval.requested_action);
                      if (!actionRequestId) return null;
                      return (
                        <button
                          className="ghost"
                          type="button"
                          disabled={busyWorkflowId !== null}
                          onClick={() => void exportWorkflow(actionRequestId)}
                          title="Exportar como workflow.v1 JSON"
                        >
                          Exportar
                        </button>
                      );
                    })()}
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
