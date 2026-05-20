import { expect, test } from "@playwright/test";

import {
  TAB_LABELS,
  filterUnexpectedErrors,
  readJwt,
  seedAuth,
  tabButton,
  watchPageHealth,
} from "./_helpers";

/**
 * Navega secuencialmente por las 20 tabs y verifica que cada vista:
 * - se monta sin lanzar excepción (sin pantalla blanca),
 * - no produce respuestas 5xx en la API,
 * - no genera `console.error` no tolerado.
 *
 * Las tabs no cambian URL — el `tab` vive en el state del SPA — por lo
 * que esperamos visualmente por el cambio de contenido (el `<button
 * className="active">`) en vez de `waitForURL`.
 */
test.describe("navigation: las 20 tabs montan sin romper", () => {
  test("recorrido completo del Sidebar", async ({ page }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");
    await expect(tabButton(page, "Dashboard")).toBeVisible();

    for (const label of TAB_LABELS) {
      const btn = tabButton(page, label);
      await expect(btn, `Tab "${label}" no es visible en el Sidebar`).toBeVisible();
      await btn.click();
      // El botón activo del Sidebar gana la clase `active`. La esperamos
      // como prueba de que el state cambió de verdad.
      await expect(btn).toHaveClass(/active/);
    }

    // Volvemos a Dashboard para dejar la app en estado conocido.
    await tabButton(page, "Dashboard").click();

    expect(
      health.serverErrors,
      `respuestas 5xx detectadas: ${JSON.stringify(health.serverErrors)}`,
    ).toEqual([]);
    const filtered = filterUnexpectedErrors(health.errors);
    expect(
      filtered,
      `console.error inesperados: ${JSON.stringify(filtered, null, 2)}`,
    ).toEqual([]);
    health.dispose();
  });

  test("la tab elegida persiste tras refresh (cogos.tab en localStorage)", async ({
    page,
  }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);

    await page.goto("/");
    await tabButton(page, "Health").click();

    // El estado del SPA queda en localStorage bajo `cogos.tab`. Refrescamos
    // y debe seguir mostrando Health activo.
    await page.reload();
    const healthBtn = tabButton(page, "Health");
    await expect(healthBtn).toBeVisible();
    await expect(healthBtn).toHaveClass(/active/);
  });
});
