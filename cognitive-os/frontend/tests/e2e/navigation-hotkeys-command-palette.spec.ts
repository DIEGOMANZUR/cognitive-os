import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

test.describe("navigation: hotkeys and command palette", () => {
  test("keyboard shortcut and command palette navigate without errors", async ({ page }) => {
    await installCommercialApiMocks(page);
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    await page.goto("/");
    await page.getByRole("heading", { name: "Operations Dashboard" }).click();
    await page.keyboard.press("9");
    await expect(tabButton(page, "Health")).toHaveClass(/active/);

    await page.getByRole("button", { name: "Abrir buscador de comandos" }).click();
    await expect(page.getByRole("dialog", { name: "Paleta de comandos" })).toBeVisible();
    await page.getByLabel("Buscar acción").fill("Jobs");
    await page.keyboard.press("Enter");
    await expect(tabButton(page, "Jobs")).toHaveClass(/active/);

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
