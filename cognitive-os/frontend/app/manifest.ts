import type { MetadataRoute } from "next";

/**
 * PWA manifest — declares the cockpit as an installable, dark-themed
 * standalone app. The shortcuts surface the most used views directly from
 * the launcher / Start menu (Chrome on Android, dock on macOS, Start tile
 * on Windows once installed).
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Cognitive OS — Command Center",
    short_name: "CogOS",
    description:
      "Centro de operaciones del Cognitive OS personal local-first. Dashboard, chat, jobs, aprobaciones y memoria del agente en un cockpit instalable.",
    start_url: "/?source=pwa",
    scope: "/",
    display: "standalone",
    display_override: ["window-controls-overlay", "standalone", "minimal-ui"],
    orientation: "any",
    background_color: "#04060c",
    theme_color: "#070a12",
    categories: ["productivity", "utilities", "developer"],
    lang: "es",
    dir: "ltr",
    prefer_related_applications: false,
    icons: [
      // PNG icons first — Android/Chrome/iOS treat raster as the canonical
      // install asset. SVG kept as the scalable any-size fallback for
      // desktops and progressive enhancement.
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any"
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any"
      },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable"
      },
      {
        src: "/icons/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any"
      },
      {
        src: "/icons/icon-maskable.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable"
      }
    ],
    shortcuts: [
      {
        name: "Abrir Chat",
        short_name: "Chat",
        description: "Chat orquestado con el DeepAgent",
        url: "/?tab=chat",
        icons: [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }]
      },
      {
        name: "Aprobaciones",
        short_name: "Aprob.",
        description: "Aprobaciones humanas pendientes",
        url: "/?tab=approvals",
        icons: [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }]
      },
      {
        name: "Jobs",
        short_name: "Jobs",
        description: "Estado y progreso de los jobs en curso",
        url: "/?tab=jobs",
        icons: [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }]
      },
      {
        name: "Health",
        short_name: "Health",
        description: "Health dashboard del stack",
        url: "/?tab=health",
        icons: [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }]
      }
    ]
  };
}
