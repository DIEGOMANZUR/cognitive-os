import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

test.describe("mail readonly contract", () => {
  test("mail UI exposes digest/sync but no normal send or draft action", async ({ page }) => {
    await installCommercialApiMocks(page);
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    await page.goto("/");
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
});
