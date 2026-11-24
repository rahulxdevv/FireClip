import type { Metadata } from "next";
import { InviteClient } from "./client";

export const metadata: Metadata = { title: "Workspace invitation" };

export default async function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <InviteClient token={token} />;
}
