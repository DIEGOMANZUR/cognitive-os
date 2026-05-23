"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiClient } from "./api";

type PolledState<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
  refetch: () => Promise<void>;
};

/**
 * Polling fetch hook with PWA-aware backoff.
 *
 * Beyond the basic fetch loop, we add three resiliency rules that matter
 * once the cockpit is installed as a PWA:
 *
 * 1. **Offline pause.** While `navigator.onLine === false` we skip the
 *    network call entirely. The cached data stays visible and `error`
 *    holds the "Sin conexión" notice. As soon as `online` flips back
 *    true we fire a fresh refetch immediately (no waiting for the next
 *    interval tick).
 * 2. **Visibility pause.** While `document.visibilityState !== "visible"`
 *    we drop the interval, so a hidden tab doesn't keep hammering the
 *    backend in the background (and doesn't drain the battery on
 *    laptops/phones in standby). The first refetch on re-visibility is
 *    instant.
 * 3. **Loading flag.** Distinguishes "never fetched yet" from "fetched
 *    once, polling again" so views can show a skeleton on the first
 *    load without flashing on every poll. `loading` is `true` only
 *    while data is still `null`.
 *
 * The hook is otherwise a drop-in replacement for the previous version —
 * the `{ data, error, refetch }` shape is preserved, with `loading`
 * added as an extra field.
 */
export function usePolledFetch<T>(
  client: ApiClient,
  path: string | null,
  intervalMs = 5000
): PolledState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const requestId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const dataRef = useRef<T | null>(null);

  // Keep `dataRef` in sync so the offline branch can decide whether to
  // surface the "Sin conexión" error without flickering away cached data.
  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  const fetchOnce = useCallback(async () => {
    if (!path) return;
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      // Offline — keep whatever cached data we already have, surface a
      // friendly error so views can render the "no conexión" empty state.
      setError("Sin conexión — usando datos en caché.");
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const currentRequest = requestId.current + 1;
    requestId.current = currentRequest;
    if (dataRef.current == null) setLoading(true);
    try {
      const json = await client.get<T>(path, true, controller.signal);
      if (requestId.current === currentRequest) {
        setData(json);
        setError(null);
      }
    } catch (caught) {
      if (controller.signal.aborted) return;
      if (requestId.current === currentRequest) {
        setError(caught instanceof Error ? caught.message : "Error");
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
      if (requestId.current === currentRequest) {
        setLoading(false);
      }
    }
  }, [client, path]);

  useEffect(() => {
    requestId.current += 1;
    setData(null);
    setError(null);
    setLoading(Boolean(path));
    if (!path) return;
    void fetchOnce();

    let handle: number | undefined;
    const startInterval = () => {
      if (intervalMs <= 0) return;
      if (handle !== undefined) return;
      handle = window.setInterval(() => void fetchOnce(), intervalMs);
    };
    const stopInterval = () => {
      if (handle === undefined) return;
      window.clearInterval(handle);
      handle = undefined;
    };

    const refreshGuards = () => {
      const offline = typeof navigator !== "undefined" && navigator.onLine === false;
      const hidden = typeof document !== "undefined" && document.visibilityState === "hidden";
      if (offline || hidden) {
        stopInterval();
      } else {
        startInterval();
      }
    };

    const onOnline = () => {
      refreshGuards();
      void fetchOnce();
    };
    const onOffline = () => {
      refreshGuards();
      setError("Sin conexión — usando datos en caché.");
    };
    const onVisibility = () => {
      refreshGuards();
      if (document.visibilityState === "visible") {
        void fetchOnce();
      }
    };

    refreshGuards();
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      requestId.current += 1;
      abortRef.current?.abort();
      abortRef.current = null;
      stopInterval();
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [fetchOnce, path, intervalMs]);

  return { data, error, loading, refetch: fetchOnce };
}

export function useLocalState<T>(key: string, initial: T): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(initial);
  useEffect(() => {
    const raw = localStorage.getItem(key);
    if (raw === null) return;
    try {
      setValue(JSON.parse(raw) as T);
    } catch {
      // ignore broken stored value
    }
  }, [key]);
  const update = useCallback(
    (next: T) => {
      setValue(next);
      try {
        localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // storage unavailable: still update in-memory state
      }
    },
    [key]
  );
  return [value, update];
}

export function useKeyboard(handler: (event: KeyboardEvent) => void): void {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const listener = (event: KeyboardEvent) => ref.current(event);
    window.addEventListener("keydown", listener, { capture: true });
    return () => window.removeEventListener("keydown", listener, { capture: true });
  }, []);
}

/** Avoid hydration mismatches for anything that depends on `Date.now()` or browser-only APIs. */
export function useHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    setHydrated(true);
  }, []);
  return hydrated;
}

/**
 * Live online status. Same source of truth `usePolledFetch` uses,
 * exposed for views that want a banner.
 */
export function useOnline(): boolean {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    if (typeof window === "undefined") return;
    setOnline(navigator.onLine);
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}
