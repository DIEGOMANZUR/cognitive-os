"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { Tab } from "../lib/types";
import { TAB_DEFINITIONS } from "./Sidebar";

export type CommandAction = {
  id: string;
  label: string;
  shortcut?: string;
  hint?: string;
  run: () => void;
};

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
  const inputRef = useRef<HTMLInputElement>(null);

  const allActions: CommandAction[] = useMemo(
    () => [
      ...TAB_DEFINITIONS.map((tab) => ({
        id: `goto-${tab.id}`,
        label: `Ir a ${tab.label}`,
        shortcut: tab.hotkey,
        hint: "Navegación",
        run: () => onSelectTab(tab.id)
      })),
      ...extraActions
    ],
    [onSelectTab, extraActions]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allActions.slice(0, 12);
    return allActions
      .filter((action) => action.label.toLowerCase().includes(q))
      .slice(0, 12);
  }, [allActions, query]);

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

  function handleKey(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(filtered.length - 1, index + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(0, index - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const action = filtered[activeIndex];
      if (action) {
        action.run();
        onClose();
      }
    }
  }

  return (
    <div className="palette-backdrop" onClick={onClose} role="presentation">
      <div className="palette" onClick={(event) => event.stopPropagation()} role="dialog">
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="¿Qué querés hacer? (ESC para cerrar)"
          onKeyDown={handleKey}
        />
        <ul>
          {filtered.length === 0 && <li className="muted small">Sin coincidencias.</li>}
          {filtered.map((action, index) => (
            <li
              key={action.id}
              className={index === activeIndex ? "active" : ""}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => {
                action.run();
                onClose();
              }}
              role="presentation"
            >
              <span>{action.label}</span>
              <span className="palette-meta">
                {action.hint && <em>{action.hint}</em>}
                {action.shortcut && <kbd>{action.shortcut}</kbd>}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
