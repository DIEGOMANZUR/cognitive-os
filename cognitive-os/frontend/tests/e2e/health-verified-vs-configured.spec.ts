import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

test.describe("health: verified vs configured", () => {
  test("configured is visible as warning, not green and not danger", async ({ page }) => {
    await installCommercialApiMocks(page, { healthStatus: "configured" });
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    await page.goto("/");
    await expect(page.locator(".sidebar-foot .badge.warn")).toHaveText("configured");
    await tabButton(page, "Health").click();
    await expect(page.getByRole("heading", { name: "Health dashboard" })).toBeVisible();
    await expect(page.getByText("Provider is configured; live call skipped")).toBeVisible();
    await expect(page.getByRole("button", { name: /Verificar en vivo/ })).toBeEnabled();

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
