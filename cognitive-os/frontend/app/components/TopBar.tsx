"use client";

import type { Theme } from "../lib/types";

export function TopBar({
  apiBase,
  setApiBase,
  token,
  setToken,
  theme,
  toggleTheme
}: {
  apiBase: string;
  setApiBase: (value: string) => void;
  token: string;
  setToken: (value: string) => void;
  theme: Theme;
  toggleTheme: () => void;
}) {
  return (
    <div className="topbar">
      <label className="stack">
        <span className="muted small">API</span>
        <input
          aria-label="URL base de la API"
          autoCapitalize="none"
          autoComplete="off"
          inputMode="url"
          spellCheck={false}
          value={apiBase}
          onChange={(event) => setApiBase(event.target.value)}
        />
      </label>
      <label className="stack">
        <span className="muted small">JWT</span>
        <input
          aria-label="JWT local"
          autoCapitalize="none"
          autoComplete="off"
          spellCheck={false}
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="JWT local sin prefijo Bearer"
          type="password"
        />
      </label>
      <button
        aria-label="Cambiar tema"
        className="theme-toggle"
        onClick={toggleTheme}
        type="button"
        title="Cambiar tema"
      >
        {theme === "dark" ? "☀" : "☾"}
      </button>
    </div>
  );
}
