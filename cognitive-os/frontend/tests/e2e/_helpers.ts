import type { ConsoleMessage, Locator, Page, Request, Response } from "@playwright/test";

/**
 * Read the JWT from `COGOS_JWT`.
 *
 * In `dedicated_local/full` the runner's global setup auto-mints the token
 * via `POST /auth/local-token` (see `_global-setup.ts`); callers do NOT
 * need to export it manually. In `strict`/`guarded` the mint endpoint
 * 403s and the env var must be supplied by the caller — RUNBOOK §2 has
 * the exact command. We keep this helper synchronous so existing specs
 * don't need to be rewritten as `async`.
 */
export function readJwt(): string {
  const token = process.env.COGOS_JWT?.trim();
  if (!token) {
    throw new Error(
      "COGOS_JWT env var is missing and auto-mint failed. " +
        "If you are in strict/guarded mode, mint it manually — see " +
        "docs/qa/RUNBOOK.md §2. If you are in dedicated_local/full, the " +
        "backend at COGOS_API_BASE (default http://127.0.0.1:8000) must " +
        "be reachable so global-setup can call POST /auth/local-token.",
    );
  }
  return token;
}

/**
 * Seed `localStorage` with the JWT BEFORE the SPA hydrates.
 *
 * The frontend stores its JWT under `cogos.token` (`useLocalState`, Fase
 * 71-H). Setting it via `addInitScript` guarantees the first render of
 * the SPA already has a valid token and the polling hooks fire correctly.
 *
 * `cogos.api` mirrors the API base URL the panel will hit — defaulting to
 * the local backend on :8000.
 */
export async function seedAuth(page: Page, jwt: string): Promise<void> {
  const apiBase = process.env.COGOS_API_BASE ?? "http://127.0.0.1:8000";
  await page.addInitScript(
    ({ jwt, apiBase }) => {
      // `useLocalState` JSON-stringifies the value before storing it.
      window.localStorage.setItem("cogos.token", JSON.stringify(jwt));
      window.localStorage.setItem("cogos.token.source", JSON.stringify("manual"));
      window.localStorage.setItem("cogos.api", JSON.stringify(apiBase));
    },
    { jwt, apiBase },
  );
}

/**
 * Console + network sentinel used by every spec.
 *
 * Captures `console.error`s and any 5xx response. Tests can assert on the
 * `errors` / `serverErrors` arrays after their flow finishes. We INCLUDE
 * 401/403 only if they come from a path the test explicitly hits while
 * authenticated; the polling-only 401 noise that happens before the JWT
 * is seeded is filtered by the caller.
 *
 * Returns `{ errors, serverErrors, dispose }` — `dispose` detaches the
 * listeners so the page can be reused.
 */
export function watchPageHealth(page: Page): {
  errors: { url: string; text: string }[];
  serverErrors: { url: string; status: number }[];
  dispose: () => void;
} {
  const errors: { url: string; text: string }[] = [];
  const serverErrors: { url: string; status: number }[] = [];

  const onConsole = (msg: ConsoleMessage) => {
    if (msg.type() === "error") {
      errors.push({ url: page.url(), text: msg.text() });
    }
  };
  const onResponse = (res: Response) => {
    if (res.status() >= 500) {
      serverErrors.push({ url: res.url(), status: res.status() });
    }
  };
  const onPageError = (err: Error) => {
    errors.push({ url: page.url(), text: `pageerror: ${err.message}` });
  };
  const onRequestFailed = (req: Request) => {
    const failure = req.failure();
    if (!failure) return;
    // `net::ERR_ABORTED` is benign only for GET polling/view-refresh calls
    // cancelled by fast tab navigation. Mutating/critical requests must stay
    // visible to the suite.
    if (failure.errorText.includes("ABORTED") && req.method() === "GET") return;
    errors.push({
      url: req.url(),
      text: `requestfailed: ${failure.errorText}`,
    });
  };

  page.on("console", onConsole);
  page.on("response", onResponse);
  page.on("pageerror", onPageError);
  page.on("requestfailed", onRequestFailed);

  return {
    errors,
    serverErrors,
    dispose: () => {
      page.off("console", onConsole);
      page.off("response", onResponse);
      page.off("pageerror", onPageError);
      page.off("requestfailed", onRequestFailed);
    },
  };
}

/**
 * Known-noise console patterns we tolerate without flunking a test.
 *
 * - PWA service worker registration emits a warning in dev under Next 16.
 * - `webkit2png` etc. only appear under macOS; safe to skip.
 * - Polling timeouts during page-close cleanup.
 */
const TOLERATED_CONSOLE_PATTERNS: RegExp[] = [
  /ServiceWorker.*registration failed/i,
  /AbortError/i,
  /The play\(\) request was interrupted/i,
];

export function filterUnexpectedErrors(
  errors: { url: string; text: string }[],
): { url: string; text: string }[] {
  return errors.filter(
    (e) => !TOLERATED_CONSOLE_PATTERNS.some((re) => re.test(e.text)),
  );
}

/**
 * List of tab buttons that Sidebar renders. Matches the `Tab` union in
 * `app/lib/types.ts`. Used by navigation.spec to iterate over all 20.
 */
export const TAB_LABELS = [
  "Dashboard",
  "Chat",
  "DeepAgents",
  "Skills",
  "Memoria",
  "Asistente",
  "Mail",
  "Documentos",
  "Document Analysis",
  "Jobs",
  "Aprobaciones",
  "Google Ops",
  "Research",
  "Code Director",
  "Sandbox",
  "LangSmith",
  "Audit log",
  "Health",
  "Sistema",
  "Conexión",
] as const;

/**
 * Locate a tab button. The Sidebar renders buttons with composite
 * accessible names like "◧ Dashboard 1" (icon + label + hotkey), so a
 * plain `{ name, exact: true }` does NOT match. We use a substring regex
 * anchored on word boundaries.
 *
 * Section headers (Overview/Agentes/Conocimiento/...) are also `<button>`
 * elements with a "▾"/"▸" caret; they happen to have non-tab labels so
 * the regex naturally skips them.
 */
export function tabButton(page: Page, label: string): Locator {
  const safe = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return page
    .getByRole("button", { name: new RegExp(`\\b${safe}\\b`) })
    .first();
}
