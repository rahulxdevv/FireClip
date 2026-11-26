import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { ToastViewport } from "@/components/toast";

const display = localFont({
  src: "./fonts/bricolage-grotesque-var.woff2",
  variable: "--font-bricolage",
  weight: "400 800",
  display: "swap",
  fallback: ["ui-sans-serif", "system-ui", "sans-serif"],
});

const sans = localFont({
  src: "./fonts/manrope-var.woff2",
  variable: "--font-manrope",
  weight: "300 800",
  display: "swap",
  fallback: ["ui-sans-serif", "system-ui", "sans-serif"],
});

export const metadata: Metadata = {
  title: {
    default: "FireClip: find the moment, make it viral",
    template: "%s | FireClip",
  },
  description:
    "FireClip turns long videos, podcasts and streams into short-form clips with AI highlight detection, captions, smart cropping and one-click publishing.",
  applicationName: "FireClip",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#0a0908",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable}`}>
      <body className="min-h-screen bg-ink-950 text-paper antialiased">
        {children}
        <ToastViewport />
      </body>
    </html>
  );
}
