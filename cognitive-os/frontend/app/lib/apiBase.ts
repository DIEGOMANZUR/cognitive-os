export const LOCAL_API_BASE = "http://127.0.0.1:8000";
export const PUBLIC_API_BASE = "https://cognitive-api.doctormanzur.com";
export const PUBLIC_FRONTEND_HOSTS = new Set(["cognitive.doctormanzur.com"]);
export const LOCAL_FRONTEND_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

export function normalizeApiBaseUrl(raw: string): string | null {
  const trimmed = raw.trim().replace(/\/+$/, "");
  if (!trimmed) return null;
  try {
    const candidate = trimmed.includes("://") ? trimmed : `https://${trimmed}`;
    const url = new URL(candidate);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    return url.origin.replace(/\/+$/, "");
  } catch {
    return null;
  }
}

export function isMisconfiguredApiBase(apiBase: string, hostname: string): boolean {
  const normalized = normalizeApiBaseUrl(apiBase);
  if (!normalized) return true;
  if (!PUBLIC_FRONTEND_HOSTS.has(hostname)) return false;
  try {
    const host = new URL(normalized).hostname;
    return PUBLIC_FRONTEND_HOSTS.has(host) || LOCAL_FRONTEND_HOSTS.has(host);
  } catch {
    return true;
  }
}

export function resolveApiBaseForHost(stored: string, hostname: string): string {
  const env = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (PUBLIC_FRONTEND_HOSTS.has(hostname)) {
    const normalized = normalizeApiBaseUrl(stored);
    if (normalized && !isMisconfiguredApiBase(normalized, hostname)) return normalized;
    const envBase = env ? normalizeApiBaseUrl(env) : null;
    if (envBase && !isMisconfiguredApiBase(envBase, hostname)) return envBase;
    return PUBLIC_API_BASE;
  }
  if (LOCAL_FRONTEND_HOSTS.has(hostname)) {
    return normalizeApiBaseUrl(stored) || (env ? normalizeApiBaseUrl(env) : null) || LOCAL_API_BASE;
  }
  return normalizeApiBaseUrl(stored) || (env ? normalizeApiBaseUrl(env) : null) || LOCAL_API_BASE;
}

export function readApiBaseFromHash(hash: string): string | null {
  const params = new URLSearchParams(hash.startsWith("#") ? hash.slice(1) : hash);
  for (const key of ["cogos_api", "api"]) {
    const value = params.get(key)?.trim();
    if (!value) continue;
    const normalized = normalizeApiBaseUrl(value);
    if (normalized) return normalized;
  }
  return null;
}

export function stripApiBaseFromHash(hash: string): string {
  const params = new URLSearchParams(hash.startsWith("#") ? hash.slice(1) : hash);
  params.delete("cogos_api");
  params.delete("api");
  const next = params.toString();
  return next ? `#${next}` : "";
}
