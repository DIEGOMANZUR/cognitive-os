import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

async function boot(page: Parameters<typeof watchPageHealth>[0]) {
  await seedMockAuth(page);
  const health = watchPageHealth(page);
  await page.goto("/");
  await expect(page.getByText("Estado global")).toBeVisible();
  return health;
}

test.describe("commercial fixtures: critical UI flows", () => {
  test("health general and degraded backend state stay diagnostic", async ({ page }) => {
    await installCommercialApiMocks(page, { scenario: "degraded" });
    const health = await boot(page);

    await tabButton(page, "Health").click();
    await expect(page.getByText("degraded").first()).toBeVisible();
    await expect(page.getByText("operational_backlog")).toBeVisible();

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("jobs dashboard, failed job and retryable diagnostics are visible", async ({ page }) => {
    await installCommercialApiMocks(page, { scenario: "retryable_job" });
    const health = await boot(page);

    await tabButton(page, "Jobs").click();
    await expect(page.getByRole("heading", { name: "Jobs" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "failed" })).toBeVisible();
    await page.getByRole("button", { name: /Ver/ }).first().click();
    await expect(page.getByText("fixture_retry_available")).toBeVisible();
    await expect(page.getByRole("cell", { name: /Fixture failure is retryable/i })).toBeVisible();

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("jobs lifecycle shows running progress and event history", async ({ page }) => {
    await installCommercialApiMocks(page, { scenario: "populated" });
    const health = await boot(page);

    await tabButton(page, "Jobs").click();
    await expect(page.getByRole("cell", { name: "running" })).toBeVisible();
    await expect(page.getByText("50%")).toBeVisible();
    await page.getByRole("button", { name: /Ver/ }).first().click();
    await expect(page.getByText("action_request_dispatch_submitted")).toBeVisible();
    await expect(page.getByRole("cell", { name: "Dispatch submitted" })).toBeVisible();

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("failed job UX exposes diagnostic event without crashing", async ({ page }) => {
    await installCommercialApiMocks(page, { scenario: "failed_job" });
    const health = await boot(page);

    await tabButton(page, "Jobs").click();
    await expect(page.getByRole("cell", { name: "document_analysis" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "failed" })).toBeVisible();
    await page.getByRole("button", { name: /Ver/ }).first().click();
    await expect(page.getByText("fixture_failed")).toBeVisible();
    await expect(page.getByRole("cell", { name: /visible diagnostics/i })).toBeVisible();

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("approvals/action lifecycle dispatches only fixture-safe action", async ({ page }) => {
    await installCommercialApiMocks(page, { scenario: "pending_approval" });
    const health = await boot(page);

    await tabButton(page, "Aprobaciones").click();
    await expect(page.getByText("1 pendientes")).toBeVisible();
    await expect(page.getByText("computer_organize")).toBeVisible();
    await page.getByRole("button", { name: /Aprobar/ }).first().click();
    await expect(page.getByText(/acción despachada/i)).toBeVisible();

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("mail read-only digest preview proposes text without send or draft", async ({ page }) => {
    await installCommercialApiMocks(page, { scenario: "mail_digest_read_only" });
    const health = await boot(page);

    await tabButton(page, "Mail").click();
    await expect(page.getByRole("button", { name: "Sync por worker" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Generar resumen 50" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Enviar|Crear draft|Borrador/i })).toHaveCount(0);
    await page.getByRole("button", { name: "Generar resumen 50" }).click();
    await expect(page.locator("textarea").first()).toHaveValue("Resumen mock.");

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("mail read-only and digest-disabled states never expose normal send/draft", async ({ page }) => {
    await installCommercialApiMocks(page, { scenario: "mail_digest_disabled" });
    const health = await boot(page);

    await tabButton(page, "Mail").click();
    await expect(page.getByText("mail desactivado")).toBeVisible();
    await expect(page.getByText("send bloqueado")).toBeVisible();
    await expect(page.getByRole("button", { name: /Generar resumen/ })).toBeDisabled();
    await expect(page.getByRole("button", { name: /Enviar|Crear borrador/i })).toHaveCount(0);

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("zero-friction dedicated local exposes full autonomy without strict contamination", async ({
    page,
  }) => {
    await installCommercialApiMocks(page, { scenario: "populated" });
    const health = await boot(page);

    await tabButton(page, "Sistema").click();
    await expect(page.getByText("dedicated_local")).toBeVisible();
    await expect(page.getByText("full")).toBeVisible();
    await expect(page.getByText(/require_human_approval_for_external_actions/i)).toBeVisible();

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("malformed API state falls back to empty/error states without white screen", async ({ page }) => {
    await installCommercialApiMocks(page, { scenario: "malformed_api_state" });
    const health = await boot(page);

    for (const label of ["Jobs", "Aprobaciones", "Audit log"] as const) {
      await tabButton(page, label).click();
      await expect(page.locator("body")).not.toContainText("Algo falló en esta vista");
      await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
    }

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("mobile-friendly fixture keeps navigation and core panes visible", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installCommercialApiMocks(page, { scenario: "mobile_friendly_state" });
    const health = await boot(page);

    await page.getByRole("button", { name: "Abrir menú" }).click();
    await tabButton(page, "Health").click();
    await expect(page.getByRole("heading", { name: "Health" })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("Algo falló en esta vista");

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
