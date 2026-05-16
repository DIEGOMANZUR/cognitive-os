"use client";

import { useEffect, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage, statusClass } from "../lib/api";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { MailMessage, MailSendResult, MailStatus, MailSyncResult } from "../lib/types";

const STATUS_OPTIONS = ["", "reply_proposed", "pending_send", "new", "ignored", "sent", "failed"];

export function MailInboxView({ client }: { client: ApiClient }) {
  const [status, setStatus] = useState("reply_proposed");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [replyText, setReplyText] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const params = new URLSearchParams();
  params.set("limit", "100");
  if (status) params.append("statuses", status);
  const mailStatus = usePolledFetch<MailStatus>(client, "/mail/status", 10000);
  const messages = usePolledFetch<MailMessage[]>(client, `/mail/messages?${params.toString()}`, 5000);
  const selected = (messages.data ?? []).find((item) => item.id === selectedId) ?? null;

  useEffect(() => {
    if (!selectedId && (messages.data ?? []).length > 0) {
      setSelectedId(messages.data?.[0]?.id ?? null);
    }
  }, [messages.data, selectedId]);

  useEffect(() => {
    setReplyText(selected?.proposed_reply_text ?? "");
  }, [selected?.id, selected?.proposed_reply_text]);

  async function syncNow() {
    setBusy(true);
    try {
      const result = await client.post<MailSyncResult>("/mail/sync", {});
      toast.push(`Mail sync: ${result.inserted} nuevos / ${result.fetched} leídos.`, "success");
      void messages.refetch();
      void mailStatus.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  async function saveReply() {
    if (!selected) return;
    setBusy(true);
    try {
      await client.patch<MailMessage>(`/mail/messages/${selected.id}/reply`, {
        body_text: replyText
      });
      toast.push("Propuesta actualizada.", "success");
      void messages.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  async function approveSend() {
    if (!selected) return;
    setBusy(true);
    try {
      const result = await client.post<MailSendResult>(`/mail/messages/${selected.id}/approve-send`, {
        body_text: replyText
      });
      toast.push(
        result.sent ? "Respuesta enviada." : "Respuesta aprobada; envío pendiente.",
        result.sent ? "success" : "warning"
      );
      void messages.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  async function ignore() {
    if (!selected) return;
    setBusy(true);
    try {
      await client.post(`/mail/messages/${selected.id}/ignore`, {});
      toast.push("Mensaje ignorado.", "success");
      void messages.refetch();
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid-2" style={{ gridTemplateColumns: "minmax(0, 1.1fr) minmax(0, 1fr)" }}>
      <section className="section">
        <div className="section-head">
          <div>
            <h2>Mail personal</h2>
            <p className="muted small">
              GoDaddy envía todo; Gmail solo lee label TODOS. Nunca crea borradores.
            </p>
          </div>
          <div className="row">
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option || "Todos"}
                </option>
              ))}
            </select>
            <button className="ghost" disabled={busy} onClick={syncNow} type="button">
              Sync ahora
            </button>
          </div>
        </div>
        <div className="row wrap">
          <span className={mailStatus.data?.enabled ? "badge ok" : "badge configured"}>
            {mailStatus.data?.enabled ? "enabled" : "disabled"}
          </span>
          <span className={mailStatus.data?.require_approval_for_send ? "badge warn" : "badge ok"}>
            {mailStatus.data?.require_approval_for_send ? "send requiere aprobación" : "send directo"}
          </span>
          <span className="muted small">sender: {mailStatus.data?.default_sender ?? "-"}</span>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Estado</th>
                <th>Cuenta</th>
                <th>De</th>
                <th>Asunto</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {(messages.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">
                    Sin mensajes para este filtro.
                  </td>
                </tr>
              )}
              {(messages.data ?? []).map((message) => (
                <tr
                  key={message.id}
                  onClick={() => setSelectedId(message.id)}
                  style={selectedId === message.id ? { background: "var(--accent-soft)" } : undefined}
                >
                  <td>
                    <span className={statusClass(message.status)}>{message.status}</span>
                  </td>
                  <td>{message.account_label ?? message.folder}</td>
                  <td>{message.sender.slice(0, 42)}</td>
                  <td>{message.subject ?? "(sin asunto)"}</td>
                  <td>{message.importance_score.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Propuesta</h2>
          {selected && <span className={statusClass(selected.classification)}>{selected.classification}</span>}
        </div>
        {!selected ? (
          <p className="muted">Selecciona un mensaje.</p>
        ) : (
          <div className="stack">
            <div className="card soft">
              <p className="muted small">{selected.account_label} / {selected.folder}</p>
              <h3>{selected.subject ?? "(sin asunto)"}</h3>
              <p><strong>De:</strong> {selected.sender}</p>
              <p className="muted">{selected.snippet}</p>
              {selected.proposed_reply_rationale && (
                <p className="muted small">Criterio: {selected.proposed_reply_rationale}</p>
              )}
            </div>
            <textarea
              rows={14}
              value={replyText}
              onChange={(event) => setReplyText(event.target.value)}
              placeholder="Escribe o edita la respuesta propuesta..."
            />
            <div className="row wrap">
              <button className="ghost" disabled={busy || !replyText.trim()} onClick={saveReply} type="button">
                Guardar texto
              </button>
              <button disabled={busy || !replyText.trim()} onClick={approveSend} type="button">
                Aprobar y enviar
              </button>
              <button className="danger" disabled={busy} onClick={ignore} type="button">
                Ignorar
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
