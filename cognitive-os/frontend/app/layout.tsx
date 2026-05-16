import type { Metadata, Viewport } from "next";

import "./globals.css";

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
    icon: [{ url: "/icons/icon-192.svg", type: "image/svg+xml", sizes: "192x192" }],
    apple: [{ url: "/icons/apple-touch-icon.svg", sizes: "180x180" }]
  },
  formatDetection: {
    telephone: false,
    email: false,
    address: false
  }
};

export const viewport: Viewport = {
  themeColor: "#0b1020",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
