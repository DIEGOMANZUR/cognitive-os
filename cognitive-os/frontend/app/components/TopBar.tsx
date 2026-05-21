"use client";

import { Icon } from "./Icon";

export function TopBar({
  apiBase,
  setApiBase,
  token,
  setToken,
  onOpenCommand,
  onOpenNotifications,
  notificationsUnread,
  online
}: {
  apiBase: string;
  setApiBase: (value: string) => void;
  token: string;
  setToken: (value: string) => void;
  onOpenCommand: () => void;
  onOpenNotifications: () => void;
  notificationsUnread: number;
  online: boolean;
}) {
  return (
    <div className="topbar" role="toolbar" aria-label="Barra principal">
      <div className="topbar-field grow">
        <span className="field-icon" aria-hidden="true">
          <Icon name="link" size={14} />
        </span>
        <input
          aria-label="URL base de la API"
          autoCapitalize="none"
          autoComplete="off"
          inputMode="url"
          spellCheck={false}
          value={apiBase}
          onChange={(event) => setApiBase(event.target.value)}
          placeholder="http://127.0.0.1:8000"
        />
      </div>
      <div className="topbar-sep" aria-hidden="true" />
      <div className="topbar-field grow">
        <span className="field-icon" aria-hidden="true">
          <Icon name="key" size={14} />
        </span>
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
      </div>

      <div className="topbar-sep" aria-hidden="true" />

      <button
        className="icon-btn ghost tip"
        type="button"
        data-tip="Buscar y comandos · Ctrl K"
        aria-label="Abrir buscador de comandos"
        onClick={onOpenCommand}
      >
        <Icon name="search" size={17} />
      </button>

      <button
        className="icon-btn ghost tip"
        type="button"
        data-tip={online ? "Centro de notificaciones" : "Sin conexión"}
        aria-label="Abrir centro de notificaciones"
        onClick={onOpenNotifications}
      >
        {online ? <Icon name="bell" size={17} /> : <Icon name="wifiOff" size={17} />}
        {notificationsUnread > 0 && <span className="dot-badge" aria-hidden="true" />}
        <span className="sr-only">
          {notificationsUnread > 0 ? `${notificationsUnread} no leídas` : "sin novedades"}
        </span>
      </button>
    </div>
  );
}
