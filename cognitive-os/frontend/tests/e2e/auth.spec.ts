import { expect, test } from "@playwright/test";

import {
  filterUnexpectedErrors,
  readJwt,
  seedAuth,
  tabButton,
  watchPageHealth,
} from "./_helpers";

/**
 * El panel es un SPA sin login real: el operador pega un JWT en el
 * TopBar y eso desbloquea el polling autenticado. Auditamos los tres
 * casos: sin JWT, JWT inválido y JWT válido.
 */
test.describe("auth: el JWT controla el acceso autenticado", () => {
  test("sin JWT el panel monta y muestra la TopBar pidiendo token", async ({
    page,
  }) => {
    const health = watchPageHealth(page);
    // No seedAuth aquí.
    await page.goto("/");

    // Sidebar sigue renderizando (el panel no se rompe sin JWT).
    await expect(page.getByRole("button", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByLabel("JWT local")).toBeVisible();

    // Aviso esperado: tabs como Health/Dashboard polling con token vacío
    // no pueden devolver 5xx; SI pueden devolver 401, eso es correcto.
    // Sólo flunkeamos 5xx puros.
    expect(health.serverErrors).toEqual([]);
    health.dispose();
  });

  test("pegar un JWT inválido NO rompe el SPA — la API responde 401 pero el UI sigue", async ({
    page,
  }) => {
    const health = watchPageHealth(page);
    await page.goto("/");

    const tokenInput = page.getByLabel("JWT local");
    await tokenInput.fill("token-fake-deliberadamente-roto");
    // El TopBar persiste el JWT directamente via `useLocalState` en el
    // onChange — no hace falta clickear "Aplicar". Disparamos un blur
    // para asegurar el commit del state.
    await tokenInput.blur();

    // El panel sigue montado: el Sidebar respondería a clicks.
    await tabButton(page, "Health").click();
    await expect(
      tabButton(page, "Health"),
    ).toHaveClass(/active/);

    expect(
      health.serverErrors,
      `un JWT inválido NUNCA debe producir 5xx: ${JSON.stringify(health.serverErrors)}`,
    ).toEqual([]);
    health.dispose();
  });

  test("con JWT válido las llamadas autenticadas resuelven 200", async ({
    page,
  }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    const ok200: string[] = [];
    page.on("response", (res) => {
      if (
        res.status() === 200 &&
        res.url().includes("/health/dashboard")
      ) {
        ok200.push(res.url());
      }
    });

    await page.goto("/");
    // Pasamos a Health para forzar el fetch del dashboard.
    await tabButton(page, "Health").click();

    await expect
      .poll(() => ok200.length, { timeout: 15_000 })
      .toBeGreaterThan(0);
    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
