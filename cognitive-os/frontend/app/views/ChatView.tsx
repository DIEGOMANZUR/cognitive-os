"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { ApiClient } from "../lib/api";
import { errorMessage } from "../lib/api";
import { Icon } from "../components/Icon";
import { renderMarkdownLite } from "../lib/markdown";
import { useHydrated } from "../lib/hooks";
import { useToast } from "../lib/toasts";
import type {
  ChatResponse,
  StreamEvent,
  ThreadMessage,
  ThreadResponse,
  ThreadSummary
} from "../lib/types";

type LocalEntry = ThreadMessage & { ts?: number; optimisticId?: string };

function threadLabel(threadId: string): string {
  // Fase 72 J: para Telegram threads (`telegram-chat-<id>-<salt>`) los
  // primeros 8 chars son siempre "telegram", lo que hace que todos se vean
  // idénticos en la lista. Para esos casos mostrar el sufijo informativo.
  if (threadId.startsWith("telegram-chat-")) {
    const tail = threadId.slice(-8);
    return `tg…${tail}`;
  }
  return `${threadId.slice(0, 8)}…`;
}

export function ChatView({ client }: { client: ApiClient }) {
  const [message, setMessage] = useState("");
  const [threadId, setThreadId] = useState("");
  const [docIdsInput, setDocIdsInput] = useState("");
  const [caseId, setCaseId] = useState("");
  const [history, setHistory] = useState<LocalEntry[]>([]);
  const [activeRoute, setActiveRoute] = useState<string>("");
  const [pending, setPending] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [resumeMessage, setResumeMessage] = useState("");
  const [streamLog, setStreamLog] = useState<StreamEvent[]>([]);
  const [recentThreads, setRecentThreads] = useState<ThreadSummary[]>([]);
  const toast = useToast();
  const hydrated = useHydrated();
  const historyEndRef = useRef<HTMLDivElement>(null);
  const currentThreadId = threadId.trim();

  const refreshThread = useCallback(
    async (targetId: string) => {
      if (!targetId) return;
      try {
        const data = await client.get<ThreadResponse>(`/threads/${targetId}`);
        const messages = data.values.messages ?? [];
        setHistory(messages.map((message) => ({ ...message })));
        setActiveRoute(String(data.values.active_route ?? ""));
        setPending(
          (data.values.pending_human_review as Record<string, unknown> | null) ?? null
        );
      } catch (caught) {
        toast.push(`No se pudo cargar el thread: ${errorMessage(caught)}`, "warning");
      }
    },
    [client, toast]
  );

  const refreshThreads = useCallback(async () => {
    try {
      const data = await client.get<ThreadSummary[]>("/threads?limit=20");
      setRecentThreads(data);
    } catch {
      // best-effort
    }
  }, [client]);

  useEffect(() => {
    void refreshThreads();
  }, [refreshThreads]);

  useEffect(() => {
    if (currentThreadId) void refreshThread(currentThreadId);
  }, [currentThreadId, refreshThread]);

  useEffect(() => {
    historyEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history.length]);

  function parseDocIds(): string[] {
    return docIdsInput
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function pushOptimisticUser(content: string, optimisticId: string) {
    setHistory((prev) => [...prev, { type: "human", content, ts: Date.now(), optimisticId }]);
  }

  async function send(useStream: boolean) {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || busy) return;
    const optimisticId = crypto.randomUUID();
    setBusy(true);
    setStreamLog([]);
    pushOptimisticUser(trimmedMessage, optimisticId);
    const docIds = parseDocIds();
    const payload = {
      message: trimmedMessage,
      thread_id: currentThreadId || undefined,
      doc_ids: docIds.length ? docIds : undefined,
      case_id: caseId.trim() || undefined
    };
    try {
      if (useStream) {
        const final = await client.streamChat(payload, (event) => {
          setStreamLog((cur) => [...cur, event]);
          if (event.event === "thread_started" && typeof event.thread_id === "string") {
            setThreadId(event.thread_id);
          }
        });
        if (final) {
          setThreadId(final.thread_id);
          setActiveRoute(final.route);
          setPending(final.pending_human_review ?? null);
          await refreshThread(final.thread_id);
        }
      } else {
        const result = await client.post<ChatResponse>("/chat", payload);
        setThreadId(result.thread_id);
        setActiveRoute(result.route);
        setPending(result.pending_human_review ?? null);
        await refreshThread(result.thread_id);
      }
      setMessage("");
      void refreshThreads();
    } catch (caught) {
      setHistory((prev) => prev.filter((entry) => entry.optimisticId !== optimisticId));
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  async function resume(action: "approve" | "reject" | "edit") {
    const activeThreadId = currentThreadId;
    if (!activeThreadId || busy) return;
    const editedMessage = resumeMessage.trim();
    if (action === "edit" && !editedMessage) {
      toast.push("Ingresá el mensaje editado antes de reenviar.", "error");
      return;
    }

    setBusy(true);
    try {
      const payload: Record<string, unknown> = { action };
      if (action === "edit") payload.message = editedMessage;
      await client.post<ChatResponse>(`/threads/${activeThreadId}/resume`, payload);
      await refreshThread(activeThreadId);
      setResumeMessage("");
      toast.push(`Acción ${action} aplicada.`, "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    } finally {
      setBusy(false);
    }
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.push("Copiado al portapapeles.", "success");
    } catch (caught) {
      toast.push(errorMessage(caught), "error");
    }
  }

  return (
    <div
      className="grid-2"
      style={{ gridTemplateColumns: "minmax(0, 280px) minmax(0, 1fr)", alignItems: "start" }}
    >
      <section className="section stack" style={{ position: "sticky", top: 16 }}>
        <div className="section-head">
          <h2>Threads</h2>
          <button
            className="ghost icon"
            onClick={() => void refreshThreads()}
            type="button"
            aria-label="Refrescar threads"
          >
            <Icon name="refresh" size={14} />
          </button>
        </div>
        <button
          className="primary"
          onClick={() => {
            setThreadId("");
            setHistory([]);
            setActiveRoute("");
            setPending(null);
            setStreamLog([]);
          }}
          type="button"
        >
          <Icon name="plus" size={14} /> Nuevo thread
        </button>
        <ul className="stack" style={{ gap: 4, listStyle: "none", padding: 0, margin: 0 }}>
          {recentThreads.length === 0 && (
            <li>
              <div className="empty-state" style={{ padding: "18px 8px" }}>
                <span className="empty-icon">
                  <Icon name="chat" size={16} />
                </span>
                <span className="empty-msg">
                  Aún no hay threads. Hacé tu primera consulta abajo.
                </span>
              </div>
            </li>
          )}
          {recentThreads.map((thread) => (
            <li key={thread.thread_id}>
              <button
                onClick={() => setThreadId(thread.thread_id)}
                type="button"
                style={{
                  width: "100%",
                  justifyContent: "flex-start",
                  background:
                    currentThreadId === thread.thread_id ? "var(--accent-soft)" : "transparent",
                  borderColor:
                    currentThreadId === thread.thread_id ? "var(--accent)" : "transparent"
                }}
              >
                <div className="stack" style={{ gap: 2, alignItems: "flex-start" }}>
                  <code className="small">{threadLabel(thread.thread_id)}</code>
                  <span className="muted small">
                    {thread.last_route ?? "—"}
                    {thread.last_active_at &&
                      ` · ${hydrated ? relativeTime(thread.last_active_at) : "—"}`}
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <div className="stack">
        <section className="section stack">
          <div className="section-head">
            <h2>
              Chat orquestado{" "}
              {activeRoute && <span className="badge info">{activeRoute}</span>}
            </h2>
            <div className="row">
              {currentThreadId && (
                <code className="small" onClick={() => copyText(currentThreadId)} role="button">
                  {threadLabel(currentThreadId)} (copiar)
                </code>
              )}
            </div>
          </div>
          <div className="stack" style={{ gap: 6 }}>
            <div className="row">
              <input
                placeholder="thread_id (vacío = nuevo)"
                value={threadId}
                onChange={(event) => setThreadId(event.target.value)}
              />
              <input
                placeholder="case_id (opcional)"
                value={caseId}
                onChange={(event) => setCaseId(event.target.value)}
                style={{ maxWidth: 200 }}
              />
            </div>
            <input
              placeholder="doc_ids (UUIDs separados por coma — fuerza ruta legal)"
              value={docIdsInput}
              onChange={(event) => setDocIdsInput(event.target.value)}
            />
          </div>

          {history.length > 0 && (
            <div className="stack" style={{ gap: 8, maxHeight: "55vh", overflow: "auto" }}>
              {history.map((entry, index) => (
                <article
                  key={`${entry.type}-${index}`}
                  className={`chat-bubble${entry.type === "human" ? " you" : ""}`}
                >
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <span className="muted small">
                      {entry.type === "human" ? "Vos" : "Cognitive OS"}
                    </span>
                    <button
                      className="ghost"
                      onClick={() => copyText(entry.content)}
                      type="button"
                      title="Copiar"
                    >
                      ⎘
                    </button>
                  </div>
                  <div
                    className="markdown"
                    dangerouslySetInnerHTML={{ __html: renderMarkdownLite(entry.content) }}
                  />
                </article>
              ))}
              <div ref={historyEndRef} />
            </div>
          )}

          {pending && <PendingReview pending={pending} onCopy={copyText} />}
          {pending && (
            <div className="warn-box stack">
              <strong>Revisión humana</strong>
              <input
                placeholder="(opcional) mensaje editado"
                value={resumeMessage}
                onChange={(event) => setResumeMessage(event.target.value)}
              />
              <div className="row">
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => resume("approve")}
                  type="button"
                >
                  Aprobar
                </button>
                <button
                  disabled={busy || !resumeMessage.trim()}
                  onClick={() => resume("edit")}
                  type="button"
                >
                  Editar y reenviar
                </button>
                <button
                  className="danger"
                  disabled={busy}
                  onClick={() => resume("reject")}
                  type="button"
                >
                  Rechazar
                </button>
              </div>
            </div>
          )}

          <textarea
            placeholder="Pregunta al Cognitive OS… (Cmd/Ctrl + Enter envía con stream)"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={(event) => {
              if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                event.preventDefault();
                void send(true);
              }
            }}
          />
          <div className="row">
            <button
              className="primary"
              disabled={busy || !message.trim()}
              onClick={() => void send(false)}
              type="button"
            >
              {busy ? <span className="spinner" aria-hidden="true" /> : <Icon name="send" size={14} />}
              Enviar
            </button>
            <button
              disabled={busy || !message.trim()}
              onClick={() => void send(true)}
              type="button"
            >
              <Icon name="zap" size={14} /> Enviar (SSE)
            </button>
            {currentThreadId && (
              <button
                className="ghost small"
                onClick={() => void refreshThread(currentThreadId)}
                type="button"
              >
                <Icon name="refresh" size={13} /> Refrescar thread
              </button>
            )}
          </div>
          {streamLog.length > 0 && (
            <div className="chat-stream">
              {streamLog.map((event, index) => (
                <span
                  key={`${event.event}-${index}`}
                  className={
                    event.event === "final_response"
                      ? "ev-final"
                      : event.event === "error"
                        ? "ev-error"
                        : "ev"
                  }
                >
                  {formatStreamEvent(event)}
                </span>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function PendingReview({
  pending,
  onCopy
}: {
  pending: Record<string, unknown>;
  onCopy: (text: string) => void;
}) {
  const draft =
    typeof (pending.payload as Record<string, unknown> | undefined)?.draft === "string"
      ? String((pending.payload as Record<string, unknown>).draft)
      : null;
  return (
    <section className="section stack" style={{ borderColor: "var(--warn)" }}>
      <div className="section-head">
        <h3>Pending human review</h3>
        <button className="ghost" onClick={() => onCopy(JSON.stringify(pending, null, 2))} type="button">
          ⎘ JSON
        </button>
      </div>
      {pending.reason ? <p>{String(pending.reason)}</p> : null}
      {pending.proposed_action ? (
        <p className="small muted">
          Proposed action: <code>{String(pending.proposed_action)}</code>
        </p>
      ) : null}
      {draft && (
        <div className="stack">
          <strong className="small">Borrador propuesto:</strong>
          <pre style={{ background: "var(--bg-elev)" }}>{draft}</pre>
        </div>
      )}
      <details>
        <summary className="muted small">Payload completo</summary>
        <pre>{JSON.stringify(pending, null, 2)}</pre>
      </details>
    </section>
  );
}

function formatStreamEvent(event: StreamEvent): string {
  if (event.event === "node_update") return `▸ ${event.node ?? "node"}`;
  if (event.event === "final_response") return `✓ final · ruta=${event.route ?? "?"}`;
  if (event.event === "interrupt") return "⏸ aprobación humana requerida";
  if (event.event === "error") return `✗ error: ${event.detail ?? "desconocido"}`;
  if (event.event === "thread_started") return `· thread ${(event.thread_id ?? "").slice(0, 8)}…`;
  if (event.event === "done") return "— fin del stream";
  return event.event;
}

function relativeTime(iso: string): string {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return iso;
  const diff = Math.max(0, Date.now() - ts);
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}
