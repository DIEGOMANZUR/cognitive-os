import { defineConfig, devices } from "@playwright/test";

/**
 * Cognitive OS — E2E config (Fase 76 QA audit).
 *
 * The app is a Next.js SPA at http://localhost:3001 backed by a FastAPI
 * at http://127.0.0.1:8000. Both must be running BEFORE invoking the
 * suite — see docs/qa/RUNBOOK.md §1.
 *
 * The token is minted out-of-band and injected via the COGOS_JWT env var
 * so the suite never hardcodes secrets nor depends on the live mint
 * endpoint (which is admin-only).
 */
export default defineConfig({
  testDir: "./tests/e2e",
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
