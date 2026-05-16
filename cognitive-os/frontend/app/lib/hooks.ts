"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiClient } from "./api";

export function usePolledFetch<T>(
  client: ApiClient,
  path: string | null,
  intervalMs = 5000
): { data: T | null; error: string | null; refetch: () => Promise<void> } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const fetchOnce = useCallback(async () => {
    if (!path) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const currentRequest = requestId.current + 1;
    requestId.current = currentRequest;
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
    }
  }, [client, path]);

  useEffect(() => {
    requestId.current += 1;
    setData(null);
    setError(null);
    void fetchOnce();
    if (!path || intervalMs <= 0) return;
    const handle = setInterval(() => void fetchOnce(), intervalMs);
    return () => {
      requestId.current += 1;
      abortRef.current?.abort();
      abortRef.current = null;
      clearInterval(handle);
    };
  }, [fetchOnce, path, intervalMs]);

  return { data, error, refetch: fetchOnce };
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
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
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
