import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

test.describe("mobile PWA shell", () => {
  test("mobile drawer opens, navigates, and keeps content visible", async ({ page }) => {
    await page.setViewportSize({ width: 393, height: 851 });
    await installCommercialApiMocks(page);
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    await page.goto("/");
    await page.getByLabel("Abrir menú").click();
    await tabButton(page, "Health").click();
    await expect(page.getByRole("heading", { name: "Health dashboard" })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("Algo falló en esta vista");

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
