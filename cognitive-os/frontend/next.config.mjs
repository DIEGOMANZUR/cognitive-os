import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const distDir = process.env.NEXT_DIST_DIR?.trim() || ".next";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  distDir,
  // The project path contains a space ("PROYECTO COGNITIVE OS") and there
  // are parent lockfiles outside the project (~/.local, ~/.opencode), so
  // Next.js 16 mis-infers the workspace root and refuses to compile
  // (`couldn't find next/package.json from <project>/app`) BEFORE reading
  // `turbopack.root` (the auto-inference runs first). Pin BOTH the
  // turbopack root and the file-tracing root to this directory.
  turbopack: { root: __dirname },
  outputFileTracingRoot: __dirname,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-DNS-Prefetch-Control", value: "on" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
          }
        ]
      }
    ];
  }
};

export default nextConfig;
