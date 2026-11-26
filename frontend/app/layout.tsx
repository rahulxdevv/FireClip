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
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#07070c" },
  ],
  colorScheme: "light dark",
  width: "device-width",
  initialScale: 1,
};

const THEME_SCRIPT =
  '(function(){var t=null;try{t=localStorage.getItem("fireclip-theme")}catch(e){}if(t!=="light"&&t!=="dark"){t=window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";}document.documentElement.dataset.theme=t;})();';

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning className={GeistSans.variable + " " + GeistMono.variable}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-screen bg-ink-950 text-paper antialiased">
        {children}
        <ToastViewport />
      </body>
    </html>
  );
}
