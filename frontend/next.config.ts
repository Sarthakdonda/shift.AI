import type { NextConfig } from "next";
import { hostname, networkInterfaces } from "node:os";
const config: NextConfig = {
  poweredByHeader: false,
  devIndicators: false,
  distDir: process.env.SHIFT_TEST_BUILD_DIR || ".next",
  allowedDevOrigins: [
    hostname(),
    ...Object.values(networkInterfaces()).flatMap((addresses) =>
      (addresses || [])
        .filter((address) => address.family === "IPv4")
        .map((address) => address.address),
    ),
  ],
  async rewrites() {
    const backend = process.env.BACKEND_URL?.replace(/\/$/, "");
    return backend
      ? [{ source: "/backend/:path*", destination: `${backend}/:path*` }]
      : [];
  },
  async headers() {
    return [
      ...["/login", "/signup"].map((source) => ({
        source,
        headers: [
          {
            key: "Cross-Origin-Opener-Policy",
            value: "same-origin-allow-popups",
          },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      })),
      {
        source: "/downloads/shift-ai.apk",
        headers: [
          {
            key: "Content-Type",
            value: "application/vnd.android.package-archive",
          },
          {
            key: "Content-Disposition",
            value: 'attachment; filename="shift-ai.apk"',
          },
          { key: "Cache-Control", value: "public, max-age=0, must-revalidate" },
        ],
      },
    ];
  },
};
export default config;
