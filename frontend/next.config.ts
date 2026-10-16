import type { NextConfig } from "next";

// The browser only talks to this Next.js server. Every /api/* request is
// forwarded to FastAPI, so the session cookie stays same-origin and no CORS
// setup is needed.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8010";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
