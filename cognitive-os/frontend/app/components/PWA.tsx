"use client";

import { useEffect, useState } from "react";

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

  const title = !online
    ? "Sin conexión"
    : updateReady
      ? "Actualización disponible"
      : "Instalar Cognitive OS";
  const detail = !online
    ? "La consola seguirá abriendo el shell cacheado; las APIs quedan en vivo cuando vuelva la red."
    : updateReady
      ? "Hay una nueva versión del cockpit lista para activar."
      : "Agregá el cockpit al escritorio para abrirlo como app local.";

  return (
    <div
      className={`pwa-prompt${!online ? " offline" : ""}${updateReady ? " update" : ""}`}
      role={canInstall || updateReady ? "dialog" : "status"}
      aria-live="polite"
    >
      <div className="stack">
        <strong>{title}</strong>
        <span className="small">{detail}</span>
      </div>
      <div className="row">
        {updateReady && (
          <button
            className="primary"
            onClick={() => {
              if (registration?.waiting) {
                registration.waiting.postMessage({ type: "COGOS_SKIP_WAITING" });
                return;
              }
              window.location.reload();
            }}
            type="button"
          >
            Actualizar
          </button>
        )}
        {canInstall && (
          <button
            className="primary"
            onClick={async () => {
              await installEvent.prompt();
              const choice = await installEvent.userChoice;
              if (choice.outcome === "accepted") setInstalled(true);
              setInstallEvent(null);
            }}
            type="button"
          >
            Instalar
          </button>
        )}
        {canInstall && (
          <button className="ghost" onClick={() => setHidden(true)} type="button">
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
