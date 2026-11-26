"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { BadgeCheck, Loader2 } from "lucide-react";
import { AuthLayout } from "@/components/auth-form";
import { Alert, Button } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";

function VerifyInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [state, setState] = React.useState<"working" | "done" | "error">("working");
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!token) {
      setState("error");
      setError("This link is missing its verification token.");
      return;
    }
    let active = true;
    (async () => {
      try {
        await api.post("/api/auth/verify-email", { token });
        if (!active) return;
        setState("done");
        toast("Email confirmed", "success");
      } catch (err) {
        if (!active) return;
        setState("error");
        setError(errorMessage(err));
      }
    })();
    return () => {
      active = false;
    };
  }, [token]);

  return (
    <AuthLayout
      title={state === "done" ? "Email confirmed" : state === "error" ? "Could not confirm" : "Confirming your email"}
      subtitle={
        state === "done"
          ? "Your account is verified. You can close this tab or continue to your workspace."
          : "Verification links are single-use and expire."
      }
      footer={<Link href="/login" className="text-flame-400 hover:text-flame-500">Go to sign in</Link>}
    >
      {state === "working" ? (
        <div className="flex items-center gap-3 rounded-[var(--radius-control)] border border-paper/10 bg-paper/4 px-4 py-5 text-[13px] text-muted">
          <Loader2 className="h-4 w-4 animate-spin text-flame-500" /> Checking your link…
        </div>
      ) : state === "done" ? (
        <div className="space-y-4">
          <Alert tone="success" title="Verified">
            Your email address is now attached to this account.
          </Alert>
          <Button className="w-full" onClick={() => router.push("/dashboard")}>
            <BadgeCheck className="h-4 w-4" /> Continue
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <Alert>{error}</Alert>
          <Link href="/login">
            <Button variant="outline" className="w-full">Return to sign in</Button>
          </Link>
        </div>
      )}
    </AuthLayout>
  );
}

export default function VerifyEmailPage() {
  return (
    <React.Suspense fallback={null}>
      <VerifyInner />
    </React.Suspense>
  );
}
