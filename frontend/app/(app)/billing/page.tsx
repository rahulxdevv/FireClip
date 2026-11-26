"use client";

import Link from "next/link";
import * as React from "react";
import { Check, CreditCard, ExternalLink, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { Alert, Badge, Button, PageSkeleton, Panel, PanelHeader } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast, useSessionStore } from "@/lib/stores";
import { formatBytes } from "@/lib/format";
import type { BillingOverview } from "@/lib/types";

export default function BillingPage() {
  const billing = useApi<BillingOverview>("/api/billing");
  const workspace = useSessionStore((state) =>
    state.workspaces.find((item) => item.id === state.activeWorkspaceId),
  );
  const [interval, setInterval] = React.useState<"month" | "year">("month");
  const [busy, setBusy] = React.useState<string | null>(null);

  async function checkout(planId: string) {
    setBusy(planId);
    try {
      const result = await api.post<{ url: string }>("/api/billing/checkout", {
        plan: planId,
        interval,
      });
      window.location.assign(result.url);
    } catch (err) {
      toast(errorMessage(err), "error");
      setBusy(null);
    }
  }

  async function openPortal() {
    setBusy("portal");
    try {
      const result = await api.post<{ url: string }>("/api/billing/portal");
      window.location.assign(result.url);
    } catch (err) {
      toast(errorMessage(err), "error");
      setBusy(null);
    }
  }

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
  const paid =
    data.plan !== "free" &&
    data.status === "active" &&
    (Boolean(data.renews_at) || data.invoices.length > 0);
  const isAdmin = workspace?.role === "owner" || workspace?.role === "admin";

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Plan & usage"
        description="Limits and usage here come from real pipeline records. Checkout only appears when a payment provider is configured on this instance."
        actions={
          <Badge tone="flame">
            {data.plan_name}, {data.status}
          </Badge>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Panel className="p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] text-faint">Current plan</p>
              <p className="mt-1 text-[24px] font-semibold">{data.plan_name}</p>
              <p className="mt-0.5 text-[11.5px] capitalize text-faint">
                {paid
                  ? data.interval + "ly billing" + (data.renews_at ? ", renews " + new Date(data.renews_at).toLocaleDateString() : "")
                  : data.payment_provider.available
                    ? "No active subscription"
                    : "Self-hosted, no payment provider connected"}
              </p>
            </div>
            <span className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-control)] bg-flame-500/12 text-flame-500">
              <Sparkles className="h-4 w-4" />
            </span>
          </div>
          <ul className="mt-4 space-y-2 text-[12px] text-muted">
            {[
              data.limits.clips_per_month.toLocaleString() + " clips / month",
              data.limits.render_minutes_per_month.toLocaleString() + " render minutes / month",
              "Unlimited team members",
              "Bring your own AI keys",
            ].map((item) => (
              <li key={item} className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 text-mint" /> {item}
              </li>
            ))}
          </ul>
          <div className="mt-4 flex flex-wrap gap-2">
            {paid && data.payment_provider.available && isAdmin ? (
              <Button size="sm" variant="outline" loading={busy === "portal"} onClick={openPortal}>
                <CreditCard className="h-3.5 w-3.5" /> Manage billing
              </Button>
            ) : null}
            <Link href="/workspace">
              <Button size="sm" variant="ghost">Workspace settings</Button>
            </Link>
          </div>
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
              <div className="h-1.5 overflow-hidden rounded-full bg-paper/7">
                <div className="h-full rounded-full bg-flame-500" style={{ width: Math.max(1, clipPct) + "%" }} />
              </div>
            </div>
            <div>
              <div className="mb-1.5 flex justify-between text-[11.5px]">
                <span className="text-faint">Render minutes</span>
                <span className="font-mono text-muted">
                  {data.usage.render_minutes_this_month.toFixed(1)} / {data.limits.render_minutes_per_month}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-paper/7">
                <div className="h-1.5 rounded-full bg-ember" style={{ width: Math.max(1, renderPct) + "%" }} />
              </div>
            </div>
            <div className="flex items-center justify-between border-t border-paper/7 pt-3 text-[11.5px]">
              <span className="text-faint">Storage used</span>
              <span className="font-mono text-muted">{formatBytes(data.usage.storage_bytes)}</span>
            </div>
          </div>
        </Panel>
      </div>

      <Panel className="mt-5">
        <PanelHeader
          title="Plans"
          description="Switch at any time. Existing work stays in the workspace."
          action={
            <div className="flex rounded-[var(--radius-control)] border border-paper/10 p-0.5">
              {(["month", "year"] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => setInterval(option)}
                  className={
                    "rounded-[var(--radius-control)] px-2.5 py-1 text-[11px] font-medium capitalize " +
                    (interval === option ? "bg-flame-500 text-seed" : "text-faint hover:text-paper")
                  }
                >
                  {option}ly
                </button>
              ))}
            </div>
          }
        />
        <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-4">
          {data.plans.map((plan) => {
            const current = plan.id === data.plan;
            const price = interval === "month" ? plan.monthly : plan.yearly;
            return (
              <div
                key={plan.id}
                className={
                  "flex flex-col rounded-[var(--radius-card)] border p-4 " +
                  (current ? "border-flame-500/40 bg-flame-500/6" : "border-paper/8 bg-ink-850/40")
                }
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-[13px] font-semibold">{plan.name}</p>
                    <p className="mt-0.5 text-[10.5px] leading-relaxed text-faint">{plan.tagline}</p>
                  </div>
                  {current ? <Badge tone="flame">current</Badge> : null}
                </div>
                <p className="mt-4 font-mono text-[24px] font-semibold">
                  {price === 0 ? "Free" : "$" + price}
                  {price !== 0 ? <span className="text-[11px] font-normal text-faint">/{interval}</span> : null}
                </p>
                <ul className="mt-3 flex-1 space-y-1.5 text-[11px] text-muted">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-1.5">
                      <Check className="mt-0.5 h-3 w-3 shrink-0 text-mint" /> {feature}
                    </li>
                  ))}
                </ul>
                <Button
                  size="sm"
                  variant={current ? "ghost" : "outline"}
                  className="mt-4 w-full"
                  disabled={current || plan.id === "free" || !data.payment_provider.available || !isAdmin}
                  loading={busy === plan.id}
                  onClick={() => checkout(plan.id)}
                >
                  {current ? "Current plan" : plan.id === "free" ? "Included" : "Choose " + plan.name}
                </Button>
              </div>
            );
          })}
        </div>
      </Panel>

      <Panel className="mt-5">
        <PanelHeader title="Payment provider" description="Configured by the instance operator." />
        <div className="space-y-4 p-5">
          <Alert tone={data.payment_provider.available ? "success" : "info"}>
            {data.payment_provider.message}
          </Alert>
          {data.payment_provider.available ? (
            <p className="text-[11px] text-faint">
              Checkout and invoices are handled by {data.payment_provider.provider}. Card data never touches this
              server.
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                ["Plan limits", "Stored on the workspace and enforced during analysis and rendering."],
                ["Usage metering", "Render seconds, transcription seconds and AI units are recorded."],
                ["Enable checkout", "Set the provider keys and price IDs in the backend environment."],
              ].map(([title, body]) => (
                <div key={title} className="rounded-[var(--radius-control)] border border-paper/8 bg-ink-850/60 p-3">
                  <p className="text-[11.5px] font-medium">{title}</p>
                  <p className="mt-1 text-[10.5px] leading-relaxed text-faint">{body}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </Panel>

      <Panel className="mt-5">
        <PanelHeader
          title="Invoices"
          description="Synced from the payment provider when webhooks are configured."
          action={<CreditCard className="h-4 w-4 text-faint" />}
        />
        {data.invoices.length === 0 ? (
          <p className="px-5 py-6 text-[12px] text-faint">No invoices yet.</p>
        ) : (
          <div className="divide-y divide-paper/6">
            {data.invoices.map((invoice) => (
              <div key={invoice.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[12.5px]">{invoice.number || invoice.id}</p>
                  <p className="font-mono text-[10px] text-faint">
                    {new Date(invoice.created_at).toLocaleDateString()}, {invoice.status}
                  </p>
                </div>
                <span className="font-mono text-[12px]">
                  {(invoice.amount_cents / 100).toFixed(2)} {invoice.currency.toUpperCase()}
                </span>
                {invoice.hosted_url ? (
                  <a href={invoice.hosted_url} target="_blank" rel="noreferrer">
                    <Button size="sm" variant="ghost">
                      View <ExternalLink className="h-3 w-3" />
                    </Button>
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </Panel>

      <p className="mt-5 text-center text-[11px] text-faint">
        Limits are enforced locally.{" "}
        <Link href="/docs" className="text-flame-400 hover:text-flame-500">
          Deployment & limits
        </Link>
      </p>
    </div>
  );
}
