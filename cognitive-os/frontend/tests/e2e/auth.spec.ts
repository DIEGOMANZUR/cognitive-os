import { expect, test } from "@playwright/test";

import {
  filterUnexpectedErrors,
  readJwt,
  seedAuth,
  tabButton,
  watchPageHealth,
} from "./_helpers";

const AUTO_JWT = fakeJwt(Date.now() + 365 * 24 * 60 * 60 * 1000);

/**
 * El panel es un SPA local: en dedicated_local/full debe conseguir su JWT
 * automáticamente, pero sigue permitiendo override manual en TopBar/Conexión.
 */
test.describe("auth: el JWT controla el acceso autenticado", () => {
  test("sin JWT persistido el panel autoprovisiona un JWT local", async ({
    page,
  }) => {
    const health = watchPageHealth(page);
    await page.route("**/auth/local-token", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: AUTO_JWT,
          token_type: "bearer",
          user_id: "local-operator",
          roles: ["admin", "operator"],
          expires_at: "2036-05-20T00:00:00Z",
        }),
      });
    });
    await page.goto("/");

    // Sidebar sigue renderizando y el JWT queda fijo en localStorage.
    await expect(page.getByRole("button", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByLabel("JWT local")).toHaveValue(AUTO_JWT);
    await expect(
      page.getByText("Falta JWT local"),
    ).toHaveCount(0);
    await expect
      .poll(() =>
        page.evaluate(() => window.localStorage.getItem("cogos.token.source")),
      )
      .toBe(JSON.stringify("auto"));

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

function fakeJwt(expiresAtMs: number): string {
  const payload = {
    sub: "local-operator",
    roles: ["admin", "operator"],
    exp: Math.floor(expiresAtMs / 1000),
  };
  return [
    base64Url({ alg: "HS256", typ: "JWT" }),
    base64Url(payload),
    "fake-signature",
  ].join(".");
}

function base64Url(value: unknown): string {
  return Buffer.from(JSON.stringify(value))
    .toString("base64")
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}
