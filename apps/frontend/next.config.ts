import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Django's URL patterns are slash-sensitive. Keep the URL supplied by the
  // client intact so POST bodies are never lost to Next's slash redirect.
  skipTrailingSlashRedirect: true,
};

export default nextConfig;
