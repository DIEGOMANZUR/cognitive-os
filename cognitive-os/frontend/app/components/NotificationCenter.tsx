"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { useFocusTrap } from "../lib/a11y";
import type { ApiClient } from "../lib/api";
import { useToast } from "../lib/toasts";
import type {
  ApprovalResponse,
  AuditEvent,
  JobResponse,
  Tab
} from "../lib/types";
import { Icon, type IconName } from "./Icon";

type Tone = "ok" | "warn" | "danger" | "info";

type Item = {
  id: string;
  tone: Tone;
  icon: IconName;
  title: string;
  text: string;
  ts: number;
  target: Tab;
};

const SEEN_KEY = "cogos.notif.seen";

function loadSeen(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(SEEN_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as string[];
    return new Set(parsed);
  } catch {
    return new Set();
  }
}

function persistSeen(set: Set<string>) {
  try {
    window.localStorage.setItem(SEEN_KEY, JSON.stringify([...set].slice(-200)));
  } catch {
    // storage might be unavailable; non-fatal
  }
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return "—";
  const diff = Math.max(0, Date.now() - ts);
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

export function buildNotificationItems(
  approvals: ApprovalResponse[] | null,
  jobs: JobResponse[] | null,
  audit: AuditEvent[] | null
): Item[] {
  const items: Item[] = [];

  for (const approval of approvals ?? []) {
    if (approval.status !== "pending") continue;
    items.push({
      id: `approval:${approval.id}`,
      tone: "warn",
      icon: "approvals",
      title: "Aprobación pendiente",
      text: approval.requested_action,
      ts: new Date(approval.created_at).getTime(),
      target: "approvals"
    });
  }

  for (const job of jobs ?? []) {
    if (job.status === "failed") {
      items.push({
        id: `job-fail:${job.id}`,
        tone: "danger",
        icon: "circleX",
        title: "Job fallido",
        text: job.job_type,
        ts: new Date(job.updated_at).getTime(),
        target: "jobs"
      });
    } else if (job.status === "completed") {
      items.push({
        id: `job-done:${job.id}`,
        tone: "ok",
        icon: "circleCheck",
        title: "Job completado",
        text: job.job_type,
        ts: new Date(job.updated_at).getTime(),
        target: "jobs"
      });
    } else if (job.status === "running") {
      items.push({
        id: `job-run:${job.id}`,
        tone: "info",
        icon: "jobs",
        title: "Job en ejecución",
        text: `${job.job_type} · ${job.progress}%`,
        ts: new Date(job.updated_at).getTime(),
        target: "jobs"
      });
    }
  }

  for (const event of audit ?? []) {
    items.push({
      id: `audit:${event.id}`,
      tone: "info",
      icon: "audit",
      title: event.action,
      text: event.resource_type ?? "audit event",
      ts: new Date(event.created_at).getTime(),
      target: "audit"
    });
  }

  items.sort((a, b) => b.ts - a.ts);
  return items.slice(0, 60);
}

function PushControls({ client }: { client: ApiClient }) {
  const [supported, setSupported] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>("default");
  const [registering, setRegistering] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const ok = "Notification" in window && "serviceWorker" in navigator;
    setSupported(ok);
    if (ok) setPermission(Notification.permission);
  }, []);

  if (!supported) return null;

  async function enable() {
    setRegistering(true);
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      if (result !== "granted") {
        toast.push("Notificaciones denegadas por el sistema.", "warning");
        return;
      }
      // Subscribe to the SW push registration if the backend exposes it; this is
      // best-effort — if `/push/subscribe` is not implemented yet we still keep
      // local in-app notifications working.
      const reg = await navigator.serviceWorker.ready;
      try {
        const sub = await reg.pushManager.getSubscription();
        if (!sub) {
          // Without VAPID we cannot create a real push subscription, but we
          // post a hint to the backend so it can opt the channel in later.
          await client.post("/system/notifications/optin", {
            wants_push: true,
            user_agent: navigator.userAgent
          }).catch(() => undefined);
        }
        toast.push("Notificaciones activadas en este dispositivo.", "success");
      } catch {
        toast.push("Notificaciones in-app activadas (push externo no disponible).", "info");
      }
    } finally {
      setRegistering(false);
    }
  }

  if (permission === "granted") {
    return (
      <span className="row" style={{ gap: 7 }}>
        <span className="dot ok" aria-hidden="true" />
        <span className="muted small">Notificaciones del sistema activadas</span>
      </span>
    );
  }

  return (
    <button className="ghost small" type="button" onClick={enable} disabled={registering}>
      <Icon name="bell" size={14} />
      {permission === "denied" ? "Permisos bloqueados" : "Activar push del sistema"}
    </button>
  );
}

