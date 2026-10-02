import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,

  async rewrites() {
    return [
      {
        source: "/api/:path*/",
        destination: "https://niprix.onrender.com/api/:path*/",
      },
    ];
  },
};

export default nextConfig;
