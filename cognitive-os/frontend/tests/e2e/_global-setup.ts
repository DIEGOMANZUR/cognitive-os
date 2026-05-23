import type { FullConfig } from "@playwright/test";

/**
 * Auto-mint COGOS_JWT in dedicated_local/full so the suite is zero-friction.
 *
 * Historical contract (`_helpers.ts` comment) said the runner must mint the
 * token out-of-band because the mint endpoint was admin-only. That is no
 * longer true: `POST /auth/local-token` is open in `dedicated_local/full`
 * (it 403s in strict). For the dedicated PC profile this means a fresh
 * `npx playwright test` against a live backend should succeed without any
 * setup step — consistent with `ZERO_FRICTION_OPERATING_MODEL.md`.
 *
 * Behaviour:
 *   - If `COGOS_JWT` is already set (CI, custom env, strict mode) → leave alone.
 *   - Else, attempt `POST ${COGOS_API_BASE:-http://127.0.0.1:8000}/auth/local-token`.
 *     • 200 → export `process.env.COGOS_JWT`. Workers inherit env from parent.
 *     • 403 → strict/guarded profile. Leave unset; `readJwt()` will surface
 *       a clear error pointing to RUNBOOK §2.
 *     • Network error → leave unset; `readJwt()` will surface the original
 *       missing-env error.
 *
 * Skipping any failure on purpose: we do NOT want to turn a backend that is
 * temporarily down into a setup crash — the individual tests will fail with
 * actionable context instead.
 */
export default async function globalSetup(_config: FullConfig): Promise<void> {
  if (process.env.COGOS_JWT?.trim()) {
    return;
  }
  const apiBase = process.env.COGOS_API_BASE?.trim() || "http://127.0.0.1:8000";
  try {
    const res = await fetch(`${apiBase}/auth/local-token`, {
      method: "POST",
      headers: { "Cache-Control": "no-store" },
    });
    if (!res.ok) {
      // 403 in strict/guarded profile is expected; leave COGOS_JWT unset
      // and let readJwt() emit the explicit "set COGOS_JWT manually" error.
      return;
    }
    const payload = (await res.json()) as { access_token?: string };
    const token = payload.access_token?.trim();
    if (token) {
      process.env.COGOS_JWT = token;
      console.log(
        `[playwright global-setup] auto-minted COGOS_JWT via ${apiBase}/auth/local-token (dedicated_local/full)`,
      );
    }
  } catch {
    // Backend not reachable or fetch unsupported — fall through silently.
    // readJwt() will throw with a clear message and the test will report
    // the underlying connectivity issue.
  }
}
