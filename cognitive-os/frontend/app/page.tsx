"use client";

import { useEffect, useMemo, useState } from "react";

import { CommandPalette, type CommandAction } from "./components/CommandPalette";
import { PWA } from "./components/PWA";
import { Sidebar, type SidebarBadges } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { ApiClient } from "./lib/api";
import { useKeyboard, useLocalState, usePolledFetch } from "./lib/hooks";
import { ToastProvider, useToast } from "./lib/toasts";
import type {
  ApprovalResponse,
  HealthDashboardResponse,
  KnowledgeStats,
  Tab,
  Theme
} from "./lib/types";
import { AgentsView } from "./views/AgentsView";
import { ApprovalsView } from "./views/ApprovalsView";
import { AssistView } from "./views/AssistView";
import { AuditView } from "./views/AuditView";
import { ChatView } from "./views/ChatView";
import { ConfigurationView } from "./views/ConfigurationView";
import { DashboardView } from "./views/DashboardView";
import { DocumentAnalysisView } from "./views/DocumentAnalysisView";
import { DocumentsView } from "./views/DocumentsView";
import { HealthView } from "./views/HealthView";
import { GoogleOpsView } from "./views/GoogleOpsView";
import { JobsView } from "./views/JobsView";
import { LangSmithView } from "./views/LangSmithView";
import { MailInboxView } from "./views/MailInboxView";
import { CodeDirectorView } from "./views/CodeDirectorView";
import { MemoryView } from "./views/MemoryView";
import { ResearchView } from "./views/ResearchView";
import { SandboxView } from "./views/SandboxView";
import { SettingsView } from "./views/SettingsView";
import { SkillsView } from "./views/SkillsView";

const MOBILE_QUICK_TABS: Array<{ id: Tab; label: string; icon: string }> = [
  { id: "dashboard", label: "Home", icon: "◧" },
  { id: "chat", label: "Chat", icon: "◇" },
  { id: "jobs", label: "Jobs", icon: "▶" },
  { id: "approvals", label: "Aprob.", icon: "✓" },
  { id: "langsmith", label: "Traces", icon: "⌬" }
];

export default function Home() {
  return (
    <ToastProvider>
      <App />
    </ToastProvider>
  );
}

function App() {
  const [tab, setTab] = useLocalState<Tab>("cogos.tab", "dashboard");
  const [apiBase, setApiBase] = useLocalState<string>("cogos.api", "http://127.0.0.1:8000");
  // Persist JWT in localStorage so a page reload does not force the operator
  // to paste it again. Aligned with the AGENT_SELF.md / docs/USER_GUIDE.md
  // contract that says "JWT en localStorage" for dedicated_local. XSS risk
  // is low on a single-operator PC without third-party scripts. (Fase 71 P1.H)
  const [token, setToken] = useLocalState<string>("cogos.token", "");
  const [theme, setTheme] = useLocalState<Theme>("cogos.theme", "dark");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const toast = useToast();

  useEffect(() => {
    const env = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
    if (env) setApiBase(env);
  }, [setApiBase]);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.dataset.theme = theme;
    }
  }, [theme]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(max-width: 920px)");
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

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

  const badges: SidebarBadges = useMemo(() => {
    const pendingApprovals =
      stats.data?.approvals_pending ??
      (approvals.data ?? []).filter((a) => a.status === "pending").length;
    const runningJobs = stats.data?.jobs_running ?? 0;
    return {
      approvals: pendingApprovals,
      jobs: runningJobs
    };
  }, [stats.data, approvals.data]);

  const healthStatus = !token ? "no-auth" : health.data?.status ?? "?";

  const extraActions: CommandAction[] = useMemo(
    () => [
      {
        id: "theme-toggle",
        label: theme === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro",
        hint: "UI",
        run: () => setTheme(theme === "dark" ? "light" : "dark")
      },
      {
        id: "consolidate-memory",
        label: "Consolidar memoria DeepAgents",
        hint: "Acción",
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
        hint: "Datos",
        run: () => {
          void stats.refetch();
          void health.refetch();
          void approvals.refetch();
        }
      }
    ],
    [theme, setTheme, client, toast, stats, health, approvals]
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
      return;
    }
    const target = event.target as HTMLElement | null;
    if (target && ["INPUT", "TEXTAREA"].includes(target.tagName)) return;
    const tabHotkeys: Record<string, Tab> = {
      "1": "dashboard",
      "2": "chat",
      "3": "documents",
      "4": "documentAnalysis",
      "5": "jobs",
      "6": "approvals",
      "7": "langsmith",
      "8": "audit",
      "9": "health"
    };
    const targetTab = tabHotkeys[event.key];
    if (targetTab) setTab(targetTab);
  });

  const showDrawer = isMobile && drawerOpen;
  const showSidebar = !isMobile || drawerOpen;

  return (
    <main className="shell">
      {showSidebar && (
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
            onSelect={setTab}
            badges={badges}
            healthStatus={healthStatus}
            envName={token ? "ops" : "guest"}
            onCommand={() => setPaletteOpen(true)}
            isMobile={isMobile}
            onCloseMobile={() => setDrawerOpen(false)}
          />
        </div>
      )}
      <section className="main">
        <div className="main-head">
          {isMobile && (
            <button
              className="ghost icon"
              onClick={() => setDrawerOpen(true)}
              type="button"
              aria-label="Abrir menú"
            >
              ☰
            </button>
          )}
          <TopBar
            apiBase={apiBase}
            setApiBase={setApiBase}
            token={token}
            setToken={setToken}
            theme={theme}
            toggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
          />
        </div>
        {!token && (
          <div className="warn-box">
            Falta JWT local. Pegalo sin prefijo Bearer en el TopBar (o en la pestaña <em>Conexión</em>) para
            activar las consultas autenticadas.
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
            setToken={setToken}
            theme={theme}
            setTheme={setTheme}
          />
        )}
      </section>
      {isMobile && (
        <nav className="bottom-nav">
          {MOBILE_QUICK_TABS.map((item) => (
            <button
              key={item.id}
              className={tab === item.id ? "active" : ""}
              onClick={() => setTab(item.id)}
              type="button"
            >
              <span className="bn-icon">{item.icon}</span>
              <span className="bn-label">{item.label}</span>
            </button>
          ))}
        </nav>
      )}
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSelectTab={(t) => {
          setTab(t);
          setPaletteOpen(false);
        }}
        extraActions={extraActions}
      />
      <PWA />
    </main>
  );
}
