"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { useFocusTrap } from "../lib/a11y";
import type { Tab } from "../lib/types";
import { Icon, type IconName } from "./Icon";
import { TAB_DEFINITIONS } from "./Sidebar";

export type CommandAction = {
  id: string;
  label: string;
  shortcut?: string;
  hint?: string;
  icon?: IconName;
  group?: string;
  run: () => void;
};

const RECENT_KEY = "cogos.palette.recent";

function loadRecent(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function persistRecent(ids: string[]) {
  try {
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(ids.slice(0, 8)));
  } catch {
    // ignore
  }
}

/**
 * Tiny subsequence fuzzy match. Each query char must appear in order; consecutive
 * matches score higher, word-boundary matches even more. We don't need
 * Levenshtein for a 30-entry palette.
 */
function fuzzyScore(query: string, label: string): number {
  if (!query) return 0;
  const haystack = label.toLowerCase();
  let lastIndex = -1;
  let score = 0;
  let streak = 0;
  for (const char of query.toLowerCase()) {
    const idx = haystack.indexOf(char, lastIndex + 1);
    if (idx === -1) return -1;
    if (idx === lastIndex + 1) streak += 1;
    else streak = 0;
    score += 1 + streak * 2;
    if (idx === 0 || haystack[idx - 1] === " ") score += 3;
    lastIndex = idx;
  }
  return score - lastIndex * 0.01;
}

export function CommandPalette({
  open,
  onClose,
  onSelectTab,
  extraActions
}: {
  open: boolean;
  onClose: () => void;
  onSelectTab: (tab: Tab) => void;
  extraActions: CommandAction[];
}) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [recent, setRecent] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useFocusTrap(dialogRef, open);

  useEffect(() => setRecent(loadRecent()), [open]);

  const allActions: CommandAction[] = useMemo(
    () => [
      ...TAB_DEFINITIONS.map<CommandAction>((tab) => ({
        id: `goto-${tab.id}`,
        label: `Ir a ${tab.label}`,
        shortcut: tab.hotkey,
        hint: "Navegación",
        group: "Navegación",
        icon: tab.icon,
        run: () => onSelectTab(tab.id)
      })),
      ...extraActions
    ],
    [onSelectTab, extraActions]
  );

  const filtered = useMemo(() => {
    const q = query.trim();
    if (!q) {
      // Surface recent items first, then the rest of navigation.
      const recentSet = new Set(recent);
      const recents = recent
        .map((id) => allActions.find((a) => a.id === id))
        .filter((a): a is CommandAction => Boolean(a));
      const rest = allActions.filter((a) => !recentSet.has(a.id));
      return [...recents, ...rest].slice(0, 14);
    }
    return allActions
      .map((a) => ({ a, score: fuzzyScore(q, a.label) }))
      .filter(({ score }) => score >= 0)
      .sort((x, y) => y.score - x.score)
      .map(({ a }) => a)
      .slice(0, 14);
  }, [allActions, query, recent]);

  // Build groups (preserves order of `filtered`).
  const groups = useMemo(() => {
    const map = new Map<string, CommandAction[]>();
    for (const action of filtered) {
      const key = action.group ?? action.hint ?? "Acciones";
      const list = map.get(key) ?? [];
      list.push(action);
      map.set(key, list);
    }
    return [...map.entries()];
  }, [filtered]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActiveIndex(0);
    setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  useEffect(() => {
    if (activeIndex >= filtered.length) setActiveIndex(0);
  }, [activeIndex, filtered.length]);

  if (!open) return null;

  function pick(action: CommandAction) {
    const next = [action.id, ...recent.filter((id) => id !== action.id)].slice(0, 8);
    persistRecent(next);
    setRecent(next);
    action.run();
    // Navigation actions (id starts with "goto-") keep the palette open so
    // the operator (and external test harnesses) can issue a follow-up
    // search or jump without having to re-press Ctrl+K. ESC or backdrop
    // click still close the palette explicitly.
    if (!action.id.startsWith("goto-")) {
      onClose();
      return;
    }
    setQuery("");
    setActiveIndex(0);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  function handleKey(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(filtered.length - 1, index + 1));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(0, index - 1));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const action = filtered[activeIndex];
      if (action) pick(action);
    }
  }

  let flatIndex = -1;

  return (
    <div className="palette-backdrop" onClick={onClose} role="presentation">
      <div
        ref={dialogRef}
        className="palette"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Paleta de comandos"
        tabIndex={-1}
      >
        <div className="palette-search">
          <Icon name="search" size={16} />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="¿Qué querés hacer? (ESC para cerrar)"
            onKeyDown={handleKey}
            aria-label="Buscar acción"
          />
          {query && (
            <button
              className="ghost icon"
              type="button"
              onClick={() => setQuery("")}
              aria-label="Limpiar búsqueda"
            >
              <Icon name="close" size={14} />
            </button>
          )}
        </div>

        <ul>
          {filtered.length === 0 && (
            <li className="muted small" style={{ justifyContent: "center", cursor: "default" }}>
              Sin coincidencias.
            </li>
          )}
          {groups.map(([group, actions]) => (
            <li key={group} style={{ display: "block", padding: 0, cursor: "default" }}>
              <div className="palette-group">
                {!query && group === "Navegación" && recent.length > 0 && flatIndex < 0 ? "Recientes" : group}
              </div>
              {actions.map((action) => {
                flatIndex += 1;
                const isActive = flatIndex === activeIndex;
                const currentIndex = flatIndex;
                return (
                  <div
                    key={action.id}
                    className={`palette-row${isActive ? " active" : ""}`}
                    onMouseEnter={() => setActiveIndex(currentIndex)}
                    onClick={() => pick(action)}
                    role="button"
                    tabIndex={-1}
                  >
                    <span className="li-icon" aria-hidden="true">
                      <Icon name={action.icon ?? "arrowRight"} size={14} />
                    </span>
                    <span className="ellipsis">{action.label}</span>
                    <span className="palette-meta">
                      {action.shortcut && <kbd>{action.shortcut}</kbd>}
                    </span>
                  </div>
                );
              })}
            </li>
          ))}
        </ul>

        <div className="palette-foot">
          <span>
            <kbd>↑↓</kbd> mover
          </span>
          <span>
            <kbd>↵</kbd> abrir
          </span>
          <span>
            <kbd>esc</kbd> cerrar
          </span>
        </div>
      </div>
    </div>
  );
}
