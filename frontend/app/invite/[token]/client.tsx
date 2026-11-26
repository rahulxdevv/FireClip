"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { ArrowRight, Mail, Users } from "lucide-react";
import { AuthLayout } from "@/components/auth-form";
import { Alert, Button, Field, Input, PageSkeleton } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useSessionStore } from "@/lib/stores";
import type { Session } from "@/lib/types";

interface Preview {
  workspace_id: string;
  email: string;
  workspace_name: string;
  workspace_slug: string;
  role: string;
  account_exists: boolean;
}

export function InviteClient({ token }: { token: string }) {
  const router = useRouter();
  const setSession = useSessionStore((state) => state.setSession);
  const setActiveWorkspace = useSessionStore((state) => state.setActiveWorkspace);
  const [preview, setPreview] = React.useState<Preview | null>(null);
  const [signedIn, setSignedIn] = React.useState<boolean | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [form, setForm] = React.useState({ name: "", password: "" });
  const [submitting, setSubmitting] = React.useState(false);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [info, session] = await Promise.all([
          api.get<Preview>(`/api/auth/invite/${token}`),
          api.get<Session>("/api/auth/me").catch(() => null),
        ]);
        if (!active) return;
        setPreview(info);
        setSignedIn(Boolean(session));
      } catch (err) {
        if (active) setError(errorMessage(err));
      }
    })();
    return () => {
      active = false;
    };
  }, [token]);

  async function acceptExisting() {
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/api/workspaces/invites/${token}/accept`);
      const session = await api.get<Session>("/api/auth/me");
      setSession(session);
      setActiveWorkspace(preview?.workspace_id || session.active_workspace_id || "");
      router.replace("/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function createAccount(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const session = await api.post<Session>(`/api/auth/invite/${token}/accept`, form);
      setSession(session);
      router.replace("/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (!preview && !error) {
    return (
      <AuthLayout title="Opening invitation" subtitle="Verifying this single-use link." footer={null}>
        <PageSkeleton />
      </AuthLayout>
    );
  }

  if (error && !preview) {
    return (
      <AuthLayout
        title="Invitation unavailable"
        subtitle="This link may have expired or already been used."
        footer={<Link href="/login" className="text-flame-400">Go to sign in</Link>}
      >
        <Alert>{error}</Alert>
      </AuthLayout>
    );
  }

  if (!preview) return null;

  return (
    <AuthLayout
      title={`Join ${preview.workspace_name}`}
      subtitle={`You were invited as ${preview.role}. Invitation for ${preview.email}.`}
      footer={
        <Link href="/login" className="text-flame-400 hover:text-flame-500">
          Already have another account? Sign in
        </Link>
      }
    >
      <div className="space-y-4">
        <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/4 p-4">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-flame-500/12 text-flame-500">
            <Users className="h-4 w-4" />
          </span>
          <div>
            <p className="text-[13px] font-medium text-paper">{preview.workspace_name}</p>
            <p className="font-mono text-[10.5px] text-faint">{preview.workspace_slug}, {preview.role}</p>
          </div>
        </div>

        {error ? <Alert>{error}</Alert> : null}

        {preview.account_exists ? (
          signedIn ? (
            <Button className="w-full" size="lg" loading={submitting} onClick={acceptExisting}>
              Accept invitation <ArrowRight className="h-4 w-4" />
            </Button>
          ) : (
            <div className="space-y-3">
              <Alert tone="info" title="Account already exists">
                Sign in with <span className="font-mono">{preview.email}</span>, then reopen this invitation link.
              </Alert>
              <Link href="/login">
                <Button className="w-full" size="lg">
                  <Mail className="h-4 w-4" /> Sign in to accept
                </Button>
              </Link>
            </div>
          )
        ) : (
          <form onSubmit={createAccount} className="space-y-4">
            <Field label="Your name">
              <Input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                placeholder="Alex Rivera"
                autoComplete="name"
                maxLength={120}
              />
            </Field>
            <Field label="Password" hint="At least 8 characters with letters and numbers.">
              <Input
                type="password"
                required
                minLength={8}
                value={form.password}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
                autoComplete="new-password"
              />
            </Field>
            <Button type="submit" className="w-full" size="lg" loading={submitting}>
              Create account & join <ArrowRight className="h-4 w-4" />
            </Button>
          </form>
        )}
      </div>
    </AuthLayout>
  );
}
