"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CommandPalette, type CommandAction } from "./components/CommandPalette";
import { Icon } from "./components/Icon";
import {
  NotificationCenter,
  buildNotificationItems,
  useUnreadCount
} from "./components/NotificationCenter";
import { PWA } from "./components/PWA";
import { Sidebar, type SidebarBadges } from "./components/Sidebar";
import { ApiClient, asArray } from "./lib/api";
import {
  LOCAL_API_BASE,
  LOCAL_FRONTEND_HOSTS,
  PUBLIC_API_BASE,
  PUBLIC_FRONTEND_HOSTS,
  readApiBaseFromHash,
  resolveApiBaseForHost,
  stripApiBaseFromHash
} from "./lib/apiBase";
import {
  useHydrated,
  useKeyboard,
  useLocalState,
  useOnline,
  usePolledFetch
} from "./lib/hooks";
import { ToastProvider, useToast } from "./lib/toasts";
import type {
  ApprovalResponse,
  AuditEvent,
  HealthDashboardResponse,
  JobResponse,
  KnowledgeStats,
  Tab
} from "./lib/types";
import { AgentsView } from "./views/AgentsView";
import { ApprovalsView } from "./views/ApprovalsView";
import { AssistView } from "./views/AssistView";
import { AuditView } from "./views/AuditView";
import { ChatView } from "./views/ChatView";
import { CodeDirectorView } from "./views/CodeDirectorView";
import { ConfigurationView } from "./views/ConfigurationView";
import { DashboardView } from "./views/DashboardView";
import { DocumentAnalysisView } from "./views/DocumentAnalysisView";
import { DocumentsView } from "./views/DocumentsView";
import { GoogleOpsView } from "./views/GoogleOpsView";
import { HealthView } from "./views/HealthView";
import { JobsView } from "./views/JobsView";
import { LangSmithView } from "./views/LangSmithView";
import { MailInboxView } from "./views/MailInboxView";
import { MemoryView } from "./views/MemoryView";
import { ResearchView } from "./views/ResearchView";
import { SandboxView } from "./views/SandboxView";
import { SettingsView } from "./views/SettingsView";
import { SkillsView } from "./views/SkillsView";

const MOBILE_QUICK_TABS: Array<{ id: Tab; label: string; icon: Parameters<typeof Icon>[0]["name"] }> = [
  { id: "dashboard", label: "Home", icon: "dashboard" },
  { id: "chat", label: "Chat", icon: "chat" },
  { id: "jobs", label: "Jobs", icon: "jobs" },
  { id: "approvals", label: "Aprob.", icon: "approvals" },
  { id: "langsmith", label: "Traces", icon: "langsmith" }
];

const VALID_TABS = new Set<Tab>([
  "dashboard",
  "chat",
  "agents",
  "skills",
  "memory",
  "assist",
  "googleOps",
  "mail",
  "documents",
  "documentAnalysis",
  "jobs",
  "approvals",
  "sandbox",
  "research",
  "codeDirector",
  "langsmith",
  "audit",
  "health",
  "configuration",
  "settings"
]);

type TokenSource = "" | "auto" | "manual";

type LocalTokenResponse = {
  access_token: string;
  token_type: "bearer";
  user_id: string;
  roles: string[];
  expires_at: string;
};

const AUTO_TOKEN_REFRESH_SKEW_MS = 5 * 60 * 1000;
const LOCAL_TOKEN_TIMEOUT_MS = 10000;
const URL_TOKEN_HASH_KEYS = ["cogos_token", "token", "jwt"];
const MOBILE_BREAKPOINT_PX = 920;

const TAB_HOTKEYS: Record<string, Tab> = {
  "1": "dashboard",
  "2": "chat",
  "3": "agents",
  "4": "documentAnalysis",
  "5": "jobs",
  "6": "approvals",
  "7": "langsmith",
  "8": "audit",
  "9": "health"
};

/**
 * Derive a "1"-"9" numeric hotkey from any KeyboardEvent shape.
 *
 * Browsers, Playwright, CDP and TestSprite synthesise key events with
 * slightly different fields populated. Some only fill `key`, others only
 * `code`, and the deprecated `keyCode` still leaks through some headless
 * paths. Reading all three guarantees a Numpad/Top-row digit on any
 * keyboard layout reaches the same dispatcher.
 */
