import type { Metadata, Viewport } from "next";
import { Providers } from "@/components/providers";
import "@fontsource-variable/inter";
import "./globals.css";

export const metadata: Metadata = {
  title: "shift.AI",
  applicationName: "shift.AI",
  description:
    "Understand the problem before choosing the solution. The shift.AI workspace, built for your phone.",
  robots: { index: false, follow: false },
  formatDetection: { telephone: false, address: false, email: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // The app frame is fixed, so the keyboard resizes the content instead of
  // scrolling the page behind it.
  interactiveWidget: "resizes-content",
  viewportFit: "cover",
  themeColor: "#fbfaf8",
  colorScheme: "light",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
