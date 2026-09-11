import type { NextConfig } from "next";
const config: NextConfig = {
  poweredByHeader: false,
  devIndicators: false,
  distDir: process.env.SHIFT_TEST_BUILD_DIR || ".next",
  async rewrites() {
    const backend = process.env.BACKEND_URL?.replace(/\/$/, "");
    return backend
      ? [{ source: "/backend/:path*", destination: `${backend}/:path*` }]
      : [];
  },
};
export default config;
