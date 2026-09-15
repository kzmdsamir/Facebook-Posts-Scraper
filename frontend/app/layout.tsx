import type { Metadata, Viewport } from "next";
import { Jost } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";

const jost = Jost({
  subsets: ["latin"],
  variable: "--font-jost",
  weight: ["100", "200", "300", "400", "500", "600", "700"],
  display: "swap",
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "PostHarvest",
    template: "%s · PostHarvest",
  },
  description:
    "Extract publicly available Facebook page and profile posts with live progress tracking, preview, and JSON / CSV / Excel export. Throttled and compliant, no auth bypass.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "PostHarvest",
    title: "PostHarvest",
    description:
      "Extract publicly available Facebook page and profile posts with live progress tracking, preview, and JSON / CSV / Excel export. Throttled and compliant, no auth bypass.",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "PostHarvest",
    description:
      "Extract publicly available Facebook posts with live progress tracking and JSON / CSV / Excel export.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#09090b" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`light ${jost.variable}`} suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}