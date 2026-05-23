import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

test.describe("commercial zero friction smoke", () => {
  test("dashboard, health, mail, jobs and approvals render with diagnostics", async ({ page }) => {
    await installCommercialApiMocks(page, { healthStatus: "configured" });
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    await page.goto("/");
    await expect(page.getByText("Estado global")).toBeVisible();
    for (const label of ["Health", "Mail", "Jobs", "Aprobaciones"] as const) {
      await tabButton(page, label).click();
      await expect(tabButton(page, label)).toHaveClass(/active/);
      await expect(page.locator("body")).not.toContainText("Algo falló en esta vista");
    }

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
