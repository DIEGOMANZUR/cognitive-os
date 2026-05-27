import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { ErrorBoundary } from "./components/ErrorBoundary";
import "./globals.css";

// Self-hosted by next/font at build time — no runtime request, no FOIT,
// and the PWA works fully offline (the font files are part of the bundle).
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans"
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono"
});

export const metadata: Metadata = {
  title: "Cognitive OS",
  description: "Centro de operaciones del Cognitive OS personal local-first.",
  manifest: "/manifest.webmanifest",
  applicationName: "Cognitive OS",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Cognitive OS"
  },
  icons: {
    icon: [
      { url: "/icons/icon.svg", type: "image/svg+xml" },
      { url: "/icons/icon-192.png", type: "image/png", sizes: "192x192" },
      { url: "/icons/icon-512.png", type: "image/png", sizes: "512x512" }
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }]
  },
  formatDetection: {
    telephone: false,
    email: false,
    address: false
  }
};

export const viewport: Viewport = {
  themeColor: "#070a12",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover"
};

// Inlined into <head> as a blocking script so the responsive breakpoint
// is reflected on <html data-cogos-viewport="..."> from the very first
// paint, before React hydrates. Required so external test harnesses
// (TestSprite, Playwright CDP) that swap viewport via
// `Emulation.setDeviceMetricsOverride` immediately see a DOM signal even
// if the hydration cycle hasn't run yet. The same logic re-runs every
// 200ms as a safety net and on every resize/orientation/visualViewport
// event we can observe.
const RESPONSIVE_BOOT_SCRIPT = `
(function () {
  try {
    var BP = 920;
    var root = document.documentElement;
    function measure() {
      var widths = [
        window.innerWidth || Infinity,
        (window.visualViewport && window.visualViewport.width) || Infinity,
        root.clientWidth || Infinity,
        (document.body && document.body.clientWidth) || Infinity
      ];
      var minW = Math.min.apply(null, widths);
      var mode = minW <= BP ? "mobile" : "desktop";
      if (root.getAttribute("data-cogos-viewport") !== mode) {
        root.setAttribute("data-cogos-viewport", mode);
      }
    }
    measure();
    window.addEventListener("resize", measure, { passive: true });
    window.addEventListener("orientationchange", measure, { passive: true });
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", measure, { passive: true });
    }
    setInterval(measure, 200);
  } catch (e) {
    /* keep boot resilient: if anything fails we just leave the desktop default */
  }
})();
`;

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      data-theme="dark"
      data-cogos-viewport="desktop"
      className={`${inter.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: RESPONSIVE_BOOT_SCRIPT }} />
      </head>
      <body>
        <ErrorBoundary>{children}</ErrorBoundary>
      </body>
    </html>
  );
}
