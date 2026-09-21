import type { NextConfig } from "next";
import { hostname, networkInterfaces } from "node:os";

/**
 * The app frontend is only ever rendered inside the Android shell (or a phone
 * browser during development), so it carries no marketing routes and no landing
 * page. It talks to the same backend as the website in ../frontend.
 */
const config: NextConfig = {
  poweredByHeader: false,
  devIndicators: false,
  // Verification builds stay out of the directory a running dev server owns.
  distDir: process.env.SHIFT_TEST_BUILD_DIR || ".next",
  allowedDevOrigins: [
    hostname(),
    ...Object.values(networkInterfaces()).flatMap((addresses) =>
      (addresses || [])
        .filter((address) => address.family === "IPv4")
        .map((address) => address.address),
    ),
  ],
  async headers() {
    return [
      {
        // The shell is an application surface, never a search result.
        source: "/:path*",
        headers: [
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default config;
