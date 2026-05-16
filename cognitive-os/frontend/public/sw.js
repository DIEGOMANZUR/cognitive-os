/* Cognitive OS service worker.
   Cache-first for static assets, network-only for API calls (we always want
   fresh state). On offline failures the SW falls back to a cached copy of /
   so the dashboard shell still loads.
*/
const CACHE_VERSION = "cogos-v2026-05-15-32";
const SHELL_ASSETS = [
  "/",
  "/manifest.webmanifest",
  "/icons/icon-192.svg",
  "/icons/icon-512.svg",
  "/icons/apple-touch-icon.svg"
];
const ASSET_PATTERN = /^\/(?:_next\/|icons\/|manifest\.webmanifest|favicon\.ico)/;
const NETWORK_ONLY_PREFIXES = [
  "/actions",
  "/api",
  "/approvals",
  "/chat",
  "/config",
  "/deepagents",
  "/documents",
  "/health",
  "/jobs",
  "/knowledge",
  "/mail",
  "/memory",
  "/research",
  "/threads"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_VERSION);
      try {
        await cache.addAll(SHELL_ASSETS);
      } catch (e) {
        // Some shell assets may 404 in dev; ignore so install still succeeds.
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
        client.postMessage({ type: "COGOS_SW_ACTIVATED", version: CACHE_VERSION });
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

  // Same-origin requests only (the API runs on a different origin and we never
  // want to cache its responses anyway — always fetch fresh).
  if (url.origin !== self.location.origin) return;

  if (NETWORK_ONLY_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    event.respondWith(fetch(request));
    return;
  }

  if (ASSET_PATTERN.test(url.pathname)) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  // Navigation request → network-first, fallback to cached shell.
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
    const fallback = await cache.match("/");
    if (fallback) return fallback;
    return new Response(
      "<h1>Offline</h1><p>Cognitive OS necesita conexión la primera vez. Reintentá cuando vuelvas online.</p>",
      { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } }
    );
  }
}
