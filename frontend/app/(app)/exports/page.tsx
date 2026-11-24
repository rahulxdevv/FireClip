"use client";

import Link from "next/link";
import * as React from "react";
import { Copy, Download, Film, Link2, Send, Share2, Trash2 } from "lucide-react";
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
  Select,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatBytes, formatDuration, relativeTime } from "@/lib/format";
import type { ExportItem, ShareLink } from "@/lib/types";

export default function ExportsPage() {
  const exports = useApi<ExportItem[]>("/api/exports?limit=200");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [shareFor, setShareFor] = React.useState<ExportItem | null>(null);
  const [shares, setShares] = React.useState<ShareLink[]>([]);
  const [sharesLoading, setSharesLoading] = React.useState(false);
  const [shareForm, setShareForm] = React.useState({ expires: "30", password: "" });
  const [creatingShare, setCreatingShare] = React.useState(false);
  const [shareError, setShareError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!shareFor) return;
    let active = true;
    setSharesLoading(true);
    setShareError(null);
    api
      .get<ShareLink[]>(`/api/exports/${shareFor.id}/shares`)
      .then((rows) => {
        if (active) setShares(rows);
      })
      .catch((err) => {
        if (active) setShareError(errorMessage(err));
      })
      .finally(() => {
        if (active) setSharesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [shareFor]);

  async function createShare(event: React.FormEvent) {
    event.preventDefault();
    if (!shareFor) return;
    setCreatingShare(true);
    setShareError(null);
    try {
      const created = await api.post<ShareLink>(`/api/exports/${shareFor.id}/shares`, {
        expires_in_days: shareForm.expires === "never" ? null : Number(shareForm.expires),
        password: shareForm.password || null,
      });
      setShares((current) => [created, ...current]);
      setShareForm({ expires: "30", password: "" });
      await navigator.clipboard.writeText(created.url).catch(() => undefined);
      toast("Share link created and copied", "success");
    } catch (err) {
      setShareError(errorMessage(err));
    } finally {
      setCreatingShare(false);
    }
  }

  async function revokeShare(share: ShareLink) {
    if (!window.confirm("Revoke this share link? Existing viewers will lose access immediately.")) return;
    try {
      await api.delete(`/api/shares/${share.id}`);
      setShares((current) => current.filter((item) => item.id !== share.id));
      toast("Share link revoked", "success");
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  async function remove(exportItem: ExportItem) {
    if (!window.confirm(`Delete “${exportItem.filename}”? Published posts keep working if already uploaded.`)) return;
    setBusy(exportItem.id);
    try {
      await api.delete(`/api/exports/${exportItem.id}`);
      toast("Export deleted", "success");
      exports.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Create"
        title="Exports"
        description="Every file FFmpeg has produced for this workspace, with its real dimensions and duration."
        actions={
          <Link href="/renders">
            <Button size="sm" variant="outline">Render queue</Button>
          </Link>
        }
      />

      {exports.error ? <Alert className="mb-4">{exports.error}</Alert> : null}

      {exports.loading && !exports.data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <PageSkeleton /><PageSkeleton /><PageSkeleton />
        </div>
      ) : (exports.data || []).length === 0 ? (
        <Panel>
          <EmptyState
            icon={<Film className="h-5 w-5" />}
            title="No exports yet"
            description="Render a clip from the editor to produce a downloadable file here."
            action={
              <Link href="/clips">
                <Button size="sm">Review clips</Button>
              </Link>
            }
          />
        </Panel>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(exports.data || []).map((item) => (
            <Panel key={item.id} className="overflow-hidden">
              <div className="relative aspect-[9/16] max-h-[320px] overflow-hidden bg-ink-850">
                {item.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={item.thumbnail_url} alt="" className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full items-center justify-center text-ink-600">
                    <Film className="h-7 w-7" />
                  </div>
                )}
                <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/80 to-transparent p-3 text-[10px]">
                  <span className="font-mono">{item.width}×{item.height}</span>
                  <span className="font-mono">{formatDuration(item.duration_ms, true)}</span>
                </div>
                <span className="absolute right-2 top-2">
                  <Badge tone="neutral">{item.format.toUpperCase()}</Badge>
                </span>
              </div>
              <div className="p-3.5">
                <p className="truncate text-[13px] font-medium">{item.title || item.filename}</p>
                <p className="mt-0.5 text-[11px] text-faint">
                  {formatBytes(item.size_bytes)} · {relativeTime(item.created_at)}
                </p>
                <div className="mt-3 flex items-center gap-1.5">
                  <a href={item.download_url} className="flex-1">
                    <Button size="sm" variant="outline" className="w-full">
                      <Download className="h-3 w-3" /> Download
                    </Button>
                  </a>
                  <Button size="sm" variant="secondary" onClick={() => { setShares([]); setShareFor(item); }}>
                    <Share2 className="h-3 w-3" /> Share
                  </Button>
                  <Link href={`/publish?export=${item.id}`}>
                    <Button size="sm" variant="ghost" aria-label="Publish">
                      <Send className="h-3 w-3" />
                    </Button>
                  </Link>
                  <Button
                    size="sm"
                    variant="ghost"
                    loading={busy === item.id}
                    onClick={() => remove(item)}
                    aria-label="Delete export"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            </Panel>
          ))}
        </div>
      )}

      <Dialog
        open={Boolean(shareFor)}
        onOpenChange={(open) => { if (!open) setShareFor(null); }}
        title="Share this export"
        description="Create a public page for this clip. Password protection and expiry are optional."
        wide
      >
        <div className="space-y-5">
          <form onSubmit={createShare} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
            <Field label="Expires">
              <Select
                value={shareForm.expires}
                onChange={(event) => setShareForm({ ...shareForm, expires: event.target.value })}
              >
                <option value="7">In 7 days</option>
                <option value="30">In 30 days</option>
                <option value="90">In 90 days</option>
                <option value="never">Never</option>
              </Select>
            </Field>
            <Field label="Password" hint="Leave blank for anyone with the link.">
              <Input
                value={shareForm.password}
                onChange={(event) => setShareForm({ ...shareForm, password: event.target.value })}
                placeholder="Optional"
              />
            </Field>
            <Button type="submit" loading={creatingShare}>
              <Link2 className="h-3.5 w-3.5" /> Create link
            </Button>
          </form>

          {shareError ? <Alert>{shareError}</Alert> : null}

          <div>
            <p className="label-caps mb-2">Active links</p>
            {sharesLoading ? (
              <PageSkeleton />
            ) : shares.length === 0 ? (
              <p className="rounded-lg border border-white/8 bg-ink-850/50 px-3 py-4 text-[12px] text-faint">
                No active links for this export yet.
              </p>
            ) : (
              <div className="space-y-2">
                {shares.map((share) => (
                  <div key={share.id} className="rounded-lg border border-white/8 bg-ink-850/50 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="min-w-0 flex-1 break-all font-mono text-[10.5px] text-muted">{share.url}</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={async () => {
                          await navigator.clipboard.writeText(share.url);
                          toast("Link copied", "success");
                        }}
                        aria-label="Copy link"
                      >
                        <Copy className="h-3 w-3" /> Copy
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => revokeShare(share)}>
                        Revoke
                      </Button>
                    </div>
                    <p className="mt-1.5 font-mono text-[10px] text-faint">
                      {share.has_password ? "password protected · " : "public · "}
                      {share.expires_at ? `expires ${new Date(share.expires_at).toLocaleDateString()} · ` : "no expiry · "}
                      {share.view_count} {share.view_count === 1 ? "view" : "views"}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </Dialog>
    </div>
  );
}
