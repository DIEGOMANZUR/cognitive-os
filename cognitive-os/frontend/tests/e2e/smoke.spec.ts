import { expect, test } from "@playwright/test";

import {
  filterUnexpectedErrors,
  readJwt,
  seedAuth,
  tabButton,
  watchPageHealth,
} from "./_helpers";

test.describe("smoke: el panel carga y se autentica", () => {
  test("home renderiza Sidebar sin errores 5xx ni console.error", async ({
    page,
  }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");

    // La navegación principal debe existir en la primera pantalla.
    await expect(tabButton(page, "Dashboard")).toBeVisible();

    // El JWT seedeado debe estar persistido sin ocupar espacio visual permanente.
    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("cogos.token")))
      .toBe(JSON.stringify(jwt));

    // No debería haber respuestas 5xx en el primer paint.
    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);

    health.dispose();
  });

  test("Dashboard muestra métricas vivas (no spinner infinito)", async ({
    page,
  }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");

    // Tab Dashboard ya está activo por default. Las métricas se obtienen
    // por polling; esperamos a que la card "Estado global" muestre un
    // valor distinto a "…" o "Consultando…".
    const card = page.getByText("Estado global", { exact: false });
    await expect(card).toBeVisible();

    // El metric value queda en un <strong> dentro de la MetricCard:
    // si decae a "?" o queda eterno en "…", esto detecta el problema.
    await expect
      .poll(
        async () =>
          (await page.getByText(/\d+\/\d+ componentes ok/).count()) > 0,
        { timeout: 15_000, message: "Dashboard nunca pintó el conteo de componentes" },
      )
      .toBeTruthy();

    expect(health.serverErrors).toEqual([]);
    health.dispose();
  });
});
