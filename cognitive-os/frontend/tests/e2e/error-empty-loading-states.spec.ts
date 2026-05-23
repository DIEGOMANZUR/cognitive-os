import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

test.describe("error empty loading states", () => {
  test("malformed list payloads degrade to empty states without ErrorBoundary", async ({ page }) => {
    await installCommercialApiMocks(page, { malformedLists: true });
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    await page.goto("/");
    await tabButton(page, "DeepAgents").click();
    await expect(page.locator("body")).not.toContainText("Algo falló en esta vista");
    await tabButton(page, "Jobs").click();
    await expect(page.getByText("Sin jobs para este filtro")).toBeVisible();

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
