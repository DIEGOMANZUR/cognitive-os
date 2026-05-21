"use client";

import { useEffect, useState } from "react";

import { Icon } from "./Icon";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

export function PWA() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [online, setOnline] = useState(true);
  const [updateReady, setUpdateReady] = useState(false);
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    let onControllerChange: (() => void) | null = null;
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker
        .register("/sw.js")
        .then((registered) => {
          setRegistration(registered);
          if (registered.waiting) setUpdateReady(true);
          if (registered.installing) watchWorkerInstall(registered.installing, setUpdateReady);
          registered.addEventListener("updatefound", () => {
            if (registered.installing) watchWorkerInstall(registered.installing, setUpdateReady);
          });
        })
        .catch(() => {
          /* SW failures are non-fatal */
        });

      let refreshed = false;
      onControllerChange = () => {
        if (refreshed) return;
        refreshed = true;
        window.location.reload();
      };
      navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);
    }
    if (window.matchMedia("(display-mode: standalone)").matches) {
      setInstalled(true);
    }
    setOnline(navigator.onLine);
    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    const onPrompt = (event: Event) => {
      event.preventDefault();
      setInstallEvent(event as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setInstallEvent(null);
    };
    window.addEventListener("beforeinstallprompt", onPrompt as EventListener);
    window.addEventListener("appinstalled", onInstalled);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt as EventListener);
      window.removeEventListener("appinstalled", onInstalled);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      if (onControllerChange) {
        navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
      }
    };
  }, []);

  const canInstall = !installed && !hidden && installEvent;
  if (online && !updateReady && !canInstall) return null;

  const variant = !online ? "offline" : updateReady ? "update" : "install";
  const title =
    variant === "offline"
      ? "Sin conexión"
      : variant === "update"
        ? "Actualización disponible"
        : "Instalar Cognitive OS";
  const detail =
    variant === "offline"
      ? "La consola seguirá abriendo el shell cacheado; las APIs vuelven cuando regresa la red."
      : variant === "update"
        ? "Hay una nueva versión del cockpit lista para activar."
        : "Agregá el cockpit al escritorio para abrirlo como app local.";

  return (
    <div
      className={`pwa-prompt${!online ? " offline" : ""}${updateReady ? " update" : ""}`}
      role={canInstall || updateReady ? "dialog" : "status"}
      aria-live="polite"
    >
      <span className="pwa-mark" aria-hidden="true">
        <Icon
          name={
            variant === "offline" ? "wifiOff" : variant === "update" ? "refresh" : "install"
          }
          size={18}
        />
      </span>
      <div className="pwa-body stack" style={{ gap: 2 }}>
        <strong>{title}</strong>
        <span className="small">{detail}</span>
      </div>
      <div className="row" style={{ marginLeft: "auto" }}>
        {updateReady && (
          <button
            className="primary small"
            onClick={() => {
              if (registration?.waiting) {
                registration.waiting.postMessage({ type: "COGOS_SKIP_WAITING" });
                return;
              }
              window.location.reload();
            }}
            type="button"
          >
            <Icon name="refresh" size={13} /> Actualizar
          </button>
        )}
        {canInstall && (
          <button
            className="primary small"
            onClick={async () => {
              await installEvent.prompt();
              const choice = await installEvent.userChoice;
              if (choice.outcome === "accepted") setInstalled(true);
              setInstallEvent(null);
            }}
            type="button"
          >
            <Icon name="install" size={13} /> Instalar
          </button>
        )}
        {canInstall && (
          <button className="ghost small" onClick={() => setHidden(true)} type="button">
            Después
          </button>
        )}
      </div>
    </div>
  );
}

function watchWorkerInstall(
  worker: ServiceWorker,
  setUpdateReady: (value: boolean) => void
) {
  worker.addEventListener("statechange", () => {
    if (worker.state === "installed" && navigator.serviceWorker.controller) {
      setUpdateReady(true);
    }
  });
}