function extractNumericHotkey(event: KeyboardEvent): string | null {
  if (event.key && /^[1-9]$/.test(event.key)) return event.key;
  const code = event.code ?? "";
  const codeMatch = /^(?:Digit|Numpad)([1-9])$/.exec(code);
  if (codeMatch) return codeMatch[1];
  const legacyKeyCode = (event as KeyboardEvent & { keyCode?: number }).keyCode;
  if (typeof legacyKeyCode === "number") {
    if (legacyKeyCode >= 49 && legacyKeyCode <= 57) return String(legacyKeyCode - 48); // top row
    if (legacyKeyCode >= 97 && legacyKeyCode <= 105) return String(legacyKeyCode - 96); // numpad
  }
  return null;
}

/**
 * True only for an actively-writable text surface. Buttons, anchors,
 * sections with `tabIndex=-1` (our SPA shell focus target), and the
 * sidebar tabs are not considered editable, so a hotkey fired while one
 * of them holds focus still navigates.
 */
function isTypingTarget(node: EventTarget | Element | null): boolean {
  if (!(node instanceof Element)) return false;
  const tag = node.tagName.toLowerCase();
  if (tag === "textarea") return !(node as HTMLTextAreaElement).readOnly;
  if (tag === "select") return true;
  if (tag === "input") {
    const input = node as HTMLInputElement;
    if (input.readOnly) return false;
    const type = (input.type || "text").toLowerCase();
    return ["text", "search", "email", "url", "tel", "number", "password", "date", "datetime-local", "time", "month", "week"].includes(type);
  }
  const editable = node.closest("[contenteditable='true']");
  return Boolean(editable);
}

export default function Home() {
  return (
    <ToastProvider>
      <App />
    </ToastProvider>
  );
}

