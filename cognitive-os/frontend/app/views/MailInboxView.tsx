"use client";

import { useEffect, useState } from "react";

import type { ApiClient } from "../lib/api";
import { asArray, errorMessage, statusClass } from "../lib/api";
import { EmptyState, ErrorPanel, Skeleton } from "../components/StatePrimitives";
import { usePolledFetch } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type { MailDigestResult, MailMessage, MailStatus, MailSyncResult } from "../lib/types";

const STATUS_OPTIONS = ["", "reply_proposed", "pending_send", "new", "ignored", "sent", "failed"];

export function MailInboxView({ client }: { client: ApiClient }) {
  const [status, setStatus] = useState("reply_proposed");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [replyText, setReplyText] = useState("");
  const [digest, setDigest] = useState<MailDigestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const params = new URLSearchParams();
  params.set("limit", "100");
  if (status) params.append("statuses", status);
  const mailStatus = usePolledFetch<MailStatus>(client, "/mail/status", 10000);
  const messages = usePolledFetch<MailMessage[]>(client, `/mail/messages?${params.toString()}`, 5000);
  const selected = asArray(messages.data).find((item) => item.id === selectedId) ?? null;

  useEffect(() => {
    if (!selectedId && asArray(messages.data).length > 0) {
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

  async function buildDigest() {
    setBusy(true);
    try {
      const result = await client.post<MailDigestResult>("/mail/digest/preview", {
        limit: mailStatus.data?.digest_max_messages ?? 50,
        sync_first: true,
        persist_artifact: false
      });
      setDigest(result);
      toast.push(
        `Resumen generado: ${result.included_count} no-spam / ${result.important_count} importantes.`,
        "success"
      );
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

  async function copyReply() {
    if (!replyText.trim()) return;
    try {
      await navigator.clipboard.writeText(replyText);
      toast.push("Texto copiado.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }

  async function copyDigestText(text: string, label: string) {
    if (!text.trim()) return;
    try {
      await navigator.clipboard.writeText(text);
      toast.push(`${label} copiado.`, "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="section-head">
          <div>
            <h2>Digest de correo</h2>
            <p className="muted small">
              Lee Gmail Todos/Spam y GoDaddy Spam; el agente clasifica el spam y solo propone
              respuestas como texto.
            </p>
          </div>
          <button disabled={busy || !mailStatus.data?.enabled} onClick={buildDigest} type="button">
            Generar resumen 50
          </button>
        </div>
        <div className="row wrap">
          <span className={mailStatus.data?.enabled ? "badge ok" : "badge configured"}>
            {mailStatus.data?.enabled ? "mail activo" : "mail desactivado"}
          </span>
          <span className="badge warn">solo lectura por defecto</span>
          <span className={mailStatus.data?.allow_explicit_send ? "badge warn" : "badge ok"}>
            {mailStatus.data?.allow_explicit_send ? "send explícito permitido" : "send bloqueado"}
          </span>
          <span className={mailStatus.data?.background_sync_enabled ? "badge warn" : "badge ok"}>
            {mailStatus.data?.background_sync_enabled ? "sync continuo activo" : "solo digest 10/20"}
          </span>
          <span className="muted small">
            digest {mailStatus.data?.digest_hours_local?.join(", ") || "10, 20"} h{" "}
            {mailStatus.data?.digest_timezone ?? "America/Santiago"}
          </span>
        </div>
        {digest ? (
          <div className="grid-2">
            <div className="stack">
              <div className="spread">
                <strong>Resumen de los 50 correos</strong>
                <button
                  className="ghost"
                  onClick={() => void copyDigestText(digest.summary_text, "Resumen")}
                  type="button"
                >
                  Copiar
                </button>
              </div>
              <textarea readOnly rows={14} value={digest.summary_text} />
            </div>
            <div className="stack">
              <div className="spread">
                <strong>Respuestas propuestas</strong>
                <button
                  className="ghost"
                  onClick={() => void copyDigestText(digest.proposed_replies_text, "Respuestas")}
                  type="button"
                >
                  Copiar
                </button>
              </div>
              <textarea readOnly rows={14} value={digest.proposed_replies_text} />
            </div>
          </div>
        ) : (
          <EmptyState
            icon="mail"
            title="Sin digest generado"
            message="Genera el resumen para ver dos campos separados: panorama general y respuestas sugeridas."
          />
        )}
      </section>

      <div className="grid-2" style={{ gridTemplateColumns: "minmax(0, 1.1fr) minmax(0, 1fr)" }}>
      <section className="section">
        <div className="section-head">
          <div>
            <h2>Mail personal</h2>
            <p className="muted small">
              Persistencia local de mensajes leídos; no crea borradores y no envía en el flujo normal.
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
          <span className="badge ok">
            Gmail: {asArray(mailStatus.data?.gmail_monitor_labels).join(", ") || "TODOS, SPAM"}
          </span>
          <span className="badge warn">SMTP fuera del flujo normal</span>
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
              {messages.error && asArray(messages.data).length === 0 && (
                <tr>
                  <td colSpan={5}>
                    <ErrorPanel error={messages.error} onRetry={() => void messages.refetch()} />
                  </td>
                </tr>
              )}
              {messages.loading && asArray(messages.data).length === 0 && !messages.error && (
                <tr>
                  <td colSpan={5}>
                    <Skeleton rows={4} />
                  </td>
                </tr>
              )}
              {!messages.loading && !messages.error && asArray(messages.data).length === 0 && (
                <tr>
                  <td colSpan={5}>
                    <EmptyState
                      icon="mail"
                      title="Sin mensajes para este filtro"
                      message="Cambiá el filtro o sincronizá los mailboxes con el botón Sync ahora."
                    />
                  </td>
                </tr>
              )}
              {asArray(messages.data).map((message) => (
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
              <button className="ghost" disabled={busy || !replyText.trim()} onClick={copyReply} type="button">
                Copiar texto
              </button>
              <button className="danger" disabled={busy} onClick={ignore} type="button">
                Ignorar
              </button>
            </div>
          </div>
        )}
      </section>
      </div>
    </div>
  );
}
