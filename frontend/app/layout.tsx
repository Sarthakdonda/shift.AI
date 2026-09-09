import { T } from "@/components/locale";
import type { Metadata, Viewport } from "next";
import { Providers } from "@/components/providers";
import { MobileInstall } from "@/components/mobile-install";
import { LocaleProvider } from "@/components/locale";
import "@fontsource-variable/inter";
import "./globals.css";

const description =
  "Understand your business problem. Discover the right solution — AI, automation, existing software, or a better process. Turn evidence into an actionable, reviewed blueprint.";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
  ),
  title: {
    default: "shift.AI — Clarity before complexity",
    template: "%s | shift.AI",
  },
  description,
  applicationName: "shift.AI",
  openGraph: {
    title: "shift.AI — Clarity before complexity",
    description,
    siteName: "shift.AI",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  colorScheme: "light",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <a className="skip-link" href="#main">
          <T text={"Skip to content"} />
        </a>
        <LocaleProvider>
          <Providers>
            <MobileInstall />
            {children}
          </Providers>
        </LocaleProvider>
      </body>
    </html>
  );
}
