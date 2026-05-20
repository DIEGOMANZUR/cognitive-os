import { expect, test } from "@playwright/test";

import {
  filterUnexpectedErrors,
  readJwt,
  seedAuth,
  tabButton,
  watchPageHealth,
} from "./_helpers";

/**
 * Esta spec corre SÓLO bajo el proyecto `chromium-mobile`
 * (viewport Pixel 5: 393x851). Verifica que en mobile:
 * - Sidebar colapsa (el botón "Abrir menú" aparece),
 * - se puede abrir/cerrar,
 * - se puede navegar a una tab sin overflow horizontal.
 */
test.describe("responsive: el panel funciona en viewport mobile", () => {
  test("Sidebar colapsa y reabre con el hamburger", async ({ page }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");

    // En mobile el sidebar arranca cerrado y el botón hamburger aparece.
    const hamburger = page.getByRole("button", { name: "Abrir menú", exact: true });
    await expect(hamburger).toBeVisible();
    await hamburger.click();

    // El botón de cerrar aparece dentro del drawer abierto.
    const closeBtn = page.getByRole("button", { name: "Cerrar", exact: true });
    await expect(closeBtn).toBeVisible();

    // Navegamos a Health desde mobile.
    await tabButton(page, "Health").click();

    // El drawer puede auto-cerrarse después del click. Si sigue abierto,
    // el cerrar funciona.
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
    }

    // Verificamos que no haya overflow horizontal global: documentWidth
    // <= viewportWidth + un margen razonable.
    const overflow = await page.evaluate(() => ({
      doc: document.documentElement.scrollWidth,
      view: document.documentElement.clientWidth,
    }));
    expect(overflow.doc).toBeLessThanOrEqual(overflow.view + 4);

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
