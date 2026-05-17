import type { ChatResponse, ResearchEvent, StreamEvent } from "./types";

async function throwResponseError(response: Response): Promise<never> {
  const detail = await parseErrorDetail(response);
  if (response.status === 429) {
    const retryAfter = response.headers.get("Retry-After");
    const suffix = retryAfter ? ` (reintenta en ${retryAfter}s)` : "";
    throw new Error(`429 Too Many Requests: ${detail}${suffix}`);
  }
  throw new Error(`${response.status} ${response.statusText}: ${detail}`);
}

async function parseErrorDetail(response: Response): Promise<string> {
  const body = await response.text();
  if (!body) return "Request failed without response body";

  try {
    const parsed = JSON.parse(body) as unknown;
    if (parsed && typeof parsed === "object" && "detail" in parsed) {
      return formatErrorDetail((parsed as { detail: unknown }).detail);
    }
    return formatErrorDetail(parsed);
  } catch {
    return body;
  }
}

function formatErrorDetail(detail: unknown): string {
  if (detail == null) return "Unknown error";
  if (["string", "number", "boolean"].includes(typeof detail)) return String(detail);
  if (Array.isArray(detail)) {
    const messages = detail.map(formatErrorDetail).filter(Boolean);
    return messages.length ? messages.join("; ") : "Unknown error";
  }
  if (typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    if (typeof record.msg === "string") {
      const loc = Array.isArray(record.loc) ? record.loc.map(String).join(".") : "";
      return loc ? `${loc}: ${record.msg}` : record.msg;
    }
    if ("message" in record) return formatErrorDetail(record.message);
    if ("detail" in record) return formatErrorDetail(record.detail);
    return JSON.stringify(record);
  }
  return String(detail);
}

function normalizeAuthToken(token: string): string {
  return token.trim().replace(/^Bearer\s+/i, "");
}

export class ApiClient {
  constructor(
    private readonly apiBase: string,
    private readonly token: string
  ) {}

  get base(): string {
    return this.apiBase;
  }
  get authToken(): string {
    return normalizeAuthToken(this.token);
  }

  async get<T>(path: string, authenticated = true, signal?: AbortSignal): Promise<T> {
    return this.request<T>(path, { method: "GET", signal }, authenticated);
  }

  async post<T>(path: string, body: unknown, authenticated = true): Promise<T> {
    return this.request<T>(
      path,
      {
        method: "POST",
        body: JSON.stringify(body)
      },
      authenticated
    );
  }

  async patch<T>(path: string, body: unknown, authenticated = true): Promise<T> {
    return this.request<T>(
      path,
      {
        method: "PATCH",
        body: JSON.stringify(body)
      },
      authenticated
    );
  }

  async delete<T>(path: string, authenticated = true): Promise<T> {
    return this.request<T>(path, { method: "DELETE" }, authenticated);
  }

