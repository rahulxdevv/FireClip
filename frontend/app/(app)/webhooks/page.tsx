"use client";

import * as React from "react";
import { Copy, Plus, Send, Trash2, Webhook } from "lucide-react";
import { PageHeader } from "@/components/shared";
import {
  Alert,
  Badge,
  Button,
  Dialog,
  EmptyState,
  Field,
  Input,
  PageSkeleton,
  Panel,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast, useSessionStore } from "@/lib/stores";
import { relativeTime } from "@/lib/format";
import type { WebhookDelivery, WebhookEndpoint } from "@/lib/types";

interface WebhookList {
  events: string[];
  endpoints: WebhookEndpoint[];
}

export default function WebhooksPage() {
  const hooks = useApi<WebhookList>("/api/webhooks");
  const workspace = useSessionStore((state) =>
    state.workspaces.find((item) => item.id === state.activeWorkspaceId),
  );
  const [createOpen, setCreateOpen] = React.useState(false);
  const [form, setForm] = React.useState({ url: "", description: "", events: ["*"] as string[] });
  const [creating, setCreating] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [deliveriesFor, setDeliveriesFor] = React.useState<WebhookEndpoint | null>(null);
  const [deliveries, setDeliveries] = React.useState<WebhookDelivery[]>([]);
  const [deliveriesLoading, setDeliveriesLoading] = React.useState(false);
  const isAdmin = workspace?.role === "owner" || workspace?.role === "admin";

  const availableEvents = hooks.data?.events || [];

  function toggleEvent(event: string) {
    setForm((current) => {
      if (event === "*") return { ...current, events: ["*"] };
      const withoutAll = current.events.filter((item) => item !== "*");
      const next = withoutAll.includes(event)
        ? withoutAll.filter((item) => item !== event)
        : [...withoutAll, event];
      return { ...current, events: next.length ? next : ["*"] };
    });
  }

  async function createWebhook(event: React.FormEvent) {
    event.preventDefault();
    setCreating(true);
    try {
      await api.post<WebhookEndpoint>("/api/webhooks", {
        url: form.url,
        description: form.description,
        events: form.events,
      });
      toast("Webhook endpoint created", "success");
      setCreateOpen(false);
      setForm({ url: "", description: "", events: ["*"] });
      hooks.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setCreating(false);
    }
  }

  async function toggleEndpoint(endpoint: WebhookEndpoint) {
    setBusy(endpoint.id);
    try {
      await api.patch<WebhookEndpoint>("/api/webhooks/" + endpoint.id, { enabled: !endpoint.enabled });
      hooks.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function testEndpoint(endpoint: WebhookEndpoint) {
    setBusy(endpoint.id);
    try {
      const result = await api.post<{ ok: boolean; status_code: number; error: string }>(
        "/api/webhooks/" + endpoint.id + "/test",
      );
      toast(
        result.ok ? "Test delivered (" + result.status_code + ")" : "Endpoint returned " + (result.status_code || "no response"),
        result.ok ? "success" : "error",
      );
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function openDeliveries(endpoint: WebhookEndpoint) {
    setDeliveriesFor(endpoint);
    setDeliveries([]);
    setDeliveriesLoading(true);
    try {
      const rows = await api.get<WebhookDelivery[]>(
        "/api/webhooks/" + endpoint.id + "/deliveries?limit=25",
      );
      setDeliveries(rows);
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setDeliveriesLoading(false);
    }
  }

  async function removeEndpoint(endpoint: WebhookEndpoint) {
    if (!window.confirm("Delete this webhook endpoint? Delivery history is removed too.")) return;
    setBusy(endpoint.id);
    try {
      await api.delete("/api/webhooks/" + endpoint.id);
      toast("Webhook deleted", "success");
      hooks.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        eyebrow="Settings"
        title="Webhooks"
        description="Send signed events to your own service when clips are approved, rendered, published or shared."
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)} disabled={!isAdmin}>
            <Plus className="h-3.5 w-3.5" /> Add endpoint
          </Button>
        }
      />

      <Alert tone="info" className="mb-4">
        Requests are signed with HMAC-SHA256 in <span className="font-mono">X-FireClip-Signature</span> using the
        endpoint secret. Delivery is asynchronous; inspect the log per endpoint to debug failures.
        Private network addresses are rejected.
      </Alert>

      {hooks.error ? <Alert className="mb-4">{hooks.error}</Alert> : null}

      {hooks.loading && !hooks.data ? (
        <PageSkeleton />
      ) : (hooks.data?.endpoints || []).length === 0 ? (
        <Panel>
          <EmptyState
            icon={<Webhook className="h-5 w-5" />}
            title="No webhook endpoints"
            description="Add one to receive clip and publishing events in your automation stack."
            action={
              <Button size="sm" onClick={() => setCreateOpen(true)} disabled={!isAdmin}>
                Add endpoint
              </Button>
            }
          />
        </Panel>
      ) : (
        <div className="space-y-3">
          {(hooks.data?.endpoints || []).map((endpoint) => (
            <Panel key={endpoint.id} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="break-all font-mono text-[12px] text-paper">{endpoint.url}</p>
                    <Badge tone={endpoint.enabled ? "mint" : "neutral"}>
                      {endpoint.enabled ? "enabled" : "disabled"}
                    </Badge>
                  </div>
                  <p className="mt-1 text-[11px] text-faint">
                    {endpoint.description || "No description"} · created {relativeTime(endpoint.created_at)}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {endpoint.events.map((event) => (
                      <span key={event} className="rounded border border-white/8 bg-ink-850 px-1.5 py-0.5 font-mono text-[9.5px] text-muted">
                        {event}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Button size="sm" variant="ghost" loading={busy === endpoint.id} onClick={() => testEndpoint(endpoint)}>
                    <Send className="h-3 w-3" /> Test
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => openDeliveries(endpoint)}>
                    Deliveries
                  </Button>
                  <Button size="sm" variant="ghost" loading={busy === endpoint.id} onClick={() => toggleEndpoint(endpoint)}>
                    {endpoint.enabled ? "Disable" : "Enable"}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => removeEndpoint(endpoint)} aria-label="Delete endpoint">
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-white/7 pt-3">
                <span className="text-[10.5px] text-faint">Signing secret</span>
                <code className="min-w-0 flex-1 truncate rounded bg-ink-950 px-2 py-1 font-mono text-[10px] text-muted">
                  {endpoint.secret}
                </code>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    await navigator.clipboard.writeText(endpoint.secret);
                    toast("Secret copied", "success");
                  }}
                >
                  <Copy className="h-3 w-3" />
                </Button>
              </div>
            </Panel>
          ))}
        </div>
      )}

      <Dialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="Add webhook endpoint"
        description="HTTPS endpoints on public hosts only. A signing secret is generated for you."
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={createWebhook} loading={creating} disabled={!form.url.trim()}>
              Add endpoint
            </Button>
          </>
        }
      >
        <form onSubmit={createWebhook} className="space-y-4">
          <Field label="Endpoint URL" hint="Must be reachable from this server over HTTPS.">
            <Input
              type="url"
              required
              value={form.url}
              onChange={(event) => setForm({ ...form, url: event.target.value })}
              placeholder="https://hooks.example.com/fireclip"
            />
          </Field>
          <Field label="Description">
            <Input
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              placeholder="Zapier automation"
              maxLength={160}
            />
          </Field>
          <div>
            <p className="mb-2 text-[13px] font-medium text-muted">Events</p>
            <div className="grid gap-1.5 sm:grid-cols-2">
              <label className="flex items-center gap-2 rounded border border-white/8 px-2.5 py-1.5 text-[11.5px]">
                <input
                  type="checkbox"
                  checked={form.events.includes("*")}
                  onChange={() => toggleEvent("*")}
                  className="accent-flame-500"
                />
                All events
              </label>
              {availableEvents.map((event) => (
                <label key={event} className="flex items-center gap-2 rounded border border-white/8 px-2.5 py-1.5 text-[11.5px]">
                  <input
                    type="checkbox"
                    checked={form.events.includes(event)}
                    onChange={() => toggleEvent(event)}
                    className="accent-flame-500"
                  />
                  {event}
                </label>
              ))}
            </div>
          </div>
        </form>
      </Dialog>

      <Dialog
        open={Boolean(deliveriesFor)}
        onOpenChange={(open) => { if (!open) setDeliveriesFor(null); }}
        title="Recent deliveries"
        description={deliveriesFor?.url}
        wide
      >
        {deliveriesLoading ? (
          <PageSkeleton />
        ) : deliveries.length === 0 ? (
          <p className="rounded-lg border border-white/8 bg-ink-850/50 px-3 py-4 text-[12px] text-faint">
            No deliveries recorded yet. Use Test to send one now.
          </p>
        ) : (
          <div className="divide-y divide-white/6 rounded-lg border border-white/8">
            {deliveries.map((delivery) => (
              <div key={delivery.id} className="flex flex-wrap items-center gap-2 px-3 py-2.5">
                <Badge tone={delivery.ok ? "mint" : "rose"}>{delivery.status_code || "error"}</Badge>
                <span className="min-w-0 flex-1 font-mono text-[11px] text-muted">{delivery.event}</span>
                <span className="font-mono text-[10px] text-faint">{delivery.duration_ms}ms · {relativeTime(delivery.created_at)}</span>
                {delivery.error ? (
                  <p className="w-full break-words text-[10.5px] text-rose">{delivery.error}</p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </Dialog>
    </div>
  );
}
