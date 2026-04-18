import os from "node:os";

/** @type {import('next').NextConfig} */
function getAllowedDevOrigins() {
  const port = process.env.PORT || process.env.FRONTEND_PORT || "3000";
  const origins = new Set(["localhost", "127.0.0.1", "0.0.0.0"]);

  for (const entries of Object.values(os.networkInterfaces())) {
    for (const entry of entries ?? []) {
      if (entry.family !== "IPv4" || entry.internal) continue;
      origins.add(entry.address);
    }
  }

  for (const origin of (process.env.NEXT_ALLOWED_DEV_ORIGINS || "").split(",")) {
    const trimmed = origin.trim();
    if (!trimmed) continue;

    if (/^https?:\/\//i.test(trimmed)) {
      try {
        origins.add(new URL(trimmed).hostname);
        continue;
      } catch {
        // fall through to raw value
      }
    }

    origins.add(trimmed);
  }

  return Array.from(origins);
}

const nextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  basePath: "/console",
  allowedDevOrigins: getAllowedDevOrigins(),
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: process.env.NEXT_PUBLIC_API_BASE_URL
          ? `${process.env.NEXT_PUBLIC_API_BASE_URL}/:path*`
          : "http://localhost:8000/api/v1/:path*",
        basePath: false,
      },
    ];
  },
};

export default nextConfig;
