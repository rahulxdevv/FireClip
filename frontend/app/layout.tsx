import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ToastViewport } from "@/components/toast";

export const metadata: Metadata = {
  title: {
    default: "FireClip - Find the moment. Make it viral.",
    template: "%s · FireClip",
  },
  description:
    "FireClip turns long videos, podcasts and streams into short-form clips with AI highlight detection, captions, smart cropping and one-click publishing.",
  applicationName: "FireClip",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#08080b",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-ink-950 text-paper">
        {children}
        <ToastViewport />
      </body>
    </html>
  );
}
