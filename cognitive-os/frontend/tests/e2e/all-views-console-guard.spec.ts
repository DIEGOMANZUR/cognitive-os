import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { TAB_LABELS, filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

test.describe("commercial guard: all views", () => {
  test("all 20 views mount under hermetic API mocks without console/page errors", async ({ page }) => {
    await installCommercialApiMocks(page);
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    await page.goto("/");
    for (const label of TAB_LABELS) {
      const button = tabButton(page, label);
      await expect(button).toBeVisible();
      await button.click();
      await expect(button).toHaveClass(/active/);
      await expect(page.locator("body")).not.toContainText("Algo falló en esta vista");
    }

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
