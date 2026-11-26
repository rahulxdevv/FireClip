import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { ToastViewport } from "@/components/toast";

export const metadata: Metadata = {
  title: {
    default: "FireClip | AI clipping, editing and publishing",
    template: "%s | FireClip",
  },
  description:
    "FireClip turns long videos and streams into short-form clips with explainable AI highlights, captions, framing and one-click publishing.",
  applicationName: "FireClip",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/icon.svg", type: "image/svg+xml" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
  },
};

export const viewport: Viewport = {
  themeColor: "#07070c",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={GeistSans.variable + " " + GeistMono.variable}>
      <body className="min-h-screen bg-ink-950 text-paper antialiased">
        {children}
        <ToastViewport />
      </body>
    </html>
  );
}
