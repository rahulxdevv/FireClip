"use client";

import Link from "next/link";
import * as React from "react";
import { ArrowLeft, MailCheck } from "lucide-react";
import { AuthLayout } from "@/components/auth-form";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [sent, setSent] = React.useState<{ message: string; dev_link?: string | null } | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.post<{ status: string; message: string; dev_link?: string | null }>(
        "/api/auth/forgot-password",
        { email },
      );
      setSent(result);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="Enter the email on your account. If it exists, we will send a single-use reset link."
      footer={
        <Link href="/login" className="inline-flex items-center gap-1.5 text-flame-400 hover:text-flame-500">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to sign in
        </Link>
      }
    >
      {sent ? (
        <div className="space-y-4">
          <Alert tone="success" title="Check your inbox">
            {sent.message}
          </Alert>
          {sent.dev_link ? (
            <Alert tone="info" title="Development link">
              Email is not configured on this instance, so here is the reset link directly:{" "}
              <a href={sent.dev_link} className="break-all font-mono text-flame-400">
                {sent.dev_link}
              </a>
            </Alert>
          ) : null}
          <Button variant="outline" className="w-full" onClick={() => setSent(null)}>
            Use a different email
          </Button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email">
            <Input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@studio.com"
              autoComplete="email"
            />
          </Field>
          {error ? <Alert>{error}</Alert> : null}
          <Button type="submit" className="w-full" size="lg" loading={submitting}>
            <MailCheck className="h-4 w-4" /> Send reset link
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
