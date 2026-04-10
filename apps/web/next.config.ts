import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Standalone output is required for `apps/web/Dockerfile` but breaks `next start` locally (Next warns + missing chunks → 500). */
const useStandalone = process.env.NEXT_STANDALONE === "1";

/** Server-side proxy target for same-origin `/api/*` → backend (avoids browser CORS and wrong NEXT_PUBLIC_API_URL). */
const apiProxyTarget = (process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@axiom/shared"],
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiProxyTarget}/:path*` }];
  },
  ...(useStandalone
    ? {
        output: "standalone" as const,
        // Monorepo: trace files from repo root for Docker image.
        outputFileTracingRoot: path.join(__dirname, "../.."),
      }
    : {}),
};

export default nextConfig;
