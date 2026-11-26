"use client";

import Link from "next/link";
import * as React from "react";
import { Clapperboard, Download, RefreshCw, X } from "lucide-react";
import { PageHeader, SectionHeader } from "@/components/shared";
import {
  Alert,
  Badge,
  Button,
  EmptyState,
  PageSkeleton,
  Panel,
  Progress,
  Tabs,
} from "@/components/ui";
import { JobStatusBadge } from "@/components/status";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatBytes, formatDuration, relativeTime } from "@/lib/format";
import type { Job, RenderJob } from "@/lib/types";

export default function RendersPage() {
  const renders = useApi<RenderJob[]>("/api/renders?limit=100", { pollMs: 2500 });
  const jobs = useApi<Job[]>("/api/jobs?limit=40", { pollMs: 3500 });
  const [tab, setTab] = React.useState("renders");
  const [busy, setBusy] = React.useState<string | null>(null);

  const items = renders.data || [];
  const active = items.filter((item) => ["queued", "running"].includes(item.status));

  async function cancel(render: RenderJob) {
    setBusy(render.id);
    try {
      await api.post(`/api/renders/${render.id}/cancel`);
      toast("Render cancelled", "info");
      renders.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function retry(render: RenderJob) {
    setBusy(render.id);
    try {
      await api.post(`/api/renders/${render.id}/retry`);
      toast("Render requeued", "success");
      renders.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <PageHeader        title="Render queue"
        description="Asynchronous FFmpeg jobs. Rendering never blocks the API; progress is recorded per job."
        actions={
          <Link href="/exports">
            <Button size="sm" variant="outline">
              <Download className="h-3.5 w-3.5" /> Export library
            </Button>
          </Link>
        }
      />

      {renders.error ? <Alert className="mb-4">{renders.error}</Alert> : null}

      <Panel>
        <div className="px-3 pt-1">
          <Tabs
            value={tab}
            onValueChange={setTab}
            tabs={[
              { value: "renders", label: "Renders", count: items.length },
              { value: "active", label: "Active", count: active.length },
              { value: "jobs", label: "Pipeline jobs", count: (jobs.data || []).length },
            ]}
          />
        </div>

        {tab === "jobs" ? (
          <div className="divide-y divide-paper/6">
            {(jobs.data || []).length === 0 ? (
              <EmptyState title="No pipeline jobs" description="Ingestion, transcription, analysis and render jobs appear here." />
            ) : (
              (jobs.data || []).map((job) => (
                <div key={job.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[12.5px] capitalize text-paper">{job.kind}</span>
                      <JobStatusBadge status={job.status} />
                    </div>
                    <p className="mt-0.5 font-mono text-[10px] text-faint">
                      {job.stage}, {relativeTime(job.created_at)} {job.video_id ? `, video ${job.video_id.slice(0, 6)}` : ""}
                    </p>
                    {job.error_message ? <p className="mt-1 text-[11px] text-rose">{job.error_message}</p> : null}
                  </div>
                  <div className="w-32">
                    <Progress value={job.progress} />
                  </div>
                </div>
              ))
            )}
          </div>
        ) : renders.loading && !renders.data ? (
          <div className="p-4"><PageSkeleton /></div>
        ) : (tab === "active" ? active : items).length === 0 ? (
          <EmptyState
            icon={<Clapperboard className="h-5 w-5" />}
            title={tab === "active" ? "No active renders" : "No renders yet"}
            description="Open a clip in the editor and render it to a platform preset to see it here."
            action={
              <Link href="/clips">
                <Button size="sm">Go to clips</Button>
              </Link>
            }
          />
        ) : (
          <div className="divide-y divide-paper/6">
            {(tab === "active" ? active : items).map((render) => (
              <div key={render.id} className="px-4 py-3.5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/editor/${render.editing_project_id}`}
                        className="truncate text-[13px] font-medium text-paper hover:text-flame-400"
                      >
                        {render.project_name || "Untitled clip"}
                      </Link>
                      <Badge tone={render.status === "completed" ? "mint" : render.status === "failed" ? "rose" : "flame"}>
                        {render.status}
                      </Badge>
                      <Badge tone="neutral">{render.preset}, {render.format}</Badge>
                    </div>
                    <p className="mt-1 truncate text-[11px] text-faint">
                      {render.video_title || "Source video"}, requested {relativeTime(render.created_at)}
                      {render.output_size_bytes ? `, ${formatBytes(render.output_size_bytes)}` : ""}
                      {render.render_seconds ? `, encoded in ${render.render_seconds.toFixed(1)}s` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {render.download_url ? (
                      <a href={render.download_url}>
                        <Button size="sm" variant="outline">
                          <Download className="h-3 w-3" /> Download
                        </Button>
                      </a>
                    ) : null}
                    {["queued", "running"].includes(render.status) ? (
                      <Button size="sm" variant="ghost" loading={busy === render.id} onClick={() => cancel(render)}>
                        <X className="h-3 w-3" /> Cancel
                      </Button>
                    ) : ["failed", "cancelled"].includes(render.status) ? (
                      <Button size="sm" variant="ghost" loading={busy === render.id} onClick={() => retry(render)}>
                        <RefreshCw className="h-3 w-3" /> Retry
                      </Button>
                    ) : null}
                  </div>
                </div>
                {["queued", "running"].includes(render.status) ? (
                  <div className="mt-2.5 max-w-xl">
                    <div className="mb-1 flex justify-between font-mono text-[10px] text-faint">
                      <span>{render.status === "queued" ? "waiting for a worker" : "encoding"}</span>
                      <span>{Math.round(render.progress)}%</span>
                    </div>
                    <Progress value={render.progress} />
                  </div>
                ) : null}
                {render.error_message ? (
                  <p className="mt-2 rounded-[var(--radius-control)] border border-rose/20 bg-rose/5 px-3 py-2 text-[11.5px] leading-relaxed text-rose">
                    {render.error_message}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="mt-8">
        <SectionHeader title="How rendering works" description="Transparent by design." />
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ["Worker process", "ARQ + Redis in production, in-process threads locally. The API only enqueues."],
            ["FFmpeg filter graph", "Crop → captions (ASS) → overlays → loudness → encode. Hardware NVENC is optional."],
            ["Output", "MP4 H.264/AAC, MOV or WebM VP9/Opus, stored under renders/ with a generated thumbnail."],
          ].map(([title, body]) => (
            <Panel key={title} className="p-4">
              <p className="text-[12px] font-medium">{title}</p>
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-faint">{body}</p>
            </Panel>
          ))}
        </div>
      </div>
    </div>
  );
}
