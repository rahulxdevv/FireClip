"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { ArrowRight, Flame, Loader2 } from "lucide-react";
import { Alert, Button, Field, Input } from "@/components/ui";
import { Logo } from "@/components/logo";
import { api, errorMessage } from "@/lib/api";
import { useSessionStore } from "@/lib/stores";
import type { Session } from "@/lib/types";

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.05fr]">
      <div className="relative hidden overflow-hidden border-r border-white/8 bg-ink-900 lg:block">
        <div className="pointer-events-none absolute inset-0 ember-glow" />
        <div className="pointer-events-none absolute inset-0 grid-lines opacity-40" />
        <div className="relative flex h-full flex-col justify-between p-10">
          <Logo size={34} />
          <div className="max-w-md">
            <p className="text-[34px] font-semibold leading-tight tracking-tight">
              Every long recording has a clip hiding in it.
            </p>
            <p className="mt-4 text-[13.5px] leading-relaxed text-muted">
              FireClip reads the transcript, weighs the signals, and shows you exactly why a moment
              is worth cutting. Then it helps you make it.
            </p>
            <div className="mt-8 grid grid-cols-2 gap-4">
              {[
                ["12", "scoring signals"],
                ["4", "aspect presets"],
                ["1", "FFmpeg pipeline"],
                ["0", "black-box scores"],
              ].map(([value, label]) => (
                <div key={label} className="rounded-lg border border-white/8 bg-ink-950/40 p-3">
                  <p className="font-mono text-[18px] font-semibold text-flame-500">{value}</p>
                  <p className="mt-0.5 text-[11px] text-faint">{label}</p>
                </div>
              ))}
            </div>
          </div>
          <p className="text-[11px] text-faint">Open architecture · your footage, your storage, your keys.</p>
        </div>
      </div>

      <div className="flex items-center justify-center px-5 py-12">
        <div className="w-full max-w-[400px]">
          <div className="mb-8 lg:hidden">
            <Logo size={32} />
          </div>
          <div className="mb-7">
            <h1 className="text-[26px] font-semibold tracking-tight">{title}</h1>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{subtitle}</p>
          </div>
          {children}
          <div className="mt-6 text-center text-[12.5px] text-muted">{footer}</div>
        </div>
      </div>
    </div>
  );
}

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const setSession = useSessionStore((state) => state.setSession);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [form, setForm] = React.useState({
    email: "",
    password: "",
    name: "",
    workspace_name: "",
  });

  function update(key: keyof typeof form) {
    return (event: React.ChangeEvent<HTMLInputElement>) =>
      setForm((current) => ({ ...current, [key]: event.target.value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const session =
        mode === "register"
          ? await api.post<Session>("/api/auth/register", {
              email: form.email,
              password: form.password,
              name: form.name,
              workspace_name: form.workspace_name,
            })
          : await api.post<Session>("/api/auth/login", {
              email: form.email,
              password: form.password,
            });
      setSession(session);
      router.replace("/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {mode === "register" ? (
        <Field label="Your name">
          <Input
            value={form.name}
            onChange={update("name")}
            placeholder="Alex Rivera"
            autoComplete="name"
            maxLength={120}
          />
        </Field>
      ) : null}
      <Field label="Email">
        <Input
          type="email"
          required
          value={form.email}
          onChange={update("email")}
          placeholder="you@studio.com"
          autoComplete="email"
        />
      </Field>
      <Field
        label="Password"
        hint={mode === "register" ? "At least 8 characters, mixing letters and numbers." : undefined}
      >
        <Input
          type="password"
          required
          minLength={8}
          value={form.password}
          onChange={update("password")}
          placeholder="••••••••"
          autoComplete={mode === "register" ? "new-password" : "current-password"}
        />
      </Field>
      {mode === "register" ? (
        <Field label="Workspace name" hint="You can invite teammates later.">
          <Input
            value={form.workspace_name}
            onChange={update("workspace_name")}
            placeholder="Night Shift Studio"
            maxLength={120}
          />
        </Field>
      ) : null}

      {error ? <Alert>{error}</Alert> : null}

      <Button type="submit" className="w-full" size="lg" loading={submitting}>
        {mode === "register" ? "Create workspace" : "Sign in"}
        {!submitting ? <ArrowRight className="h-4 w-4" /> : null}
      </Button>

      <div className="flex items-center gap-3 pt-1 text-[11px] text-faint">
        <Flame className="h-3.5 w-3.5 text-flame-500" />
        Sessions are stored in secure HTTP-only cookies.
      </div>
    </form>
  );
}

export function AuthSwitch({ mode }: { mode: "login" | "register" }) {
  return mode === "login" ? (
    <>
      New to FireClip?{" "}
      <Link href="/register" className="font-medium text-flame-400 hover:text-flame-500">
        Create an account
      </Link>
    </>
  ) : (
    <>
      Already have a workspace?{" "}
      <Link href="/login" className="font-medium text-flame-400 hover:text-flame-500">
        Sign in
      </Link>
    </>
  );
}
