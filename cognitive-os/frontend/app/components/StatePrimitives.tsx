"use client";

import type { ReactNode } from "react";

import { Icon, type IconName } from "./Icon";

/**
 * Tiny, opinionated state primitives shared by every view in the cockpit.
 *
 * Each view consumes a polled fetch hook and needs to render one of four
 * states: loading (skeleton), error (recovery panel), empty (helpful
 * placeholder), or the real content. Centralising them keeps the visual
 * language uniform — colour, icon, spacing, copy tone — and means a tweak
 * to the design system is a one-file change.
 */

export function Skeleton({
  rows = 3,
  height = 13,
  gap = 8
}: {
  rows?: number;
  height?: number;
  gap?: number;
}) {
  return (
    <div className="stack" style={{ gap }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{ height, width: `${88 - (i % 3) * 8}%` }}
          aria-hidden="true"
        />
      ))}
      <span className="sr-only">Cargando…</span>
    </div>
  );
}

export function EmptyState({
  icon = "inbox",
  title,
  message,
  action
}: {
  icon?: IconName;
  title: string;
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state" role="status">
      <span className="empty-icon" aria-hidden="true">
        <Icon name={icon} size={18} />
      </span>
      <strong>{title}</strong>
      {message && <span className="empty-msg">{message}</span>}
      {action && <span style={{ marginTop: 4 }}>{action}</span>}
    </div>
  );
}

export function ErrorPanel({
  error,
  onRetry,
  hint
}: {
  error: string;
  onRetry?: () => void;
  hint?: string;
}) {
  return (
    <div
      className="warn-box stack"
      role="alert"
      style={{
        borderColor: "rgba(255, 111, 111, 0.45)",
        background: "var(--danger-soft)",
        gap: 8
      }}
    >
      <span className="row" style={{ gap: 8 }}>
        <Icon name="alert" size={15} />
        <strong>No se pudo cargar</strong>
      </span>
      <span className="small muted" style={{ wordBreak: "break-word" }}>
        {error}
      </span>
      {hint && <span className="faint small">{hint}</span>}
      {onRetry && (
        <div>
          <button type="button" className="small" onClick={onRetry}>
            <Icon name="refresh" size={13} /> Reintentar
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Convenience wrapper that picks the right state primitive based on
 * `{ data, error, loading }` from `usePolledFetch`. Use when the only
 * thing the view does on success is render its children.
 *
 * Usage:
 *   <DataBoundary state={jobs} empty={{ title: "Sin jobs", ... }}>
 *     {(data) => <Table rows={data} />}
 *   </DataBoundary>
 */
export function DataBoundary<T>({
  state,
  empty,
  isEmpty,
  loadingRows = 4,
  children
}: {
  state: {
    data: T | null;
    error: string | null;
    loading: boolean;
    refetch: () => Promise<void>;
  };
  empty: { icon?: IconName; title: string; message?: string };
  isEmpty?: (data: T) => boolean;
  loadingRows?: number;
  children: (data: T) => ReactNode;
}) {
  if (state.error && state.data == null) {
    return <ErrorPanel error={state.error} onRetry={() => void state.refetch()} />;
  }
  if (state.loading && state.data == null) {
    return <Skeleton rows={loadingRows} />;
  }
  if (state.data == null) {
    return <EmptyState {...empty} />;
  }
  if (isEmpty && isEmpty(state.data)) {
    return <EmptyState {...empty} />;
  }
  return <>{children(state.data)}</>;
}