export function NotificationCenter({
  open,
  onClose,
  client,
  items,
  onNavigate
}: {
  open: boolean;
  onClose: () => void;
  client: ApiClient;
  items: Item[];
  onNavigate: (tab: Tab) => void;
}) {
  const [seen, setSeen] = useState<Set<string>>(() => new Set());
  const panelRef = useRef<HTMLElement | null>(null);

  useFocusTrap(panelRef, open);

  useEffect(() => {
    setSeen(loadSeen());
  }, []);

  // ESC closes the panel — pair with the focus trap so the user can always
  // bail out via keyboard.
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    // When the panel opens, mark every visible id as seen.
    const next = new Set(seen);
    for (const it of items) next.add(it.id);
    setSeen(next);
    persistSeen(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  return (
    <>
      <div className="panel-backdrop" onClick={onClose} role="presentation" />
      <aside
        ref={panelRef}
        className="side-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Centro de notificaciones"
        tabIndex={-1}
      >
        <header className="side-panel-head">
          <div className="row" style={{ gap: 10 }}>
            <span className="brand-mark" style={{ width: 28, height: 28, borderRadius: 8 }}>
              <Icon name="bell" size={14} strokeWidth={2} />
            </span>
            <div className="stack" style={{ gap: 0 }}>
              <strong>Notificaciones</strong>
              <span className="faint small">{items.length} eventos recientes</span>
            </div>
          </div>
          <button className="ghost icon" onClick={onClose} type="button" aria-label="Cerrar">
            <Icon name="close" size={16} />
          </button>
        </header>

        <div className="side-panel-body">
          <PushControls client={client} />
          <hr className="divider" />
          {items.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">
                <Icon name="inbox" size={20} />
              </span>
              <strong>Todo tranquilo</strong>
              <span className="empty-msg">
                Cuando lleguen aprobaciones, jobs o eventos de auditoría aparecerán aquí.
              </span>
            </div>
          ) : (
            items.map((item) => {
              const isUnread = !seen.has(item.id);
              return (
                <button
                  key={item.id}
                  className={`notif${isUnread ? " unread" : ""}`}
                  onClick={() => {
                    onNavigate(item.target);
                    onClose();
                  }}
                  type="button"
                  style={{ textAlign: "left" }}
                >
                  <span className={`notif-mark ${item.tone}`} aria-hidden="true">
                    <Icon name={item.icon} size={15} />
                  </span>
                  <span className="notif-body">
                    <span className="notif-title">{item.title}</span>
                    <span className="notif-text ellipsis">{item.text}</span>
                  </span>
                  <span className="notif-time">{relativeTime(new Date(item.ts).toISOString())}</span>
                </button>
              );
            })
          )}
        </div>
      </aside>
    </>
  );
}

/**
 * Hook used by the App shell — exposes the unread count derived from the
 * persisted `SEEN_KEY` set against the current notification feed.
 */
export function useUnreadCount(items: Item[]): number {
  const [seen, setSeen] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    setSeen(loadSeen());
    const onStorage = (event: StorageEvent) => {
      if (event.key === SEEN_KEY) setSeen(loadSeen());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  return useMemo(() => items.filter((it) => !seen.has(it.id)).length, [items, seen]);
}