  async streamChat(
    body: unknown,
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal
  ): Promise<ChatResponse | null> {
    const headers = new Headers({ "Content-Type": "application/json" });
    const token = normalizeAuthToken(this.token);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(`${this.apiBase}/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal
    });
    if (!response.ok) {
      await throwResponseError(response);
    }
    if (!response.body) {
      throw new Error(
        `${response.status} ${response.statusText}: Streaming response did not include a readable body`
      );
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let final: ChatResponse | null = null;
    let streamError: string | null = null;
    const handleBlock = (block: string) => {
      if (!block.startsWith("data: ")) return;
      try {
        const event = JSON.parse(block.slice(6).trim()) as StreamEvent;
        onEvent(event);
        if (event.event === "final_response") {
          final = {
            thread_id: String(event.thread_id ?? ""),
            message: String(event.message ?? ""),
            route: String(event.route ?? "unknown"),
            pending_human_review: event.pending_human_review ?? null
          };
        } else if (event.event === "interrupt") {
          final = {
            thread_id: String(event.thread_id ?? ""),
            message: "Human approval required.",
            route: "human_review",
            pending_human_review:
              (event.payload as Record<string, unknown> | null | undefined) ?? null
          };
        } else if (event.event === "error") {
          streamError = String(event.detail ?? "Streaming chat failed");
        }
      } catch {
        // ignore malformed line
      }
    };
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx = buffer.indexOf("\n\n");
      while (idx !== -1) {
        const block = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 2);
        handleBlock(block);
        idx = buffer.indexOf("\n\n");
      }
    }
    buffer += decoder.decode();
    const trailingBlock = buffer.trim();
    if (trailingBlock) {
      handleBlock(trailingBlock);
    }
    if (streamError) {
      throw new Error(streamError);
    }
    return final;
  }

  /**
   * SSE stream for `/research/runs/{run_id}/events`. Uses `fetch` (instead of
   * the native `EventSource`) so we can attach the `Authorization` header that
   * the backend requires. Resolves when the stream emits `done` or the stream
   * ends naturally.
   */
  async streamResearchEvents(
    runId: string,
    onEvent: (event: ResearchEvent) => void,
    signal?: AbortSignal
  ): Promise<void> {
    const headers = new Headers({ Accept: "text/event-stream" });
    const token = normalizeAuthToken(this.token);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(this.buildUrl(`/research/runs/${runId}/events`), {
      method: "GET",
      headers,
      signal
    });
    if (!response.ok) {
      await throwResponseError(response);
    }
    if (!response.body) {
      throw new Error("Research SSE: server did not return a readable body.");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamError: string | null = null;
    const handleBlock = (block: string) => {
      if (!block.startsWith("data: ")) return;
      try {
        const parsed = JSON.parse(block.slice(6).trim()) as ResearchEvent;
        onEvent(parsed);
        if (parsed.event === "error") {
          streamError = String(parsed.detail ?? "Research stream failed");
        }
      } catch {
        // Ignore malformed line — server may emit empty heartbeats.
      }
    };
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx = buffer.indexOf("\n\n");
      while (idx !== -1) {
        const block = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 2);
        handleBlock(block);
        idx = buffer.indexOf("\n\n");
      }
    }
    buffer += decoder.decode();
    const trailing = buffer.trim();
    if (trailing) handleBlock(trailing);
    if (streamError) throw new Error(streamError);
  }

  async streamCodeBuildEvents(
    jobId: string,
    onEvent: (event: Record<string, unknown>) => void,
    signal?: AbortSignal
  ): Promise<void> {
    const headers = new Headers({ Accept: "text/event-stream" });
    const token = normalizeAuthToken(this.token);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(this.buildUrl(`/code-director/${jobId}/events`), {
      method: "GET",
      headers,
      signal
    });
    if (!response.ok) {
      await throwResponseError(response);
    }
    if (!response.body) {
      throw new Error("Code build SSE: server did not return a readable body.");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamError: string | null = null;
    const handleBlock = (block: string) => {
      if (!block.startsWith("data: ")) return;
      try {
        const parsed = JSON.parse(block.slice(6).trim()) as Record<string, unknown>;
        onEvent(parsed);
        if (parsed.event === "error") {
          streamError = String(parsed.detail ?? "Code build stream failed");
        }
      } catch {
        // Ignore malformed line.
      }
    };
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx = buffer.indexOf("\n\n");
      while (idx !== -1) {
        const block = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 2);
        handleBlock(block);
        idx = buffer.indexOf("\n\n");
      }
    }
    buffer += decoder.decode();
    const trailing = buffer.trim();
    if (trailing) handleBlock(trailing);
    if (streamError) throw new Error(streamError);
  }

  buildUrl(path: string): string {
    return `${this.apiBase}${path}`;
  }

  authHeaders(): HeadersInit {
    const token = normalizeAuthToken(this.token);
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async download(path: string): Promise<Blob> {
    const response = await fetch(this.buildUrl(path), { headers: this.authHeaders() });
    if (!response.ok) {
      await throwResponseError(response);
    }
    return response.blob();
  }

  private async request<T>(
    path: string,
    init: RequestInit,
    authenticated = true
  ): Promise<T> {
    const headers = new Headers(init.headers);
    if (init.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    const token = normalizeAuthToken(this.token);
    if (authenticated && token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    const response = await fetch(`${this.apiBase}${path}`, { ...init, headers });
    if (!response.ok) {
      await throwResponseError(response);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }
}

export function errorMessage(caught: unknown): string {
  return caught instanceof Error ? caught.message : "Error desconocido";
}

export function statusClass(status: string): string {
  if (["ok", "completed", "approved", "active", "ready", "sent", "normal"].includes(status)) {
    return "badge ok";
  }
  if (["configured", "disabled", "unknown", "not_enabled", "expired"].includes(status))
    return "badge configured";
  if (
    [
      "running",
      "queued",
      "pending",
      "waiting_approval",
      "pending_approval",
      "pending_send",
      "needs_human_review",
      "needs_approval",
      "partial",
      "needs_more_info",
      "reply_proposed",
      "new",
      "important",
      "promo"
    ].includes(status)
  )
    return "badge warn";
  return "badge danger";
}

export async function downloadBlob(blob: Blob, filename: string): Promise<void> {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
