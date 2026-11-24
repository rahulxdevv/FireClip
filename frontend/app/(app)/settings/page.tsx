"use client";

import Link from "next/link";
import * as React from "react";
import { KeyRound, MailCheck, ShieldCheck, UserRound } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { Alert, Badge, Button, Field, Input, Panel, PanelHeader } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { toast, useSessionStore } from "@/lib/stores";
import { formatDateTime } from "@/lib/format";
import type { Session } from "@/lib/types";

export default function SettingsPage() {
  const user = useSessionStore((state) => state.user);
  const workspace = useSessionStore((state) =>
    state.workspaces.find((item) => item.id === state.activeWorkspaceId),
  );
  const setSession = useSessionStore((state) => state.setSession);
  const [name, setName] = React.useState(user?.name || "");
  const [savingName, setSavingName] = React.useState(false);
  const [passwords, setPasswords] = React.useState({ current_password: "", new_password: "", confirm: "" });
  const [savingPassword, setSavingPassword] = React.useState(false);
  const [passwordError, setPasswordError] = React.useState<string | null>(null);
  const [resending, setResending] = React.useState(false);
  const [verifyLink, setVerifyLink] = React.useState<string | null>(null);

  React.useEffect(() => setName(user?.name || ""), [user?.name]);

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    setSavingName(true);
    try {
      await api.patch("/api/auth/profile", { name: name.trim() });
      const session = await api.get<Session>("/api/auth/me");
      setSession(session);
      toast("Profile updated", "success");
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setSavingName(false);
    }
  }

  async function resendVerification() {
    setResending(true);
    setVerifyLink(null);
    try {
      const result = await api.post<{ sent: boolean; configured: boolean; dev_link: string | null }>(
        "/api/auth/resend-verification",
      );
      if (result.dev_link) setVerifyLink(result.dev_link);
      toast(
        result.sent
          ? "Verification email sent"
          : result.configured
            ? "Email provider accepted the request"
            : "Email is not configured on this instance",
        result.sent ? "success" : "info",
      );
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setResending(false);
    }
  }

  async function changePassword(event: React.FormEvent) {
    event.preventDefault();
    setPasswordError(null);
    if (passwords.new_password !== passwords.confirm) {
      setPasswordError("The new passwords do not match.");
      return;
    }
    setSavingPassword(true);
    try {
      await api.post("/api/auth/password", {
        current_password: passwords.current_password,
        new_password: passwords.new_password,
      });
      setPasswords({ current_password: "", new_password: "", confirm: "" });
      toast("Password changed", "success", "Other sessions will expire when their tokens do.");
    } catch (err) {
      setPasswordError(errorMessage(err));
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        eyebrow="Account"
        title="My settings"
        description="Your personal profile and security settings. Workspace-level options live under Workspace."
      />

      <div className="space-y-5">
        <Panel>
          <PanelHeader title="Profile" description="Shown in activity logs and member lists." />
          <form onSubmit={saveProfile} className="space-y-4 p-5">
            <div className="flex items-center gap-3">
              <span
                className="flex h-12 w-12 items-center justify-center rounded-xl text-[16px] font-semibold text-[#160b04]"
                style={{ backgroundColor: user?.avatar_color || "#ff6a1f" }}
              >
                {(user?.name || "?").slice(0, 1).toUpperCase()}
              </span>
              <div className="text-[11.5px] text-faint">
                <p>Avatar colors are assigned automatically.</p>
                <p>Member since {formatDateTime(user?.created_at)}</p>
              </div>
            </div>
            <Field label="Name">
              <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} />
            </Field>
            <Field label="Email" hint="Contact the operator if you need to change the address on this account.">
              <Input value={user?.email || ""} disabled />
            </Field>
            <div className="rounded-lg border border-white/8 bg-ink-850/50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-[12px]">
                  <MailCheck className="h-4 w-4 text-faint" />
                  {user?.email_verified_at ? (
                    <span className="text-muted">
                      Email confirmed {formatDateTime(user.email_verified_at)}
                    </span>
                  ) : (
                    <span className="text-muted">Email not confirmed yet</span>
                  )}
                </div>
                {user?.email_verified_at ? (
                  <Badge tone="mint">verified</Badge>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    loading={resending}
                    onClick={resendVerification}
                  >
                    Resend link
                  </Button>
                )}
              </div>
              {verifyLink ? (
                <p className="mt-2 break-all font-mono text-[10px] text-faint">
                  Development link:{" "}
                  <a href={verifyLink} className="text-flame-400 hover:text-flame-500">
                    {verifyLink}
                  </a>
                </p>
              ) : null}
            </div>
            <Button type="submit" loading={savingName} disabled={!name.trim() || name === user?.name}>
              Save profile
            </Button>
          </form>
        </Panel>

        <Panel>
          <PanelHeader title="Password" description="Changing your password rotates your session cookies." />
          <form onSubmit={changePassword} className="grid gap-4 p-5 sm:grid-cols-2">
            <Field label="Current password" className="sm:col-span-2">
              <Input
                type="password"
                required
                autoComplete="current-password"
                value={passwords.current_password}
                onChange={(event) => setPasswords({ ...passwords, current_password: event.target.value })}
              />
            </Field>
            <Field label="New password" hint="At least 8 characters, letters and numbers.">
              <Input
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={passwords.new_password}
                onChange={(event) => setPasswords({ ...passwords, new_password: event.target.value })}
              />
            </Field>
            <Field label="Confirm new password">
              <Input
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={passwords.confirm}
                onChange={(event) => setPasswords({ ...passwords, confirm: event.target.value })}
              />
            </Field>
            {passwordError ? <div className="sm:col-span-2"><Alert>{passwordError}</Alert></div> : null}
            <div className="sm:col-span-2">
              <Button type="submit" loading={savingPassword} variant="outline">
                <KeyRound className="h-4 w-4" /> Update password
              </Button>
            </div>
          </form>
        </Panel>

        <Panel>
          <PanelHeader title="Session & access" />
          <div className="divide-y divide-white/6 text-[11.5px]">
            <div className="flex items-center justify-between gap-3 px-5 py-3">
              <span className="flex items-center gap-2 text-muted"><ShieldCheck className="h-4 w-4 text-mint" /> Session storage</span>
              <span className="font-mono text-faint">HTTP-only cookie · SameSite=Lax</span>
            </div>
            <div className="flex items-center justify-between gap-3 px-5 py-3">
              <span className="flex items-center gap-2 text-muted"><UserRound className="h-4 w-4" /> Workspace role</span>
              <span className="font-mono text-faint">{workspace?.role || "-"}</span>
            </div>
            <div className="px-5 py-3">
              <p className="text-muted">API keys and team members</p>
              <p className="mt-1 text-faint">
                Manage them in{" "}
                <Link href="/workspace" className="text-flame-400 hover:text-flame-500">Workspace</Link>.
              </p>
            </div>
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Data & privacy" />
          <div className="space-y-2 p-5 text-[11.5px] leading-relaxed text-faint">
            <p>Uploaded media lives in the configured storage backend and is served only through authenticated endpoints.</p>
            <p>Transcripts and AI analyses are stored in your database. Provider API keys are encrypted with AES-GCM.</p>
            <p>Deleting a video removes its media files and cascades to transcripts, clips and editing projects.</p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
