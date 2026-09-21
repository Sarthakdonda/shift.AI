import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "shift.AI",
    short_name: "shift.AI",
    description: "Clarity before complexity — the shift.AI workspace for phones.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#fbfaf8",
    theme_color: "#fbfaf8",
    icons: [
      { src: "/brand/logo-mark-512.png", sizes: "512x512", type: "image/png" },
      {
        src: "/brand/logo-mark-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
