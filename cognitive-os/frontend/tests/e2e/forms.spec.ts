import { expect, test } from "@playwright/test";

import {
  filterUnexpectedErrors,
  readJwt,
  seedAuth,
  tabButton,
  watchPageHealth,
} from "./_helpers";

/**
 * Cubrimos los 2 formularios que NO disparan acciones externas
 * irreversibles:
 *  - Settings → "Guardar" (commit local del JWT).
 *  - Settings → "API base" (commit local de la URL).
 *
 * El form de Chat dispararía un LLM real → costo + side effects. Lo
 * dejamos fuera de la suite automatizada.
 */
test.describe("forms: persistencia local desde Settings", () => {
  test("Guardar API base + JWT actualiza localStorage", async ({ page }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");
    await tabButton(page, "Conexión").click();

    // SettingsView muestra dos inputs: API base y JWT. Cambiamos la API
    // base, hacemos Guardar y verificamos el localStorage.
    const apiBaseInput = page.getByLabel("API base");
    const apiBase = process.env.COGOS_API_BASE ?? "http://127.0.0.1:8000";
    await apiBaseInput.fill(apiBase);
    await page.getByRole("button", { name: "Guardar", exact: true }).click();

    const stored = await page.evaluate(() =>
      window.localStorage.getItem("cogos.api"),
    );
    expect(stored).toContain(apiBase);

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("Settings rechaza un JWT vacío sin romper la UI", async ({ page }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");
    await tabButton(page, "Conexión").click();

    // Borrar el JWT y guardar — debe quedar persistido como string vacío
    // sin que el SPA crashee.
    const jwtInput = page.getByLabel("JWT sin prefijo Bearer");
    await jwtInput.fill("");
    await page.getByRole("button", { name: "Guardar", exact: true }).click();

    const stored = await page.evaluate(() =>
      window.localStorage.getItem("cogos.token"),
    );
    expect(stored).toBe(JSON.stringify(""));

    // El Sidebar sigue navegable.
    await tabButton(page, "Dashboard").click();

    expect(health.serverErrors).toEqual([]);
    health.dispose();
  });
});
