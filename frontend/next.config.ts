import type { NextConfig } from "next";

const apiPort = process.env.API_PORT || "8000";
const apiBase = process.env.API_BASE_URL || `http://127.0.0.1:${apiPort}`;

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${apiBase}/health`,
      },
      {
        source: "/openapi",
        destination: `${apiBase}/docs`,
      },
      {
        source: "/openapi.json",
        destination: `${apiBase}/openapi.json`,
      },
    ];
  },
};

export default nextConfig;
