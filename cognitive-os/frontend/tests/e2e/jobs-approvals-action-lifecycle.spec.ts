import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

test.describe("jobs approvals action lifecycle", () => {
  test("approval dispatch and job event are visible", async ({ page }) => {
    await installCommercialApiMocks(page);
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    await page.goto("/");
    await tabButton(page, "Aprobaciones").click();
    await expect(page.getByRole("heading", { name: "Aprobaciones humanas" })).toBeVisible();
    await page.getByRole("button", { name: /Aprobar/ }).first().click();
    await expect(page.getByText(/acción despachada/i)).toBeVisible();

    await tabButton(page, "Jobs").click();
    await expect(page.getByText("action_request")).toBeVisible();
    await page.getByRole("button", { name: /Ver/ }).first().click();
    await expect(page.getByText("action_request_dispatch_submitted")).toBeVisible();

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
