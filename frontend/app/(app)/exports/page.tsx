"use client";

import Link from "next/link";
import * as React from "react";
import { Download, Film, Send, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/shared";
import {
  Alert,
  Badge,
  Button,
  EmptyState,
  PageSkeleton,
  Panel,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatBytes, formatDuration, relativeTime } from "@/lib/format";
import type { ExportItem } from "@/lib/types";

export default function ExportsPage() {
  const exports = useApi<ExportItem[]>("/api/exports?limit=200");
  const [busy, setBusy] = React.useState<string | null>(null);

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
                  <Link href={`/publish?export=${item.id}`}>
                    <Button size="sm" variant="secondary">
                      <Send className="h-3 w-3" /> Publish
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
    </div>
  );
}