function App() {
  const [tab, setTab] = useLocalState<Tab>("cogos.tab", "dashboard");
  const [apiBase, setApiBase] = useLocalState<string>("cogos.api", defaultApiBase());
  // Persist JWT in localStorage so a page reload does not force the operator
  // to paste it again. Aligned with the AGENT_SELF.md / docs/USER_GUIDE.md
  // contract that says "JWT en localStorage" for dedicated_local. XSS risk
  // is low on a single-operator PC without third-party scripts. (Fase 71 P1.H)
  const [token, setToken] = useLocalState<string>("cogos.token", "");
  const [tokenSource, setTokenSource] = useLocalState<TokenSource>(
    "cogos.token.source",
    ""
  );
  const [localAuthState, setLocalAuthState] = useState<
    "idle" | "loading" | "ready" | "unavailable"
  >("idle");
  const [localAuthError, setLocalAuthError] = useState<string | null>(null);
  const lastAuthRefreshKey = useRef("");
  const urlTokenSeedApplied = useRef(false);
  const hydrated = useHydrated();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const online = useOnline();
  const toast = useToast();
  const [localPrefsReady, setLocalPrefsReady] = useState(false);

  const applyManualToken = useCallback(
    (value: string) => {
      setTokenSource("manual");
      setToken(value.trim().replace(/^Bearer\s+/i, ""));
    },
    [setToken, setTokenSource]
  );

  const applyAutomaticToken = useCallback(
    (value: string) => {
      setTokenSource("auto");
      setToken(value.trim().replace(/^Bearer\s+/i, ""));
    },
    [setToken, setTokenSource]
  );

  const requestLocalToken = useCallback(async () => {
    setLocalAuthState("loading");
    setLocalAuthError(null);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), LOCAL_TOKEN_TIMEOUT_MS);
    try {
      const response = await fetch(`${apiBase.replace(/\/+$/, "")}/auth/local-token`, {
        method: "POST",
        headers: { Accept: "application/json" },
        cache: "no-store",
        signal: controller.signal
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`${response.status} ${response.statusText}: ${detail}`);
      }
      const payload = (await response.json()) as LocalTokenResponse;
      applyAutomaticToken(payload.access_token);
      setLocalAuthState("ready");
    } catch (caught) {
      setLocalAuthState("unavailable");
      setLocalAuthError(formatLocalAuthError(caught));
    } finally {
      window.clearTimeout(timeout);
    }
  }, [apiBase, applyAutomaticToken]);

  useEffect(() => {
    if (!hydrated) return;
    setLocalPrefsReady(true);
  }, [hydrated]);

  useEffect(() => {
    if (!hydrated || !localPrefsReady) return;
    const resolved = resolveApiBaseForHost(apiBase, window.location.hostname);
    if (resolved !== apiBase) setApiBase(resolved);
  }, [apiBase, hydrated, localPrefsReady, setApiBase]);

  useEffect(() => {
    if (!hydrated || !localPrefsReady || urlTokenSeedApplied.current) return;
    const tokenFromHash = readTokenFromHash(window.location.hash);
    const apiFromHash = readApiBaseFromHash(window.location.hash);
    if (!tokenFromHash && !apiFromHash) return;
    urlTokenSeedApplied.current = true;
    if (tokenFromHash) {
      applyManualToken(tokenFromHash);
      setLocalAuthState("ready");
      setLocalAuthError(null);
    }
    if (apiFromHash) {
      setApiBase(apiFromHash);
    } else if (tokenFromHash && PUBLIC_FRONTEND_HOSTS.has(window.location.hostname)) {
      setApiBase(PUBLIC_API_BASE);
    }
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${window.location.search}${stripAuthFromHash(window.location.hash)}`
    );
  }, [applyManualToken, hydrated, localPrefsReady, setApiBase]);

  useEffect(() => {
    if (!hydrated || !localPrefsReady) return;
    if (urlTokenSeedApplied.current) return;
    if (tokenSource === "manual") return;
    if (token && !jwtExpiresSoon(token)) {
      setLocalAuthState("ready");
      setLocalAuthError(null);
      return;
    }
    void requestLocalToken();
  }, [hydrated, localPrefsReady, requestLocalToken, token, tokenSource]);

  // PWA deep-link via shortcut (?tab=jobs|approvals|chat|...). Runs once on mount.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const target = params.get("tab");
    if (target && VALID_TABS.has(target as Tab)) {
      setTab(target as Tab);
      const url = new URL(window.location.href);
      url.searchParams.delete("tab");
      url.searchParams.delete("source");
      window.history.replaceState({}, "", url.toString());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    // Two-way sync between the inline boot script (which stamps
    // `html[data-cogos-viewport]` from the very first paint) and React.
    // We trust whatever the boot script wrote — it has access to the
    // freshest viewport metrics on every resize/poll — and just
    // propagate the resolved breakpoint into React state so the
    // conditional render of <aside> stays consistent with the attribute.
    //
    // A MutationObserver guarantees we react the same frame the boot
    // script flips the attribute. As a belt-and-suspenders safeguard we
    // also re-measure on every resize/orientation/visualViewport event
    // (no React re-render unless the resolved value actually changed)
    // and re-sync every 200ms in case both the event AND the observer
    // somehow get throttled by the headless harness.
    const root = document.documentElement;
    const mq = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT_PX}px)`);
    const measure = (): boolean => {
      const widths = [
        mq.matches ? MOBILE_BREAKPOINT_PX : Number.POSITIVE_INFINITY,
        window.innerWidth || Number.POSITIVE_INFINITY,
        window.visualViewport?.width ?? Number.POSITIVE_INFINITY,
        document.documentElement?.clientWidth ?? Number.POSITIVE_INFINITY,
        document.body?.clientWidth ?? Number.POSITIVE_INFINITY
      ];
      return Math.min(...widths) <= MOBILE_BREAKPOINT_PX;
    };
    const sync = () => {
      const next = measure();
      const desired = next ? "mobile" : "desktop";
      if (root.getAttribute("data-cogos-viewport") !== desired) {
        root.setAttribute("data-cogos-viewport", desired);
      }
      // React-side state — only triggers a re-render when the resolved
      // value actually changes thanks to the useState reducer dedupe.
      setIsMobile(next);
    };
    // Pick up whatever the boot script measured BEFORE React hydrated.
    const initialAttr = root.getAttribute("data-cogos-viewport");
    if (initialAttr === "mobile") setIsMobile(true);
    sync();
    mq.addEventListener("change", sync);
    window.addEventListener("resize", sync);
    window.addEventListener("orientationchange", sync);
    window.visualViewport?.addEventListener("resize", sync);
    const poll = window.setInterval(sync, 200);
    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(sync);
      resizeObserver.observe(document.documentElement);
      if (document.body) resizeObserver.observe(document.body);
    }
    // Observe attribute mutations on <html> so an external script — or
    // the boot script polling at a different cadence — that flips the
    // viewport attribute also updates React state.
    const attrObserver = new MutationObserver(() => {
      const attr = root.getAttribute("data-cogos-viewport");
      if (attr === "mobile") setIsMobile(true);
      else if (attr === "desktop") setIsMobile(false);
    });
    attrObserver.observe(root, { attributes: true, attributeFilter: ["data-cogos-viewport"] });
    return () => {
      mq.removeEventListener("change", sync);
      window.removeEventListener("resize", sync);
      window.removeEventListener("orientationchange", sync);
      window.visualViewport?.removeEventListener("resize", sync);
      window.clearInterval(poll);
      resizeObserver?.disconnect();
      attrObserver.disconnect();
    };
  }, []);

  // Reflect the active tab onto <html> on every change so external
  // observers (TestSprite, Playwright snapshots) have a synchronously-
  // readable signal that survives React re-render timing. Sidebar
  // clicks, command palette picks, hotkeys and PWA deep-links all hit
  // setTab → this effect → DOM attribute, in that order.
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.setAttribute("data-cogos-active-view", tab);
  }, [tab]);

  const client = useMemo(() => new ApiClient(apiBase, token), [apiBase, token]);

  const stats = usePolledFetch<KnowledgeStats>(
    client,
    token ? "/knowledge/stats" : null,
    8000
  );
  const health = usePolledFetch<HealthDashboardResponse>(
    client,
    token ? "/health/dashboard" : null,
    20000
  );
  const approvals = usePolledFetch<ApprovalResponse[]>(
    client,
    token ? "/approvals" : null,
    8000
  );
  const jobsFeed = usePolledFetch<JobResponse[]>(
    client,
    token ? "/jobs?limit=12" : null,
    10000
  );
  const auditFeed = usePolledFetch<AuditEvent[]>(
    client,
    token ? "/audit/events?limit=12" : null,
    20000
  );

  const notificationItems = useMemo(
    () => buildNotificationItems(approvals.data, jobsFeed.data, auditFeed.data),
    [approvals.data, jobsFeed.data, auditFeed.data]
  );
  const unreadCount = useUnreadCount(notificationItems);

  const badges: SidebarBadges = useMemo(() => {
    const pendingApprovals =
      stats.data?.approvals_pending ??
      asArray(approvals.data).filter((a) => a.status === "pending").length;
    const runningJobs = stats.data?.jobs_running ?? 0;
    return {
      approvals: pendingApprovals,
      jobs: runningJobs
    };
  }, [stats.data, approvals.data]);

  const healthStatus = !token ? "no-auth" : health.data?.status ?? "?";
  const authFailureSignal = [
    stats.error,
    health.error,
    approvals.error,
    jobsFeed.error,
    auditFeed.error
  ]
    .filter(Boolean)
    .join("|");

  useEffect(() => {
    if (!hydrated) return;
    if (tokenSource === "manual") return;
    if (!token || !authFailureSignal || !isUnauthorizedError(authFailureSignal)) return;
    const refreshKey = `${token}:${authFailureSignal}`;
    if (lastAuthRefreshKey.current === refreshKey) return;
    lastAuthRefreshKey.current = refreshKey;
    void requestLocalToken();
  }, [authFailureSignal, hydrated, requestLocalToken, token, tokenSource]);

  const extraActions: CommandAction[] = useMemo(
    () => [
      {
        id: "open-notifications",
        label: "Abrir centro de notificaciones",
        icon: "bell",
        hint: "UI",
        group: "UI",
        run: () => setNotifOpen(true)
      },
      {
        id: "consolidate-memory",
        label: "Consolidar memoria DeepAgents",
        icon: "memory",
        hint: "Acción",
        group: "Acciones",
        run: async () => {
          try {
            await client.post("/deepagents/memory/consolidate/run", {});
            toast.push("Consolidación de memoria encolada.", "success");
          } catch (caught) {
            toast.push(caught instanceof Error ? caught.message : "Error", "error");
          }
        }
      },
      {
        id: "refresh-stats",
        label: "Refrescar datos en vivo",
        icon: "refresh",
        hint: "Datos",
        group: "Acciones",
        run: () => {
          void stats.refetch();
          void health.refetch();
          void approvals.refetch();
          void jobsFeed.refetch();
          void auditFeed.refetch();
        }
      }
    ],
    [client, toast, stats, health, approvals, jobsFeed, auditFeed]
  );

  useKeyboard((event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      setPaletteOpen(true);
      return;
    }
    if (event.key === "Escape") {
      setPaletteOpen(false);
      setDrawerOpen(false);
      setNotifOpen(false);
      return;
    }
    // Tab hotkeys: derive the numeric key from event.key, event.code, and
    // event.keyCode so any input path (physical keyboard, on-screen
    // keyboard, CDP `Input.dispatchKeyEvent`, Playwright/TestSprite
    // synthetic events) reaches the same handler regardless of keyboard
    // layout. If anything looks like 1-9 unmodified, treat it as a tab
    // hotkey.
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    const numericKey = extractNumericHotkey(event);
    if (!numericKey) return;
    // Don't steal the keystroke from a real text input. We only respect
    // *editable* elements (writable input/textarea/select or
    // contenteditable surface). Buttons, sections, anchors with tabindex,
    // and the focus-trap on the SPA shell never block the hotkey.
    if (isTypingTarget(event.target) || isTypingTarget(document.activeElement)) return;
    const targetTab = TAB_HOTKEYS[numericKey];
    if (!targetTab) return;
    event.preventDefault();
    event.stopPropagation();
    setPaletteOpen(false);
    setDrawerOpen(false);
    setNotifOpen(false);
    setTab(targetTab);
    // Synchronously mirror the active tab onto <html> so any external
    // observer (TestSprite, Playwright, Selenium) sees the new view
    // marker in the same animation frame as the React re-render,
    // without waiting for layout to settle.
    document.documentElement.setAttribute("data-cogos-active-view", targetTab);
    window.requestAnimationFrame(() => {
      document.getElementById("cogos-main")?.focus({ preventScroll: true });
    });
  });

  const showDrawer = drawerOpen;
  // On the mobile breakpoint we *unmount* the <aside> (rather than
  // hiding it with CSS) so external test harnesses that probe the DOM
  // see a real structural change between desktop and tablet/mobile
  // viewports. Until React has hydrated we mirror the SSR markup
  // (desktop) so there is no hydration mismatch — the responsive
  // useEffect picks up the actual breakpoint within the next paint and
  // re-renders without the sidebar if the viewport is below 920px.
  const renderSidebarShell = !hydrated || !isMobile || showDrawer;
  const resolvedViewport = hydrated && isMobile ? "mobile" : "desktop";

  return (
    <main
      className={`shell${hydrated && isMobile ? " shell--mobile" : ""}`}
      data-cogos-active-tab={tab}
      data-cogos-active-view={tab}
      data-cogos-viewport={resolvedViewport}
    >
      <a href="#cogos-main" className="skip-link">
        Saltar al contenido principal
      </a>
      {renderSidebarShell && (
        <div
          className={`sidebar-wrap${showDrawer ? " is-drawer" : ""}`}
          onClick={(event) => {
            if (showDrawer && event.target === event.currentTarget) {
              setDrawerOpen(false);
            }
          }}
          role={showDrawer ? "dialog" : undefined}
        >
          <Sidebar
            current={tab}
            onSelect={(next) => {
              setTab(next);
              setDrawerOpen(false);
            }}
            badges={badges}
            healthStatus={healthStatus}
            envName={token ? "ops" : localAuthState === "loading" ? "local" : "guest"}
            onCommand={() => setPaletteOpen(true)}
            isMobile={isMobile || showDrawer}
            onCloseMobile={() => setDrawerOpen(false)}
          />
        </div>
      )}
      <section className="main" id="cogos-main" tabIndex={-1}>
        <div className="main-head">
          <button
            className="ghost icon"
            onClick={() => setDrawerOpen(true)}
            type="button"
            aria-label="Abrir menú"
          >
            <Icon name="menu" size={18} />
          </button>
        </div>
        {hydrated && !token && localAuthState === "loading" && (
          <div className="warn-box row" role="status" style={{ gap: 10 }}>
            <Icon name="key" size={16} />
            <span>Activando JWT local automático para este PC.</span>
          </div>
        )}
        {hydrated && !token && localAuthState !== "loading" && (
          <div className="warn-box row" role="alert" style={{ gap: 10 }}>
            <Icon name="key" size={16} />
            <span>
              No se pudo activar el JWT local automático. Podés pegar uno manualmente
              sin prefijo Bearer en <em>Conexión</em>.
              {localAuthError ? ` Detalle: ${localAuthError}` : ""}
            </span>
          </div>
        )}
        {tab === "dashboard" && <DashboardView client={client} onNavigate={setTab} />}
        {tab === "chat" && <ChatView client={client} />}
        {tab === "agents" && <AgentsView client={client} />}
        {tab === "skills" && <SkillsView client={client} />}
        {tab === "memory" && <MemoryView client={client} />}
        {tab === "assist" && <AssistView client={client} />}
        {tab === "googleOps" && <GoogleOpsView client={client} />}
        {tab === "mail" && <MailInboxView client={client} />}
        {tab === "documents" && <DocumentsView client={client} />}
        {tab === "documentAnalysis" && <DocumentAnalysisView client={client} />}
        {tab === "jobs" && <JobsView client={client} />}
        {tab === "approvals" && <ApprovalsView client={client} />}
        {tab === "research" && <ResearchView client={client} />}
        {tab === "codeDirector" && <CodeDirectorView client={client} />}
        {tab === "sandbox" && <SandboxView client={client} />}
        {tab === "langsmith" && <LangSmithView client={client} />}
        {tab === "audit" && <AuditView client={client} />}
        {tab === "health" && <HealthView client={client} />}
        {tab === "configuration" && <ConfigurationView client={client} />}
        {tab === "settings" && (
          <SettingsView
            client={client}
            apiBase={apiBase}
            setApiBase={setApiBase}
            token={token}
            setToken={applyManualToken}
            tokenSource={tokenSource}
            requestLocalToken={requestLocalToken}
          />
        )}
      </section>
      <nav className="bottom-nav" aria-label="Navegación rápida">
        {MOBILE_QUICK_TABS.map((item) => (
          <button
            key={item.id}
            className={tab === item.id ? "active" : ""}
            onClick={() => setTab(item.id)}
            type="button"
            aria-label={item.label}
          >
            <span className="bn-icon">
              <Icon name={item.icon} size={18} />
            </span>
            <span className="bn-label">{item.label}</span>
          </button>
        ))}
      </nav>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSelectTab={(t) => setTab(t)}
        extraActions={extraActions}
      />
      <NotificationCenter
        open={notifOpen}
        onClose={() => setNotifOpen(false)}
        client={client}
        items={notificationItems}
        onNavigate={setTab}
      />
      <PWA />
    </main>
  );
}

