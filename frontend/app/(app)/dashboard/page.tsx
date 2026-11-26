"use client";

import Link from "next/link";
import {
  ArrowRight,
  CalendarClock,
  Clapperboard,
  Download,
  Film,
  Flame,
  Plus,
  Radio,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { PageHeader, StatCard, SectionHeader, InlineProgress } from "@/components/shared";
import { VideoCard } from "@/components/video-card";
import { Alert, Badge, Button, EmptyState, PageSkeleton, Panel, PanelHeader } from "@/components/ui";
import { JobStatusBadge } from "@/components/status";
import { useApi } from "@/lib/hooks";
import { useSessionStore } from "@/lib/stores";
import { formatBytes, formatDuration, relativeTime, scoreTone } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

export default function DashboardPage() {
  const { data, error, loading } = useApi<Dashboard>("/api/dashboard", { pollMs: 5000 });
  const workspace = useSessionStore((state) => state.workspaces.find((w) => w.id === state.activeWorkspaceId));

  if (loading && !data) return <PageSkeleton />;
  if (error && !data) {
    return (
      <div className="space-y-4">
        <PageHeader title="Dashboard" />
        <Alert title="Could not load the dashboard">{error}</Alert>
      </div>
    );
  }
  if (!data) return <PageSkeleton />;

  const { counts, usage } = data;
  const onboarding = counts.videos === 0;
  const renderMinutes = usage.render_seconds / 60;

  return (
    <div>
      <PageHeader        title="Dashboard"
        description="Everything moving through the pipeline right now, read straight from the live database."
        actions={
          <>
            <Link href="/schedule">
              <Button variant="outline" size="sm">
                <CalendarClock className="h-3.5 w-3.5" /> Schedule
              </Button>
            </Link>
            <Link href="/import">
              <Button variant="outline" size="sm">
                <Radio className="h-3.5 w-3.5" /> Import URL
              </Button>
            </Link>
            <Link href="/upload">
              <Button size="sm">
                <Plus className="h-3.5 w-3.5" /> New video
              </Button>
            </Link>
          </>
        }
      />

      {onboarding ? (
        <Panel className="mb-6 overflow-hidden">
          <div className="grid gap-6 p-6 sm:grid-cols-[1.2fr_1fr] sm:p-8">
            <div>
              <Badge tone="flame">First run</Badge>
              <h2 className="mt-3 text-[22px] font-semibold tracking-tight">
                Bring one video. FireClip will handle the rest.
              </h2>
              <p className="mt-2 max-w-md text-[13px] leading-relaxed text-muted">
                Upload a file or paste a public YouTube / Twitch / Kick link. The pipeline probes the
                media, transcribes it, and proposes clips with an explanation for each one.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <Link href="/upload">
                  <Button>
                    <UploadCloud className="h-4 w-4" /> Upload a video
                  </Button>
                </Link>
                <Link href="/import">
                  <Button variant="outline">Paste a URL</Button>
                </Link>
              </div>
            </div>
            <ol className="space-y-3 rounded-[var(--radius-card)] border border-paper/8 bg-ink-950/50 p-5 text-[12.5px]">
              {[
                "Probe media: duration, resolution, audio",
                "Transcribe with word timestamps",
                "Score highlights with visible signals",
                "Trim, caption and render with FFmpeg",
              ].map((step, index) => (
                <li key={step} className="flex gap-3">
                  <span className="font-mono text-[10px] text-flame-500">0{index + 1}</span>
                  <span className="text-muted">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </Panel>
      ) : null}

      <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Source videos"
          value={counts.videos}
          hint={`${formatBytes(data.storage_bytes)} stored`}
          href="/videos"
        />
        <StatCard
          label="Clips found"
          value={counts.clips}
          hint={`${counts.approved_clips} approved`}
          href="/clips"
        />
        <StatCard
          label="Processing now"
          value={counts.processing}
          hint={counts.processing > 0 ? "Workers are running" : "Queue is idle"}
          href="/renders"
        />
        <StatCard
          label="Published clips"
          value={counts.published}
          hint={`${counts.scheduled_posts} scheduled`}
          href="/schedule"
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
        <div className="space-y-5">
          <Panel>
            <PanelHeader
              title="Pipeline activity"
              description={
                data.processing.length > 0
                  ? "Active ingestion, transcription, analysis and rendering jobs."
                  : "No jobs are running. New uploads appear here immediately."
              }
              action={
                counts.processing > 0 ? (
                  <Badge tone="flame">
                    <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-flame-500" />
                    live
                  </Badge>
                ) : (
                  <Badge tone="neutral">idle</Badge>
                )
              }
            />
            {data.processing.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-5 py-10 text-center">
                <Clapperboard className="h-5 w-5 text-ink-500" />
                <p className="text-[12.5px] text-faint">
                  Nothing queued. Upload footage or open a video to start analysis.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-paper/6">
                {data.processing.map((job) => (
                  <div key={job.id} className="px-5 py-3.5">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <JobStatusBadge status={job.status} />
                        <span className="text-[12.5px] capitalize text-muted">{job.stage || job.kind}</span>
                      </div>
                      <Link
                        href={job.video_id ? `/videos/${job.video_id}` : "/renders"}
                        className="text-[11.5px] text-faint hover:text-paper"
                      >
                        {formatDuration(0)}, {relativeTime(job.created_at)}
                      </Link>
                    </div>
                    <InlineProgress value={job.progress} label={job.kind} />
                    {job.error_message ? (
                      <p className="mt-1.5 line-clamp-2 text-[11px] text-rose">{job.error_message}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <div>
            <SectionHeader
              title="Recent videos"
              description="Latest media added to this workspace."
              action={
                <Link href="/videos" className="text-[12px] text-flame-400 hover:text-flame-500">
                  View library
                </Link>
              }
            />
            {data.recent_videos.length === 0 ? (
              <Panel>
                <EmptyState
                  icon={<Film className="h-5 w-5" />}
                  title="No videos yet"
                  description="Your uploads and imports will show up here."
                  action={
                    <Link href="/upload">
                      <Button size="sm">Upload the first one</Button>
                    </Link>
                  }
                />
              </Panel>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {data.recent_videos.map((video) => (
                  <VideoCard key={video.id} video={video} />
                ))}
              </div>
            )}
          </div>

          <Panel>
            <PanelHeader
              title="Top clips"
              description="Ranked by the current virality score. Scores are explainable, not predictive guarantees."
              action={
                <Link href="/clips" className="text-[12px] text-flame-400 hover:text-flame-500">
                  Review all
                </Link>
              }
            />
            {data.recent_clips.length === 0 ? (
              <EmptyState
                icon={<Flame className="h-5 w-5" />}
                title="No candidates yet"
                description="Once a video has a transcript, AI analysis will populate clip candidates."
              />
            ) : (
              <div className="divide-y divide-paper/6">
                {data.recent_clips.map((clip) => (
                  <Link
                    key={clip.id}
                    href={`/clips?highlight=${clip.id}`}
                    className="flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-paper/3"
                  >
                    <span className={`w-9 font-mono text-[15px] font-semibold ${scoreTone(clip.virality_score)}`}>
                      {Math.round(clip.virality_score)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12.5px] font-medium text-paper">{clip.title}</p>
                      <p className="mt-0.5 truncate text-[11px] text-faint">
                        {clip.video_title}, {formatDuration(clip.duration_ms, true)}
                      </p>
                    </div>
                    <Badge tone={clip.status === "approved" ? "mint" : clip.status === "rejected" ? "rose" : "neutral"}>
                      {clip.status}
                    </Badge>
                  </Link>
                ))}
              </div>
            )}
          </Panel>
        </div>

        <div className="space-y-5">
          <Panel>
            <PanelHeader title="Usage this month" description="Measured locally from pipeline records." />
            <div className="space-y-4 px-5 py-4">
              <UsageBar
                label="Render minutes"
                value={renderMinutes}
                limit={workspace?.monthly_render_minutes ?? 600}
                format={(value) => `${value.toFixed(1)} min`}
              />
              <UsageBar
                label="Clips generated"
                value={counts.clips}
                limit={workspace?.monthly_clip_limit ?? 500}
                format={(value) => `${Math.round(value)}`}
              />
              <div className="flex items-center justify-between border-t border-paper/6 pt-3 text-[11.5px]">
                <span className="text-faint">Transcribed audio</span>
                <span className="font-mono text-muted">{formatDuration(usage.transcription_seconds)}</span>
              </div>
              <div className="flex items-center justify-between text-[11.5px]">
                <span className="text-faint">AI usage units</span>
                <span className="font-mono text-muted">{Math.round(usage.ai_units).toLocaleString()}</span>
              </div>
              <Link
                href="/billing"
                className="flex items-center gap-1 pt-1 text-[11.5px] text-flame-400 hover:text-flame-500"
              >
                View plan & usage
                <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Rendering"
              action={
                <Link href="/renders" className="text-[12px] text-flame-400 hover:text-flame-500">
                  Queue
                </Link>
              }
            />
            {data.renders.length === 0 ? (
              <p className="px-5 py-8 text-center text-[12px] text-faint">No renders yet.</p>
            ) : (
              <div className="divide-y divide-paper/6">
                {data.renders.map((render) => (
                  <div key={render.id} className="flex items-center gap-3 px-5 py-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] bg-paper/5 text-faint">
                      <Download className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] text-paper">{render.project_name || render.preset}</p>
                      <p className="font-mono text-[10px] text-faint">
                        {render.preset}, {render.format}, {relativeTime(render.created_at)}
                      </p>
                    </div>
                    <JobStatusBadge status={render.status} />
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel>
            <PanelHeader title="Recent activity" description="Audit trail for this workspace." />
            {data.recent_activity.length === 0 ? (
              <p className="px-5 py-8 text-center text-[12px] text-faint">No activity recorded yet.</p>
            ) : (
              <div className="divide-y divide-paper/6">
                {data.recent_activity.map((item) => (
                  <div key={item.id} className="px-5 py-2.5">
                    <p className="text-[11.5px] text-muted">
                      <span className="text-paper">{item.user_email?.split("@")[0] || "system"}</span>{" "}
                      {item.action.replace(/\./g, " ")}
                    </p>
                    <p className="mt-0.5 font-mono text-[9.5px] text-faint">{relativeTime(item.created_at)}</p>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel>
            <PanelHeader title="Clip status" />
            <div className="grid grid-cols-3 divide-x divide-paper/6">
              {[
                ["Approved", counts.approved_clips, "text-mint"],
                ["Exports", counts.exports, "text-ember"],
                ["Renders", counts.renders, "text-muted"],
              ].map(([label, value, tone]) => (
                <div key={String(label)} className="px-3 py-4 text-center">
                  <p className={"font-display text-[19px] font-semibold tabular-nums " + tone}>{value as number}</p>
                  <p className="mt-0.5 text-[10.5px] text-faint">{label as string}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
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
      <div className="h-1.5 overflow-hidden rounded-full bg-paper/[0.07]">
        <div
          className={"h-full w-full origin-left rounded-full " + (pct > 85 ? "bg-rose" : "bg-flame-500")}
          style={{ transform: "scaleX(" + pct / 100 + ")" }}
        />
      </div>
    </div>
  );
}
