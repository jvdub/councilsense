import type { NextConfig } from "next";

const backend = process.env.COUNCILSENSE_BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
      {
        source: "/raw/:path*",
        destination: `${backend}/raw/:path*`,
      },
    ];
  },
};

export default nextConfig;