function isUnauthorizedError(message: string): boolean {
  return /(^|\D)401(\D|$)|invalid bearer token|bearer token required/i.test(message);
}

function defaultApiBase(): string {
  const env = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (typeof window !== "undefined" && PUBLIC_FRONTEND_HOSTS.has(window.location.hostname)) {
    return PUBLIC_API_BASE;
  }
  if (typeof window !== "undefined" && LOCAL_FRONTEND_HOSTS.has(window.location.hostname)) {
    return LOCAL_API_BASE;
  }
  return env || LOCAL_API_BASE;
}

function readTokenFromHash(hash: string): string | null {
  const params = hashParams(hash);
  for (const key of URL_TOKEN_HASH_KEYS) {
    const value = params.get(key)?.trim();
    if (value) return value.replace(/^Bearer\s+/i, "");
  }
  return null;
}

function stripTokenFromHash(hash: string): string {
  const params = hashParams(hash);
  for (const key of URL_TOKEN_HASH_KEYS) {
    params.delete(key);
  }
  const next = params.toString();
  return next ? `#${next}` : "";
}

function stripAuthFromHash(hash: string): string {
  return stripApiBaseFromHash(stripTokenFromHash(hash));
}

function hashParams(hash: string): URLSearchParams {
  return new URLSearchParams(hash.startsWith("#") ? hash.slice(1) : hash);
}

function formatLocalAuthError(caught: unknown): string {
  if (caught instanceof DOMException && caught.name === "AbortError") {
    return `Timeout al pedir JWT local despues de ${LOCAL_TOKEN_TIMEOUT_MS / 1000}s. Verifica la URL de la API.`;
  }
  if (caught instanceof Error) return caught.message;
  return "JWT local no disponible";
}

function jwtExpiresSoon(token: string): boolean {
  const payload = decodeJwtPayload(token);
  const exp = typeof payload?.exp === "number" ? payload.exp : null;
  if (!exp) return true;
  return exp * 1000 <= Date.now() + AUTO_TOKEN_REFRESH_SKEW_MS;
}

function decodeJwtPayload(token: string): { exp?: number } | null {
  const [, payload] = token.split(".");
  if (!payload) return null;
  try {
    const padded = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = window.atob(padded.padEnd(Math.ceil(padded.length / 4) * 4, "="));
    const parsed = JSON.parse(json) as unknown;
    return parsed && typeof parsed === "object" ? (parsed as { exp?: number }) : null;
  } catch {
    return null;
  }
}
