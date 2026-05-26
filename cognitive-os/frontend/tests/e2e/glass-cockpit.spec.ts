import { expect, test } from "@playwright/test";

import {
  filterUnexpectedErrors,
  readJwt,
  seedAuth,
  watchPageHealth
} from "./_helpers";

/**
 * Fase 82 — Glass Cockpit: cobertura de las capacidades nuevas del
 * frontend que no existían en la suite anterior.
 *
 * Cubre:
 *  - Command palette: abre con Ctrl+K, filtra por fuzzy, navega con Enter.
 *  - Notification center: abre desde la command palette, dismiss con ESC.
 *  - Defensive list guards: aún con un endpoint devolviendo `{}` en vez de
 *    array, la vista no cae al ErrorBoundary.
 *  - Skip link: foco visible al tabular desde el body.
 */
test.describe("Fase 82 — Glass Cockpit", () => {
  test("Command palette abre con Ctrl+K, filtra y navega con Enter", async ({ page }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");
    // Sidebar visible primero — confirma el shell montado.
    await expect(page.getByRole("button", { name: /Dashboard/ })).toBeVisible();

    // The `useKeyboard` listener is attached inside a `useEffect`, so it is
    // only live AFTER React hydrates. If we press Ctrl+K before the effect
    // runs, the keystroke is dropped on the floor (the listener simply does
    // not exist yet). To make the test resilient to hydration jitter we
    // re-press until the palette appears or the budget runs out — the
    // production behaviour (single press from the operator) is unaffected.
    const palette = page.getByRole("dialog", { name: "Paleta de comandos" });
    await expect
      .poll(
        async () => {
          if (await palette.isVisible()) return true;
          await page.keyboard.press("Control+k");
          return await palette.isVisible();
        },
        { timeout: 7_000, intervals: [200, 400, 600] },
      )
      .toBe(true);
    await expect(palette).toBeVisible();

    const search = page.getByPlaceholder("¿Qué querés hacer? (ESC para cerrar)");
    await search.fill("Aprob");
    // El primer resultado debe ser "Ir a Aprobaciones".
    await expect(palette.getByText(/Ir a Aprobaciones/)).toBeVisible();

    await page.keyboard.press("Enter");
    // La paleta se cierra y el tab Aprobaciones se activa.
    await expect(palette).toBeHidden();
    await expect(page.getByRole("button", { name: /Aprobaciones/ }).first()).toHaveClass(/active/);

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("Centro de notificaciones abre y cierra con ESC", async ({ page }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");
    await page.getByRole("button", { name: "Abrir centro de notificaciones" }).click();
    const panel = page.getByRole("dialog", { name: "Centro de notificaciones" });
    await expect(panel).toBeVisible();
    // Header con conteo de eventos.
    await expect(panel.getByText(/Notificaciones/)).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(panel).toBeHidden();

    expect(health.serverErrors).toEqual([]);
    health.dispose();
  });

  test("La SPA tolera respuestas de forma incorrecta (asArray guard)", async ({ page }) => {
    // Si el backend devuelve un objeto en vez de array en `/agents`, la vista
    // no debe caer al ErrorBoundary global. Interceptamos solo ese path.
    await page.route("**/agents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
    );

    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");
    await page.getByRole("button", { name: /DeepAgents/ }).click();

    // El ErrorBoundary tiene la cadena "Algo falló en esta vista"; nunca
    // debería verse.
    await expect(page.getByText("Algo falló en esta vista")).toHaveCount(0);
    // En su lugar, vemos el empty state.
    await expect(page.getByText(/Sin DeepAgents registrados/)).toBeVisible();

    expect(health.serverErrors).toEqual([]);
    health.dispose();
  });

  test("Skip-link aparece al recibir foco (a11y)", async ({ page }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);

    await page.goto("/");
    // Tab desde el body lleva al skip-link como primer elemento focuseable.
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Saltar al contenido principal" });
    await expect(skip).toBeFocused();

    // Click sigue el href y enfoca el main.
    await skip.click();
    await expect(page.locator("#cogos-main")).toBeFocused();
  });
});
