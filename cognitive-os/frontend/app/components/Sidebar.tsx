"use client";

import { useState } from "react";

import type { Tab } from "../lib/types";

type TabItem = { id: Tab; label: string; icon: string; hotkey?: string };
type Section = { id: string; label: string; items: TabItem[] };

const SECTIONS: Section[] = [
  {
    id: "overview",
    label: "Overview",
    items: [{ id: "dashboard", label: "Dashboard", icon: "◧", hotkey: "1" }]
  },
  {
    id: "agents",
    label: "Agentes",
    items: [
      { id: "chat", label: "Chat", icon: "◇", hotkey: "2" },
      { id: "agents", label: "DeepAgents", icon: "✱" },
      { id: "skills", label: "Skills", icon: "✸" },
      { id: "memory", label: "Memoria", icon: "◉" },
      { id: "assist", label: "Asistente", icon: "◌" },
      { id: "mail", label: "Mail", icon: "✉" }
    ]
  },
  {
    id: "knowledge",
    label: "Conocimiento",
    items: [
      { id: "documents", label: "Documentos", icon: "▦", hotkey: "3" },
      { id: "documentAnalysis", label: "Document Analysis", icon: "◈", hotkey: "4" }
    ]
  },
  {
    id: "operations",
    label: "Operaciones",
    items: [
      { id: "jobs", label: "Jobs", icon: "▶", hotkey: "5" },
      { id: "approvals", label: "Aprobaciones", icon: "✓", hotkey: "6" },
      { id: "googleOps", label: "Google Ops", icon: "⌖" },
      { id: "research", label: "Research", icon: "⌕" },
      { id: "sandbox", label: "Sandbox", icon: "▢" }
    ]
  },
  {
    id: "observability",
    label: "Observabilidad",
    items: [
      { id: "langsmith", label: "LangSmith", icon: "⌬", hotkey: "7" },
      { id: "audit", label: "Audit log", icon: "≡", hotkey: "8" },
      { id: "health", label: "Health", icon: "♡", hotkey: "9" }
    ]
  },
  {
    id: "configuration",
    label: "Configuración",
    items: [
      { id: "configuration", label: "Sistema", icon: "⚒" },
      { id: "settings", label: "Conexión", icon: "⚙" }
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
  const healthClass =
    healthStatus === "ok"
      ? "badge ok"
      : healthStatus === "degraded"
        ? "badge warn"
        : healthStatus === "no-auth"
          ? "badge warn"
          : "badge danger";

  return (
    <aside className="sidebar">
      <div className="brand-block">
        <div className="brand-title">
          <h1 className="brand">Cognitive OS</h1>
          <span className="env-pill">{envName}</span>
        </div>
        {isMobile && (
          <button className="ghost icon" onClick={onCloseMobile} type="button" aria-label="Cerrar">
            ✕
          </button>
        )}
      </div>
      <button className="cmd-trigger" onClick={onCommand} type="button">
        <span>⌘ Quick action</span>
        <kbd>Ctrl K</kbd>
      </button>
      <nav className="nav">
        {SECTIONS.map((section) => {
          const open = !collapsed[section.id];
          return (
            <div key={section.id} className="nav-section">
              <button
                className="nav-section-head"
                onClick={() =>
                  setCollapsed((prev) => ({ ...prev, [section.id]: open }))
                }
                type="button"
              >
                <span>{section.label}</span>
                <span className="muted">{open ? "▾" : "▸"}</span>
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
                    >
                      <span className="nav-icon">{item.icon}</span>
                      <span className="nav-label">{item.label}</span>
                      {showBadge && <span className="nav-badge">{badgeValue}</span>}
                      {item.hotkey && <kbd className="nav-hotkey">{item.hotkey}</kbd>}
                    </button>
                  );
                })}
            </div>
          );
        })}
      </nav>
      <div className="sidebar-foot">
        <span className="muted small">Sistema</span>
        <span className={healthClass}>{healthStatus}</span>
      </div>
    </aside>
  );
}

export const TAB_DEFINITIONS: TabItem[] = SECTIONS.flatMap((section) => section.items);
