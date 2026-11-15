"use client";

import Link from "next/link";
import { Check, CreditCard, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { Alert, Badge, Button, PageSkeleton, Panel, PanelHeader } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { useSessionStore } from "@/lib/stores";
import { formatDuration } from "@/lib/format";

interface BillingData {
  plan: string;
  status: string;
  limits: { clips_per_month: number; render_minutes_per_month: number };
  usage: { clips_this_month: number; render_minutes_this_month: number };
  payment_provider: { available: boolean; message: string };
  invoices: unknown[];
}

export default function BillingPage() {
  const billing = useApi<BillingData>("/api/billing");
  const workspace = useSessionStore((state) =>
    state.workspaces.find((item) => item.id === state.activeWorkspaceId),
  );

  if (billing.loading && !billing.data) return <PageSkeleton />;
  if (!billing.data) {
    return (
      <div>
        <PageHeader title="Plan & usage" />
        <Alert>{billing.error}</Alert>
      </div>
    );
  }
  const data = billing.data;
  const clipPct = Math.min(100, (data.usage.clips_this_month / Math.max(1, data.limits.clips_per_month)) * 100);
  const renderPct = Math.min(100, (data.usage.render_minutes_this_month / Math.max(1, data.limits.render_minutes_per_month)) * 100);

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        eyebrow="Account"
        title="Plan & usage"
        description="Usage is computed from real pipeline records in this workspace. Billing itself is not connected to a payment provider yet."
        actions={<Badge tone="flame">{data.plan} · {data.status}</Badge>}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Panel className="p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] text-faint">Current plan</p>
              <p className="mt-1 text-[24px] font-semibold capitalize">{data.plan}</p>
            </div>
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-flame-500/12 text-flame-500">
              <Sparkles className="h-4 w-4" />
            </span>
          </div>
          <ul className="mt-4 space-y-2 text-[12px] text-muted">
            {[
              `${data.limits.clips_per_month} clips / month`,
              `${data.limits.render_minutes_per_month} render minutes / month`,
              "Unlimited team members",
              "Bring your own AI keys",
            ].map((item) => (
              <li key={item} className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-mint" /> {item}
              </li>
            ))}
          </ul>
          <p className="mt-4 text-[10.5px] leading-relaxed text-faint">
            Workspace created {workspace ? new Date(workspace.created_at).toLocaleDateString() : "-"}. Limits are
            enforced for rendering; contact the operator to change the plan.
          </p>
        </Panel>

        <Panel className="p-5">
          <p className="text-[12px] font-medium">This cycle</p>
          <div className="mt-4 space-y-4">
            <div>
              <div className="mb-1.5 flex justify-between text-[11.5px]">
                <span className="text-faint">Clips generated</span>
                <span className="font-mono text-muted">
                  {data.usage.clips_this_month} / {data.limits.clips_per_month}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/7">
                <div className="h-full rounded-full bg-flame-500" style={{ width: `${Math.max(1, clipPct)}%` }} />
              </div>
            </div>
            <div>
              <div className="mb-1.5 flex justify-between text-[11.5px]">
                <span className="text-faint">Render minutes</span>
                <span className="font-mono text-muted">
                  {data.usage.render_minutes_this_month.toFixed(1)} / {data.limits.render_minutes_per_month}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/7">
                <div className="h-1.5 rounded-full bg-ember" style={{ width: `${Math.max(1, renderPct)}%` }} />
              </div>
            </div>
            <p className="font-mono text-[10px] text-faint">
              render seconds this month ≈ {formatDuration(data.usage.render_minutes_this_month * 60)}
            </p>
          </div>
        </Panel>
      </div>

      <Panel className="mt-5">
        <PanelHeader title="Payment provider" description="Billing-ready architecture, not a fake checkout." />
        <div className="p-5">
          <Alert tone="info">{data.payment_provider.message}</Alert>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {[
              ["Plan field", "Workspace.plan + monthly limits are already stored."],
              ["Usage metering", "Render seconds, transcription seconds and AI units are recorded."],
              ["Next step", "Add Stripe (or equivalent) webhooks and map plans to workspaces."],
            ].map(([title, body]) => (
              <div key={title} className="rounded-lg border border-white/8 bg-ink-850/60 p-3">
                <p className="text-[11.5px] font-medium">{title}</p>
                <p className="mt-1 text-[10.5px] leading-relaxed text-faint">{body}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-white/8 pt-3">
            <span className="flex items-center gap-2 text-[11.5px] text-faint">
              <CreditCard className="h-4 w-4" /> Invoices
            </span>
            <span className="text-[11.5px] text-faint">No payment provider connected.</span>
          </div>
        </div>
      </Panel>

      <p className="mt-5 text-center text-[11px] text-faint">
        Need more render minutes? See{" "}
        <Link href="/docs" className="text-flame-400 hover:text-flame-500">deployment & limits</Link> or ask your
        workspace owner.
      </p>
    </div>
  );
}
