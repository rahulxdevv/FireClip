"use client";

import Link from "next/link";
import {
  ArrowRight,
  CalendarClock,
  Download,
  Film,
  Flame,
  Link2,
  Plus,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { InlineProgress } from "@/components/shared";
import { Alert, Badge, Button, PageSkeleton, Panel, PanelHeader } from "@/components/ui";
import { JobStatusBadge } from "@/components/status";
import { useApi } from "@/lib/hooks";
import { useSessionStore } from "@/lib/stores";
import { formatDuration, relativeTime, scoreTone } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

const CLIP_TONE: Record<string, "mint" | "rose" | "neutral"> = {
  approved: "mint",
  rejected: "rose",
  suggested: "neutral",
};

export default function DashboardPage() {
  const { data, error, loading } = useApi<Dashboard>("/api/dashboard", { pollMs: 5000 });
  const user = useSessionStore((state) => state.user);
  const workspace = useSessionStore((state) =>
    state.workspaces.find((item) => item.id === state.activeWorkspaceId),
  );
  const firstName = (user?.name || user?.email || "there").trim().split(/\s+/)[0].split("@")[0];

  if (loading && !data) return <PageSkeleton />;
  if (error && !data) return <Alert title="Could not load the dashboard">{error}</Alert>;
  if (!data) return <PageSkeleton />;

  const { counts, usage } = data;
  const hasVideos = counts.videos > 0;
  const renderMinutes = usage.render_seconds / 60;
  const clipLimit = workspace?.monthly_clip_limit ?? 500;
  const renderLimit = workspace?.monthly_render_minutes ?? 600;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="min-w-0 truncate text-[26px] font-semibold leading-tight tracking-[-0.035em] text-paper">
          Welcome back, {firstName}
        </h1>
        <div className="flex shrink-0 items-center gap-2">
          <Link href="/import">
            <Button variant="outline" size="sm">
              <Link2 className="h-3.5 w-3.5" />
              Import
            </Button>
          </Link>
          <Link href="/upload">
            <Button size="sm">
              <Plus className="h-3.5 w-3.5" />
              New video
            </Button>
          </Link>
        </div>
      </header>

      {!hasVideos ? (
        <Panel className="flex flex-wrap items-center justify-between gap-4 p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-flame-500/12 text-flame-400">
              <Sparkles className="h-4 w-4" />
            </span>
            <p className="text-[13px] font-medium text-paper">Start with one recording.</p>
          </div>
          <Link href="/upload">
            <Button size="sm">
              <UploadCloud className="h-3.5 w-3.5" />
              Upload footage
            </Button>
          </Link>
        </Panel>
      ) : null}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Metric icon={Film} label="Source videos" value={counts.videos} href="/videos" />
        <Metric icon={Flame} label="Clips" value={counts.clips} href="/clips" />
        <Metric icon={Sparkles} label="In pipeline" value={counts.processing} href="/renders" />
        <Metric icon={CalendarClock} label="Published" value={counts.published} href="/schedule" />
      </div>

      <div className="grid gap-3 xl:grid-cols-[1.6fr_1fr]">
        <div className="min-w-0 space-y-3">
          <Panel>
            <PanelHeader
              title="Top clips"
              action={
                <Link href="/clips" className="text-[12px] font-medium text-flame-400 hover:text-flame-300">
                  Review all
                </Link>
              }
            />
            {data.recent_clips.length === 0 ? (
              <p className="px-5 py-9 text-center text-[12.5px] text-faint">
                No clips yet.
              </p>
            ) : (
              <div className="divide-y divide-white/[0.05]">
                {data.recent_clips.map((clip) => (
                  <Link
                    key={clip.id}
                    href={"/clips?highlight=" + clip.id}
                    className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-white/[0.025]"
                  >
                    <span
                      className={
                        "flex h-8 w-9 shrink-0 items-center justify-center rounded-[8px] bg-white/[0.05] font-mono text-[12.5px] font-semibold tabular-nums " +
                        scoreTone(clip.virality_score)
                      }
                    >
                      {Math.round(clip.virality_score)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[12.5px] font-medium text-paper">{clip.title}</span>
                      <span className="mt-0.5 block truncate text-[11px] text-faint">
                        {clip.video_title}, {formatDuration(clip.duration_ms, true)}
                      </span>
                    </span>
                    <Badge tone={CLIP_TONE[clip.status] || "neutral"}>{clip.status}</Badge>
                  </Link>
                ))}
              </div>
            )}
          </Panel>

          <Panel>
            <PanelHeader
              title="Recent videos"
              action={
                <Link href="/videos" className="text-[12px] font-medium text-flame-400 hover:text-flame-300">
                  Library
                </Link>
              }
            />
            {data.recent_videos.length === 0 ? (
              <p className="px-5 py-9 text-center text-[12.5px] text-faint">No videos yet.</p>
            ) : (
              <div className="divide-y divide-white/[0.05]">
                {data.recent_videos.slice(0, 5).map((video) => (
                  <Link
                    key={video.id}
                    href={"/videos/" + video.id}
                    className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-white/[0.025]"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] bg-white/[0.05] text-faint">
                      <Film className="h-3.5 w-3.5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[12.5px] font-medium text-paper">{video.title}</span>
                      <span className="mt-0.5 block truncate text-[11px] text-faint">
                        {formatDuration(video.duration_seconds)}, {relativeTime(video.created_at)}
                      </span>
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-ink-500" />
                  </Link>
                ))}
              </div>
            )}
          </Panel>
        </div>

        <div className="min-w-0 space-y-3">
          <Panel>
            <PanelHeader title="Pipeline" />
            {data.processing.length === 0 ? (
              <p className="px-5 py-6 text-[12.5px] text-faint">Queue is idle.</p>
            ) : (
              <div className="divide-y divide-white/[0.05]">
                {data.processing.map((job) => (
                  <Link
                    key={job.id}
                    href={job.video_id ? "/videos/" + job.video_id : "/renders"}
                    className="block px-5 py-3 transition-colors hover:bg-white/[0.025]"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <JobStatusBadge status={job.status} />
                      <span className="text-[11px] text-faint">{relativeTime(job.created_at)}</span>
                    </div>
                    <div className="mt-2">
                      <InlineProgress value={job.progress} label={job.stage || job.kind} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Panel>

          <Panel>
            <PanelHeader
              title="Usage"
              action={
                <Link href="/billing" className="text-[12px] font-medium text-flame-400 hover:text-flame-300">
                  Plan
                </Link>
              }
            />
            <div className="space-y-4 px-5 py-4">
              <UsageBar
                label="Render minutes"
                value={renderMinutes}
                limit={renderLimit}
                format={(value) => String(Math.round(value))}
              />
              <UsageBar
                label="Clips"
                value={counts.clips}
                limit={clipLimit}
                format={(value) => String(Math.round(value))}
              />
              <div className="flex items-center justify-between border-t border-white/[0.05] pt-3 text-[11.5px]">
                <span className="text-faint">Audio transcribed</span>
                <span className="tabular-nums text-muted">{formatDuration(usage.transcription_seconds)}</span>
              </div>
            </div>
          </Panel>

          {data.renders.length > 0 ? (
            <Panel>
              <PanelHeader
                title="Renders"
                action={
                  <Link href="/renders" className="text-[12px] font-medium text-flame-400 hover:text-flame-300">
                    Queue
                  </Link>
                }
              />
              <div className="divide-y divide-white/[0.05]">
                {data.renders.slice(0, 4).map((render) => (
                  <div key={render.id} className="flex items-center gap-3 px-5 py-2.5">
                    <Download className="h-3.5 w-3.5 shrink-0 text-ink-500" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] text-paper">{render.project_name || render.preset}</p>
                      <p className="text-[10.5px] text-faint">
                        {render.format}, {relativeTime(render.created_at)}
                      </p>
                    </div>
                    <JobStatusBadge status={render.status} />
                  </div>
                ))}
              </div>
            </Panel>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  href,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  href: string;
}) {
  return (
    <Link href={href} className="panel panel-hover group block p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] text-muted">{label}</span>
        <Icon className="h-3.5 w-3.5 text-ink-500 transition-colors group-hover:text-flame-400" />
      </div>
      <p className="mt-3 text-[28px] font-semibold leading-none tracking-[-0.03em] tabular-nums text-paper">
        {value}
      </p>
    </Link>
  );
}

function UsageBar({
  label,
  value,
  limit,
  format,
}: {
  label: string;
  value: number;
  limit: number;
  format: (value: number) => string;
}) {
  const pct = limit > 0 ? Math.min(100, (value / limit) * 100) : 0;
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-[11.5px]">
        <span className="text-faint">{label}</span>
        <span className="tabular-nums text-muted">
          {format(value)} / {format(limit)}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.07]">
        <div className="h-full rounded-full bg-flame-500" style={{ width: pct + "%" }} />
      </div>
    </div>
  );
}
