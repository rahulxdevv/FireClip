import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Workspace invitation | FireClip",
  robots: { index: false, follow: false, nocache: true },
};

export default function SharedClipLayout({ children }: { children: React.ReactNode }) {
  return children;
}
