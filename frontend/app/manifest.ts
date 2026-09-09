import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "shift.AI — Transformation workspace",
    short_name: "shift.AI",
    description: "Discover, design, review and plan business transformation.",
    start_url: "/dashboard",
    display: "standalone",
    background_color: "#fff4e6",
    theme_color: "#0b1320",
    icons: [
      {
        src: "/brand/logo-mark-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
    ],
  };
}
