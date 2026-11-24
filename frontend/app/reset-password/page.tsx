"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { ArrowLeft, KeyRound } from "lucide-react";
import { AuthLayout } from "@/components/auth-form";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

function ResetForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [done, setDone] = React.useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/api/auth/reset-password", { token, new_password: password });
      setDone(true);
      window.setTimeout(() => router.replace("/login"), 1500);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <AuthLayout
        title="Reset link missing"
        subtitle="This page needs a valid reset token."
        footer={<Link href="/forgot-password" className="text-flame-400">Request a new link</Link>}
      >
        <Alert>Open the link from your reset email, or request a fresh one.</Alert>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title={done ? "Password updated" : "Choose a new password"}
      subtitle={done ? "Redirecting you to the sign-in page." : "Use at least eight characters with letters and numbers."}
      footer={
        <Link href="/login" className="inline-flex items-center gap-1.5 text-flame-400 hover:text-flame-500">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to sign in
        </Link>
      }
    >
      {done ? (
        <Alert tone="success">Your password was changed. All reset links are now spent.</Alert>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="New password">
            <Input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
            />
          </Field>
          <Field label="Confirm new password">
            <Input
              type="password"
              required
              minLength={8}
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              autoComplete="new-password"
            />
          </Field>
          {error ? <Alert>{error}</Alert> : null}
          <Button type="submit" className="w-full" size="lg" loading={submitting}>
            <KeyRound className="h-4 w-4" /> Save new password
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}

export default function ResetPasswordPage() {
  return (
    <React.Suspense fallback={null}>
      <ResetForm />
    </React.Suspense>
  );
}
