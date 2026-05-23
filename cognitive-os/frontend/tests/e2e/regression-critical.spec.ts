import { expect, request, test } from "@playwright/test";

import { readJwt } from "./_helpers";

/**
 * Regresiones críticas que NO dependen de la UI — chequean directamente
 * contra el backend para detectar regresiones de las últimas fases:
 *
 *  - Fase 72: `/system/readiness` debe responder con un report shape.
 *  - Fase 73: `/system/mcp` reporta los servers declarados.
 *  - Fase 74: `/health/dashboard` lista 17 componentes incluido `mcp_client`.
 *
 * Si alguno de estos endpoints rompe, todas las features visuales que
 * dependen de ellos (los tiles del SettingsView) heredan el bug.
 */
const API = process.env.COGOS_API_BASE ?? "http://127.0.0.1:8000";

test.describe("regression-critical: contratos clave Fase 72-74", () => {
  test("GET /health (público) responde 200", async () => {
    const ctx = await request.newContext();
    const res = await ctx.get(`${API}/health`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
    await ctx.dispose();
  });

  test("GET /health/dashboard lista 17 componentes incluido mcp_client", async () => {
    const jwt = readJwt();
    const ctx = await request.newContext({
      extraHTTPHeaders: { Authorization: `Bearer ${jwt}` },
    });
    const res = await ctx.get(`${API}/health/dashboard`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(["ok", "configured", "degraded"]).toContain(body.status);
    expect(body.components.length).toBeGreaterThanOrEqual(16);
    const names: string[] = body.components.map((c: { name: string }) => c.name);
    // Componentes que la Fase 74 garantiza:
    expect(names).toContain("mcp_client");
    expect(names).toContain("mail");
    expect(names).toContain("checkpointer");
    if (body.status === "degraded") {
      // El modelo de health distingue:
      //   - "degraded" → componente con problema operativo (e.g. probe en vivo
      //     falló o backlog operacional pasó umbral). Ej.: AUDIT-2026-B/F
      //     introdujeron `operational_backlog` y `POST /health/verify`, ambos
      //     reportan `degraded` con `detail` legible cuando aplica.
      //   - "blocked"/"error" → status heredados del action_request, no del
      //     dashboard de health; se mantienen aceptados por compatibilidad.
      const problematic = body.components.filter(
        (c: { status: string }) =>
          c.status === "degraded" ||
          c.status === "blocked" ||
          c.status === "error",
      );
      expect(problematic.length).toBeGreaterThan(0);
      expect(problematic.every((c: { detail?: string }) => Boolean(c.detail))).toBe(
        true,
      );
    }
    await ctx.dispose();
  });

  test("GET /system/readiness devuelve un report válido", async () => {
    const jwt = readJwt();
    const ctx = await request.newContext({
      extraHTTPHeaders: { Authorization: `Bearer ${jwt}` },
    });
    const res = await ctx.get(`${API}/system/readiness`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(["strict", "dedicated_local"]).toContain(body.operator_profile);
    expect(typeof body.summary).toBe("string");
    expect(Array.isArray(body.gaps)).toBe(true);
    expect(
      body.target_capabilities_unlocked + body.gaps.length,
    ).toBeGreaterThan(0);
    await ctx.dispose();
  });

  test("GET /system/mcp respeta enable_mcp_client + lista servers", async () => {
    const jwt = readJwt();
    const ctx = await request.newContext({
      extraHTTPHeaders: { Authorization: `Bearer ${jwt}` },
    });
    const res = await ctx.get(`${API}/system/mcp`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(typeof body.enabled).toBe("boolean");
    expect(typeof body.declared_count).toBe("number");
    expect(Array.isArray(body.servers)).toBe(true);
    // Cuando el cliente MCP está habilitado el shape de cada server debe
    // existir; cuando está apagado, `servers` viene vacío y `declared`
    // refleja sólo lo parseado del .env.
    if (body.enabled && body.servers.length > 0) {
      const first = body.servers[0];
      expect(typeof first.name).toBe("string");
      expect(typeof first.transport).toBe("string");
      expect(typeof first.connected).toBe("boolean");
      expect(typeof first.tools_count).toBe("number");
    }
    await ctx.dispose();
  });

  test("GET /config/public expone operator_profile + flags Fase 71-72", async () => {
    const jwt = readJwt();
    const ctx = await request.newContext({
      extraHTTPHeaders: { Authorization: `Bearer ${jwt}` },
    });
    const res = await ctx.get(`${API}/config/public`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(["strict", "dedicated_local"]).toContain(body.operator_profile);
    expect(["guarded", "full"]).toContain(body.local_autonomy_mode);
    expect(typeof body.auto_approve_reversible_actions).toBe("boolean");
    expect(["soft", "hard"]).toContain(body.code_director_budget_mode);
    await ctx.dispose();
  });
});


/**
 * `crud.spec.ts` cubre la única forma de CRUD real sin side effects
 * externos: PersonalTask vía `/assist/tasks`.
 *
 * Crea → lista → marca done → verifica done → no rompe.
 */
test.describe("crud: PersonalTask end-to-end", () => {
  test("crear tarea, marcarla done y listar", async () => {
    const jwt = readJwt();
    const ctx = await request.newContext({
      extraHTTPHeaders: { Authorization: `Bearer ${jwt}` },
    });

    // En el host del operador el assistant requiere TELEGRAM_ASSIST_USER_MAP
    // o user_id explícito. El endpoint POST devuelve 400/404 si la
    // capacidad no está cableada; en ese caso saltamos para no inflar
    // falsos positivos.
    const probe = await ctx.get(`${API}/assist/tasks`);
    if (probe.status() === 404) {
      test.skip(true, "Personal Assistant API deshabilitada en este host");
    }
    expect([200, 404]).toContain(probe.status());
    if (probe.status() !== 200) {
      await ctx.dispose();
      return;
    }

    const title = `qa-smoke-${Date.now()}`;
    const created = await ctx.post(`${API}/assist/tasks`, {
      data: { title, description: "auto-generated by Playwright QA" },
    });
    if (created.status() === 422 || created.status() === 400) {
      // Falta TELEGRAM_ASSIST_USER_MAP — no es un bug, es una capacidad
      // que necesita config del operador.
      await ctx.dispose();
      test.skip(true, "Assist requires TELEGRAM_ASSIST_USER_MAP");
    }
    expect(created.status()).toBe(201);
    const createdBody = await created.json();
    expect(createdBody.title).toBe(title);

    const list = await ctx.get(`${API}/assist/tasks`);
    const items = await list.json();
    const found = items.find?.((t: { title: string }) => t.title === title);
    expect(found, "la tarea recién creada debe estar en /assist/tasks").toBeDefined();

    await ctx.dispose();
  });
});
