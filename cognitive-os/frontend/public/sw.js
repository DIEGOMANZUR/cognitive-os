/* Cognitive OS service worker.
   Strategy:
   - Static shell + Next chunks: stale-while-revalidate (instant UI, fresh in background).
   - Same-origin navigations: network-first with cached shell fallback, and a
     final HTML fallback so the operator gets a branded offline page if the
     shell isn't cached yet.
   - Backend API: network-only (no caching of mutating endpoints or live state).
   - Push notifications: standard push/notificationclick handler so the
     backend can wake the user when there is a new approval, a failed job,
     or any subscribed event.
*/

const CACHE_VERSION = "cogos-v2026-05-20-glass-2";
const SHELL_ASSETS = [
  "/",
  "/manifest.webmanifest",
  "/offline.html",
  "/icons/icon.svg",
  "/icons/icon-192.svg",
  "/icons/icon-512.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-maskable.svg",
  "/icons/icon-maskable-512.png",
  "/icons/apple-touch-icon.svg",
  "/icons/apple-touch-icon.png"
];

const ASSET_PATTERN =
  /^\/(?:_next\/|icons\/|manifest\.webmanifest|favicon\.ico|offline\.html)/;

const NETWORK_ONLY_PREFIXES = [
  "/actions",
  "/api",
  "/approvals",
  "/assist",
  "/audit",
  "/chat",
  "/code-director",
  "/config",
  "/deepagents",
  "/documents",
  "/health",
  "/jobs",
  "/knowledge",
  "/langsmith",
  "/mail",
  "/memory",
  "/research",
  "/sessions",
  "/skills",
  "/system",
  "/threads"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_VERSION);
      try {
        await cache.addAll(SHELL_ASSETS);
      } catch (e) {
        // Some shell assets may 404 in dev (e.g. /manifest.webmanifest before
        // first build). Ignore so install still succeeds.
      }
    })()
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
      );
      await self.clients.claim();
      const clients = await self.clients.matchAll({ type: "window" });
      clients.forEach((client) => {
        client.postMessage({
          type: "COGOS_SW_ACTIVATED",
          version: CACHE_VERSION
        });
      });
    })()
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "COGOS_SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  // Cross-origin requests (API calls under a different host) — never cache.
  if (url.origin !== self.location.origin) return;

  if (NETWORK_ONLY_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    event.respondWith(fetch(request));
    return;
  }

  if (ASSET_PATTERN.test(url.pathname)) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  // Navigation request → network-first, fallback to cached shell / offline.
  if (request.mode === "navigate") {
    event.respondWith(networkFirstShell(request));
  }
});

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_VERSION);
  const cached = await cache.match(request);
  const networkPromise = fetch(request)
    .then((response) => {
      if (response && response.ok && response.status === 200) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => cached);
  return cached || networkPromise;
}

async function networkFirstShell(request) {
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(CACHE_VERSION);
      cache.put("/", response.clone());
    }
    return response;
  } catch (e) {
    const cache = await caches.open(CACHE_VERSION);
    const shell = await cache.match("/");
    if (shell) return shell;
    const offline = await cache.match("/offline.html");
    if (offline) return offline;
    return new Response(
      "<h1>Offline</h1><p>Cognitive OS necesita conexión la primera vez. Reintentá cuando vuelvas online.</p>",
      { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } }
    );
  }
}

/* ----- Push notifications (best-effort) ------------------------------------
 * Backend must POST a Web Push payload like:
 *   { title: "Aprobación pendiente", body: "approve doc.x", tag: "approval:<id>",
 *     url: "/?tab=approvals" }
 * If push is not configured the SW silently no-ops.
 */
self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { title: "Cognitive OS", body: event.data?.text() ?? "" };
  }
  const title = payload.title || "Cognitive OS";
  const options = {
    body: payload.body || "",
    icon: "/icons/icon-192.svg",
    badge: "/icons/icon-192.svg",
    tag: payload.tag,
    data: { url: payload.url || "/" },
    requireInteraction: Boolean(payload.requireInteraction)
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/";
  event.waitUntil(
    (async () => {
      const all = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of all) {
        if (client.url.endsWith(targetUrl) && "focus" in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })()
  );
});
