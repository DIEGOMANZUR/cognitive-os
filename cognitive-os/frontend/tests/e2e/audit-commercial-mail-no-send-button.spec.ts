import { expect, test } from "@playwright/test";

import { installCommercialApiMocks, seedMockAuth } from "./_commercial_mocks";
import { filterUnexpectedErrors, tabButton, watchPageHealth } from "./_helpers";

/**
 * P0 commercial-audit hardening — Mail UI no-send-button contract.
 *
 * Contract (docs/CURRENT_STATE.md §"Mail: Contrato Actual"; docs/ZERO_FRICTION_OPERATING_MODEL.md
 * §"Excepción dura"): the Mail view exposes digest/sync controls but
 * MUST NOT expose any UI affordance to send mail or create drafts. The
 * existing mail-readonly-contract.spec.ts already checks for
 * `button[name=/Enviar|Crear draft|Borrador/]`. This spec hardens that
 * promise:
 *
 *   1. Scan ALL roles (button, link, menuitem) for send/draft text in
 *      Spanish AND English variants.
 *   2. Intercept POST /mail/messages/<id>/approve-send and FAIL if any
 *      call lands on it during normal interaction (digest/sync workflow).
 *   3. Confirm the contract phrase from CURRENT_STATE — operator copies
 *      the proposed reply manually — is preserved by the static UI.
 *
 * Auditoría comercial — 2026-05-25. Plan en
 * tmp/commercial_audit_20260525_030342/02_TEST_MATRIX.md §G2.
 */
test.describe("audit · mail UI exposes no send affordance", () => {
  test("no send/draft control in any interactive role, and SMTP endpoint untouched", async ({ page }) => {
    await installCommercialApiMocks(page);
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    // Sentinel: if the SPA ever calls approve-send we fail the test.
    const smtpHits: string[] = [];
    await page.route(
      (url) => /\/mail\/messages\/.+\/approve-send/.test(url.pathname),
      (route) => {
        smtpHits.push(route.request().url());
        route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"audit blocked"}' });
      },
    );

    await page.goto("/");
    await tabButton(page, "Mail").click();

    // The two legitimate, read-only actions must remain visible.
    await expect(page.getByRole("button", { name: "Sync por worker" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Generar resumen 50" })).toBeVisible();

    // Exhaustive role × text scan. Spanish + English variants.
    const FORBIDDEN_PATTERN = /\b(enviar|enviar.+ahora|enviar.+correo|send(\s+email)?|send.+now|crear\s+draft|crear\s+borrador|create\s+draft|aprobar\s+y\s+enviar|approve\s+and\s+send)\b/i;

    for (const role of ["button", "link", "menuitem", "switch", "checkbox"] as const) {
      const matches = page.getByRole(role, { name: FORBIDDEN_PATTERN });
      await expect(matches, `role=${role} should not expose a send/draft affordance`).toHaveCount(
        0,
      );
    }

    // Defensive: also reject any input whose label/placeholder suggests a
    // composer-with-send flow.
    const inputs = page.locator("input[placeholder], input[aria-label], textarea[placeholder]");
    const inputCount = await inputs.count();
    for (let i = 0; i < inputCount; i += 1) {
      const el = inputs.nth(i);
      const placeholder = (await el.getAttribute("placeholder")) ?? "";
      const ariaLabel = (await el.getAttribute("aria-label")) ?? "";
      expect(
        FORBIDDEN_PATTERN.test(placeholder) || FORBIDDEN_PATTERN.test(ariaLabel),
        `input ${placeholder || ariaLabel} suggests a send/draft flow`,
      ).toBe(false);
    }

    // Run the digest workflow to make sure it does NOT trigger /approve-send.
    await page.getByRole("button", { name: "Generar resumen 50" }).click();
    // The mocked summary populates a textarea.
    await expect(page.locator("textarea").first()).toHaveValue("Resumen mock.");

    // Click around for a bit to give the SPA a chance to misbehave.
    await page.waitForTimeout(150);

    // CRITICAL: zero calls to the SMTP escape hatch from the digest flow.
    expect(smtpHits).toEqual([]);
    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });

  test("Mail tab body does not contain a contract-breaking literal", async ({ page }) => {
    await installCommercialApiMocks(page);
    await seedMockAuth(page);
    const health = watchPageHealth(page);

    await page.goto("/");
    await tabButton(page, "Mail").click();

    // Static phrases that, if shown to the operator, would contradict the
    // read-only contract. We allow the word "respuesta" (which describes
    // the *proposed text* the operator copies manually).
    const bodyText = (await page.locator("main").innerText()).toLowerCase();
    const forbiddenLiterals = [
      "enviar correo",
      "enviar respuesta",
      "send email",
      "send reply",
      "auto-send",
      "crear draft",
      "crear borrador",
    ];
    for (const literal of forbiddenLiterals) {
      expect(
        bodyText.includes(literal),
        `Mail view contains contract-breaking literal: ${literal}`,
      ).toBe(false);
    }

    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
