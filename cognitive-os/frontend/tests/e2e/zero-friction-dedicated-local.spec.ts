import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

test.describe("zero friction dedicated local", () => {
  test("system view exposes full local autonomy without strict contamination", async ({ page }) => {
    await installCommercialApiMocks(page);
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    await page.goto("/");
    await tabButton(page, "Sistema").click();
    await expect(page.getByText("dedicated_local")).toBeVisible();
    await expect(page.getByText("full")).toBeVisible();
    await expect(page.getByText(/require_human_approval_for_external_actions/i)).toBeVisible();

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
