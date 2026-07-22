import type { NextConfig } from "next";

// Standalone output is required for Docker/self-hosted deployments.
// Vercel handles its own bundling, so we disable standalone there.
// Vercel automatically sets VERCEL=1 during build.
const isVercel = process.env.VERCEL === "1";

const nextConfig: NextConfig = {
  // Only use standalone output for Docker; Vercel does not support it.
  ...(isVercel ? {} : { output: "standalone" }),

  // Allow images from S3, Render-hosted backend, and localhost during development
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "*.amazonaws.com",
        pathname: "/**",
      },
      {
        // Render backend (e.g. smarthire-api.onrender.com)
        protocol: "https",
        hostname: "*.onrender.com",
        pathname: "/**",
      },
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/**",
      },
    ],
  },

  // Forward API requests to backend in dev (avoids CORS issues with localhost)
  async rewrites() {
    return process.env.NODE_ENV === "development"
      ? [
          {
            source: "/api/v1/:path*",
            destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/:path*`,
          },
        ]
      : [];
  },

  // Security headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
