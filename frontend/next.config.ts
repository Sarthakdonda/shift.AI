import type { NextConfig } from "next";
import { hostname, networkInterfaces } from "node:os";
const config: NextConfig = {
  poweredByHeader: false,
  devIndicators: false,
  distDir: process.env.SHIFT_TEST_BUILD_DIR || ".next",
  allowedDevOrigins: [
    hostname(),
    ...Object.values(networkInterfaces()).flatMap((addresses) =>
      (addresses || []).filter((address) => address.family === "IPv4").map((address) => address.address),
    ),
  ],
  async rewrites() {
    const backend = process.env.BACKEND_URL?.replace(/\/$/, "");
    return backend
      ? [{ source: "/backend/:path*", destination: `${backend}/:path*` }]
      : [];
  },
};
export default config;
