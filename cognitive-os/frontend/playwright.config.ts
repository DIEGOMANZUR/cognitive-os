import { defineConfig, devices } from "@playwright/test";

/**
 * Cognitive OS — E2E config.
 *
 * The app is a Next.js SPA at http://localhost:3001 backed by a FastAPI
 * at http://127.0.0.1:8000. Both must be running BEFORE invoking the
 * suite — see docs/qa/RUNBOOK.md §1.
 *
 * Token strategy (zero-friction for `dedicated_local/full`):
 *
 *   1. If `COGOS_JWT` is exported by the caller, the suite uses it as-is
 *      (CI, strict profile, custom tokens).
 *   2. Otherwise `_global-setup.ts` auto-mints one via
 *      `POST /auth/local-token` against `COGOS_API_BASE` (defaulting to
 *      `http://127.0.0.1:8000`). That endpoint only accepts the call in
 *      `dedicated_local/full`; in any other profile it 403s and the
 *      individual tests still emit a clear "set COGOS_JWT manually"
 *      message via `_helpers.ts::readJwt()`.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  globalSetup: require.resolve("./tests/e2e/_global-setup"),
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  use: {
    baseURL: process.env.COGOS_BASE_URL ?? "http://localhost:3001",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
    // The cockpit ships a service worker (PWA). Across test runs a stale
    // SW registration can keep returning cached chunks from a previous
    // build — that surfaces as MIME-type errors and 500s on chunk URLs
    // that no longer exist. Blocking SW registration in tests + disabling
    // the HTTP cache keeps the suite deterministic without weakening the
    // actual SW in production.
    serviceWorkers: "block",
    launchOptions: {
      args: ["--disable-application-cache", "--disable-cache"],
    },
    extraHTTPHeaders: {
      "Cache-Control": "no-store",
    },
  },
  expect: {
    timeout: 7_000,
  },
  projects: [
    {
      name: "chromium-desktop",
      testIgnore: /responsive\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
    {
      name: "chromium-mobile",
      testMatch: /responsive\.spec\.ts/,
      use: { ...devices["Pixel 5"] },
    },
  ],
});
