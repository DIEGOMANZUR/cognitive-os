import { expect, test } from "@playwright/test";

import {
  filterUnexpectedErrors,
  readJwt,
  seedAuth,
  tabButton,
  watchPageHealth,
} from "./_helpers";

test.describe("mail: digest y sync manual", () => {
  test("el botón de sync encola el worker mail y no llama el sync directo", async ({
    page,
  }) => {
    const jwt = readJwt();
    let dispatchCalls = 0;
    let directSyncCalls = 0;

    await page.route("**/mail/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: true,
          default_sender: "diego@example.test",
          require_approval_for_send: true,
          allow_explicit_send: false,
          background_sync_enabled: false,
          digest_enabled: true,
          digest_hours_local: ["10", "20"],
          digest_timezone: "America/Santiago",
          digest_max_messages: 50,
          gmail_monitor_labels: ["TODOS", "SPAM"],
          accounts: [],
          reasons: [],
        }),
      });
    });
    await page.route("**/mail/messages**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
    });
    await page.route("**/mail/sync/dispatch", async (route) => {
      dispatchCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ task_id: "mail-task-123", status: "dispatched" }),
      });
    });
    await page.route("**/mail/sync", async (route) => {
      directSyncCalls += 1;
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "direct mail sync must not be called from UI" }),
      });
    });

    await seedAuth(page, jwt);
    const health = watchPageHealth(page);

    await page.goto("/");
    await tabButton(page, "Mail").click();
    await expect(page.getByRole("heading", { name: "Digest de correo" })).toBeVisible();
    await page.getByRole("button", { name: "Sync por worker" }).click();

    await expect(page.getByText(/Sync encolado en mail/)).toBeVisible();
    expect(dispatchCalls).toBe(1);
    expect(directSyncCalls).toBe(0);
    expect(health.serverErrors).toEqual([]);
    expect(filterUnexpectedErrors(health.errors)).toEqual([]);
    health.dispose();
  });
});
