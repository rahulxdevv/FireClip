"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { ArrowRight, Flame, MailCheck } from "lucide-react";
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
    <div className="grid min-h-screen bg-ink-950 lg:grid-cols-[1.02fr_1fr]">
      <aside className="relative hidden overflow-hidden border-r border-paper/[0.07] bg-ink-900 p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="relative">
          <Link href="/" aria-label="FireClip home">
            <Logo size={30} />
          </Link>
        </div>
        <div className="relative max-w-[430px]">
          <h2 className="display text-[40px] text-paper">
            Every long recording has a clip hiding in it.
          </h2>
          <p className="mt-5 text-[13.5px] leading-relaxed text-muted">
            FireClip reads the transcript, weighs the signals, and shows you exactly why a moment is
            worth cutting. Then it helps you make it.
          </p>
          <dl className="mt-9 divide-y divide-paper/[0.08] border-y border-paper/[0.08]">
            {[
              ["87", "Strong hook", "the opening line lands in 3 words"],
              ["79", "Story payoff", "a claim, then the reason for it"],
              ["74", "Concrete result", "numbers repeated from the source"],
            ].map(([score, label, note]) => (
              <div key={label} className="flex items-baseline gap-4 py-3">
                <dt className="font-display text-[15px] font-semibold tabular-nums text-flame-400">{score}</dt>
                <dd className="text-[12.5px] leading-snug text-muted">
                  <span className="font-medium text-paper">{label}</span>
                  <span className="block text-[11.5px] text-faint">{note}</span>
                </dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="relative flex flex-wrap items-center gap-x-5 gap-y-1 text-[11.5px] text-faint">
          <span>Open architecture</span>
          <span>Files stay on your own storage</span>
        </div>
      </aside>

      <main className="relative flex items-start justify-center overflow-hidden px-5 pb-12 pt-7 lg:items-center lg:py-12">
        <Link
          href="/"
          className="absolute right-6 top-6 hidden text-[12px] text-faint transition-colors hover:text-paper lg:block"
        >
          Back to site
        </Link>
          <div className="relative w-full max-w-[400px]">
          <div className="mb-10 flex items-center justify-between lg:hidden">
            <Link href="/" aria-label="FireClip home">
              <Logo size={30} />
            </Link>
            <Link href="/" className="text-[12px] text-faint transition-colors hover:text-paper">
              Back to site
            </Link>
          </div>
          <div className="mb-8">
            <h1 className="display text-[30px] text-paper">{title}</h1>
            <p className="mt-2 text-[13.5px] leading-relaxed text-muted">{subtitle}</p>
          </div>
          {children}
          <div className="mt-7 text-center text-[12.5px] text-muted">{footer}</div>
        </div>
      </main>
    </div>
  );
}

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const setSession = useSessionStore((state) => state.setSession);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [verification, setVerification] = React.useState<{
    email: string;
    sent: boolean;
    link: string | null;
  } | null>(null);
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
          ? await api.post<Session & {
              verification_required?: boolean;
              verification_email_sent?: boolean;
              verification_link?: string | null;
            }>("/api/auth/register", {
              email: form.email,
              password: form.password,
              name: form.name,
              workspace_name: form.workspace_name,
            })
          : await api.post<Session>("/api/auth/login", {
              email: form.email,
              password: form.password,
            });
      const result = session as Session & {
        verification_required?: boolean;
        verification_email_sent?: boolean;
        verification_link?: string | null;
      };
      if (mode === "register" && result.verification_required) {
        setVerification({
          email: form.email,
          sent: Boolean(result.verification_email_sent),
          link: result.verification_link || null,
        });
        return;
      }
      setSession(session);
      router.replace("/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (verification) {
    return (
      <div className="space-y-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-[var(--radius-card)] border border-paper/10 bg-flame-500/10 text-flame-500">
          <MailCheck className="h-5 w-5" />
        </div>
        <div>
          <p className="text-[15px] font-medium">Check your email</p>
          <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
            {verification.sent
              ? "We sent a confirmation link to " + verification.email + ". Open it, then sign in."
              : "Email delivery is not configured on this instance. Use the development link below to confirm " + verification.email + "."}
          </p>
        </div>
        {verification.link ? (
          <a
            href={verification.link}
            className="block break-all rounded-[var(--radius-control)] border border-flame-500/30 bg-ink-850 px-3 py-2 font-mono text-[11px] text-flame-400 hover:text-flame-500"
          >
            {verification.link}
          </a>
        ) : null}
        <Link href="/login" className="block">
          <Button className="w-full" size="lg">
            Back to sign in <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>
    );
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
          placeholder="Your password"
          autoComplete={mode === "register" ? "new-password" : "current-password"}
        />
      </Field>
      {mode === "login" ? (
        <div className="flex justify-end">
          <Link href="/forgot-password" className="text-[11.5px] text-faint hover:text-flame-400">
            Forgot password?
          </Link>
        </div>
      ) : null}
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
