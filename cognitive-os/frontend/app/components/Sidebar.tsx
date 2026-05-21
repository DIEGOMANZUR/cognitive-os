"use client";

import { useState } from "react";

import type { Tab } from "../lib/types";
import { Icon, type IconName } from "./Icon";

type TabItem = { id: Tab; label: string; icon: IconName; hotkey?: string };
type Section = { id: string; label: string; items: TabItem[] };

const SECTIONS: Section[] = [
  {
    id: "overview",
    label: "Overview",
    items: [{ id: "dashboard", label: "Dashboard", icon: "dashboard", hotkey: "1" }]
  },
  {
    id: "agents",
    label: "Agentes",
    items: [
      { id: "chat", label: "Chat", icon: "chat", hotkey: "2" },
      { id: "agents", label: "DeepAgents", icon: "agents" },
      { id: "skills", label: "Skills", icon: "skills" },
      { id: "memory", label: "Memoria", icon: "memory" },
      { id: "assist", label: "Asistente", icon: "assist" },
      { id: "mail", label: "Mail", icon: "mail" }
    ]
  },
  {
    id: "knowledge",
    label: "Conocimiento",
    items: [
      { id: "documents", label: "Documentos", icon: "documents", hotkey: "3" },
      { id: "documentAnalysis", label: "Document Analysis", icon: "documentAnalysis", hotkey: "4" }
    ]
  },
  {
    id: "operations",
    label: "Operaciones",
    items: [
      { id: "jobs", label: "Jobs", icon: "jobs", hotkey: "5" },
      { id: "approvals", label: "Aprobaciones", icon: "approvals", hotkey: "6" },
      { id: "googleOps", label: "Google Ops", icon: "googleOps" },
      { id: "research", label: "Research", icon: "research" },
      { id: "codeDirector", label: "Code Director", icon: "codeDirector" },
      { id: "sandbox", label: "Sandbox", icon: "sandbox" }
    ]
  },
  {
    id: "observability",
    label: "Observabilidad",
    items: [
      { id: "langsmith", label: "LangSmith", icon: "langsmith", hotkey: "7" },
      { id: "audit", label: "Audit log", icon: "audit", hotkey: "8" },
      { id: "health", label: "Health", icon: "health", hotkey: "9" }
    ]
  },
  {
    id: "configuration",
    label: "Configuración",
    items: [
      { id: "configuration", label: "Sistema", icon: "configuration" },
      { id: "settings", label: "Conexión", icon: "settings" }
    ]
  }
];

export type SidebarBadges = Partial<Record<Tab, number>>;

export function Sidebar({
  current,
  onSelect,
  badges,
  healthStatus,
  envName,
  onCommand,
  isMobile,
  onCloseMobile
}: {
  current: Tab;
  onSelect: (tab: Tab) => void;
  badges: SidebarBadges;
  healthStatus: string;
  envName: string;
  onCommand: () => void;
  isMobile?: boolean;
  onCloseMobile?: () => void;
}) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const healthDotClass =
    healthStatus === "ok"
      ? "dot ok live"
      : healthStatus === "degraded"
        ? "dot warn live"
        : healthStatus === "no-auth"
          ? "dot warn"
          : "dot danger live";

  const healthBadgeClass =
    healthStatus === "ok"
      ? "badge ok"
      : healthStatus === "degraded" || healthStatus === "no-auth"
        ? "badge warn"
        : "badge danger";

  return (
    <aside className="sidebar">
      <div className="brand-block">
        <div className="brand-title">
          <span className="brand-mark" aria-hidden="true">
            <Icon name="brand" size={18} strokeWidth={2} />
          </span>
          <div className="stack" style={{ gap: 0 }}>
            <h1 className="brand">Cognitive OS</h1>
            <span className="brand-sub">command center</span>
          </div>
        </div>
        {isMobile && (
          <button
            className="ghost icon"
            onClick={onCloseMobile}
            type="button"
            aria-label="Cerrar"
          >
            <Icon name="close" size={18} />
          </button>
        )}
      </div>

      <button className="cmd-trigger" onClick={onCommand} type="button">
        <span className="row" style={{ gap: 8 }}>
          <Icon name="search" size={14} />
          <span>Quick action…</span>
        </span>
        <kbd>Ctrl K</kbd>
      </button>

      <span className="env-pill" style={{ alignSelf: "flex-start" }}>
        ENV · {envName}
      </span>

      <nav className="nav" aria-label="Navegación principal">
        {SECTIONS.map((section) => {
          const open = !collapsed[section.id];
          return (
            <div key={section.id} className="nav-section">
              <button
                className="nav-section-head"
                onClick={() => setCollapsed((prev) => ({ ...prev, [section.id]: open }))}
                type="button"
                aria-expanded={open}
              >
                <span>{section.label}</span>
                <Icon name={open ? "chevronDown" : "chevronRight"} size={12} />
              </button>
              {open &&
                section.items.map((item) => {
                  const badgeValue = badges[item.id];
                  const showBadge = typeof badgeValue === "number" && badgeValue > 0;
                  return (
                    <button
                      key={item.id}
                      className={`nav-item${current === item.id ? " active" : ""}`}
                      onClick={() => {
                        onSelect(item.id);
                        if (isMobile && onCloseMobile) onCloseMobile();
                      }}
                      type="button"
                      aria-current={current === item.id ? "page" : undefined}
                    >
                      <span className="nav-icon">
                        <Icon name={item.icon} size={16} />
                      </span>
                      <span className="nav-label">{item.label}</span>
                      {showBadge && (
                        <span className="nav-badge" aria-label={`${badgeValue} pendientes`}>
                          {badgeValue}
                        </span>
                      )}
                      {item.hotkey && <kbd className="nav-hotkey">{item.hotkey}</kbd>}
                    </button>
                  );
                })}
            </div>
          );
        })}
      </nav>

      <div className="sidebar-foot">
        <span className="row" style={{ gap: 7 }}>
          <span className={healthDotClass} aria-hidden="true" />
          <span className="muted small">Sistema</span>
        </span>
        <span className={healthBadgeClass}>{healthStatus}</span>
      </div>
    </aside>
  );
}

export const TAB_DEFINITIONS: TabItem[] = SECTIONS.flatMap((section) => section.items);
