/**
 * Fase 78 — smoke test for the Recetas propuestas section in MemoryView.
 *
 * Asserts only DOM shape: that the new section header renders and the
 * "Extraer ahora" button is wired up. Does not validate live recipe
 * data, since that depends on the backend extractor and a populated
 * `deepagent_memory_proposals` table.
 */

import { expect, test } from "@playwright/test";

import { filterUnexpectedErrors, readJwt, seedAuth, tabButton, watchPageHealth } from "./_helpers";

test.describe("Fase 78 — Recetas propuestas en MemoryView", () => {
  // NOTA F78: este spec comparte el helper `seedAuth` con auth/smoke/
  // navigation/forms/responsive. Al cierre de F78 esos 10 specs fallan
  // en este entorno con el mismo síntoma (el input "JWT local" no
  // recibe el valor seedeado en localStorage — value=""). El backend
  // y el endpoint `/deepagents/memory/recipes` están verificados live;
  // dejar el spec aquí garantiza que cuando el seedAuth se arregle
  // (F79+), esta cobertura quede activa sin tocar más código.
  test("la tab Memoria muestra la sección de recetas y su botón Extraer ahora", async ({
    page,
  }) => {
    const jwt = readJwt();
    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");
    await tabButton(page, "Memoria").click();

    // Encabezado de la sección. El conteo viene entre paréntesis, así que
    // matcheamos por la parte estable del texto.
    const recipesHeader = page
      .locator('section[data-testid="recipe-proposals-section"] >> h2')
      .filter({ hasText: /Recetas propuestas/ });
    await expect(recipesHeader).toBeVisible({ timeout: 10_000 });

    // Botón admin que dispara el extractor inmediato. Debe estar habilitado
    // por defecto (el role del JWT seedeado en _helpers es admin).
    await expect(page.getByRole("button", { name: "Extraer ahora" })).toBeVisible();

    // El estado "Cargando…" o "Sin recetas pendientes." aparece según si
    // el backend respondió a tiempo; cualquiera de los dos es válido para
    // el smoke (la lógica de render del payload se cubre con tests
    // unitarios del extractor en el backend).
    const emptyOrLoading = page.locator(
      'section[data-testid="recipe-proposals-section"] >> text=/Sin recetas pendientes\\.|Cargando…/'
    );
    await expect(emptyOrLoading).toBeVisible({ timeout: 15_000 });

    // Smoke: no debe haber 5xx ni errores inesperados de consola.
    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
  });
});
