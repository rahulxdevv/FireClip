"use client";

import Link from "next/link";
import * as React from "react";
import { CalendarClock, ExternalLink, Plus, RefreshCw, Send, X } from "lucide-react";
import { PageHeader } from "@/components/shared";
import {
  Alert,
  Badge,
  Button,
  EmptyState,
  Input,
  PageSkeleton,
  Panel,
  PanelHeader,
  Select,
} from "@/components/ui";
import { PublishStatusBadge } from "@/components/status";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatDateTime, relativeTime } from "@/lib/format";
import type { PublishingJob, SocialAccount } from "@/lib/types";

type View = "upcoming" | "published" | "failed" | "all";

export default function SchedulePage() {
  const jobs = useApi<PublishingJob[]>("/api/publishing/jobs?limit=300", { pollMs: 10000 });
  const accounts = useApi<SocialAccount[]>("/api/publishing/accounts");
  const [view, setView] = React.useState<View>("upcoming");
  const [platform, setPlatform] = React.useState("all");
  const [query, setQuery] = React.useState("");
  const [busy, setBusy] = React.useState<string | null>(null);

  const all = jobs.data || [];
  const upcoming = all.filter((job) => job.status === "scheduled" || job.status === "queued");
  const published = all.filter((job) => job.status === "published");
  const failed = all.filter((job) => job.status === "failed");
  const connected = (accounts.data || []).filter((account) => account.status === "connected");

  const filtered = all.filter((job) => {
    if (view === "upcoming" && !["scheduled", "queued"].includes(job.status)) return false;
    if (view === "published" && job.status !== "published") return false;
    if (view === "failed" && job.status !== "failed") return false;
    if (platform !== "all" && job.platform !== platform) return false;
    if (query.trim()) {
      const haystack = `${job.title} ${job.caption} ${job.account_name} ${job.video_title}`.toLowerCase();
      if (!haystack.includes(query.trim().toLowerCase())) return false;
    }
    return true;
  });

  async function cancel(job: PublishingJob) {
    if (!window.confirm("Cancel this scheduled post?")) return;
    setBusy(job.id);
    try {
      await api.post(`/api/publishing/jobs/${job.id}/cancel`);
      toast("Post cancelled", "success");
      jobs.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function retry(job: PublishingJob) {
    setBusy(job.id);
    try {
      await api.post(`/api/publishing/jobs/${job.id}/retry`);
      toast("Post queued again", "success");
      jobs.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  const views: Array<{ id: View; label: string; count: number }> = [
    { id: "upcoming", label: "Upcoming", count: upcoming.length },
    { id: "published", label: "Published", count: published.length },
    { id: "failed", label: "Failed", count: failed.length },
    { id: "all", label: "All", count: all.length },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        eyebrow="Distribute"
        title="Schedule"
        description="Every scheduled and published post in one calendar. Direct links open the live post on each platform."
        actions={
          <Link href="/publish">
            <Button size="sm"><Plus className="h-3.5 w-3.5" /> New post</Button>
          </Link>
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["Upcoming", upcoming.length],
          ["Published", published.length],
          ["Failed", failed.length],
          ["Connected accounts", connected.length],
        ].map(([label, value]) => (
          <Panel key={String(label)} className="p-4">
            <p className="text-[10px] uppercase tracking-[0.14em] text-faint">{label}</p>
            <p className="mt-1 font-display text-2xl">{value}</p>
          </Panel>
        ))}
      </div>

      {accounts.data && connected.length === 0 ? (
        <Alert tone="info" className="mb-4" title="No connected publishing accounts">
          Connect YouTube, Instagram or TikTok in <Link href="/accounts" className="text-flame-300 underline">social accounts</Link> before scheduling a post.
        </Alert>
      ) : null}
      {jobs.error ? <Alert className="mb-4">{jobs.error}</Alert> : null}

      <Panel>
        <PanelHeader
          title="Post timeline"
          description="Scheduled posts move to the publishing queue when their time arrives."
          action={<Badge tone="neutral">{all.length} posts</Badge>}
        />
        <div className="flex flex-wrap items-center gap-2 border-b border-white/6 px-4 py-3">
          <div className="flex flex-wrap gap-1">
            {views.map((item) => (
              <button
                key={item.id}
                onClick={() => setView(item.id)}
                className={`rounded-md px-2.5 py-1.5 text-[11.5px] transition-colors ${
                  view === item.id ? "bg-white/10 text-paper" : "text-faint hover:bg-white/5 hover:text-paper"
                }`}
              >
                {item.label} <span className="text-[10px] opacity-60">{item.count}</span>
              </button>
            ))}
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search"
              className="h-8 w-36 text-[11px]"
            />
            <Select value={platform} onChange={(event) => setPlatform(event.target.value)} className="h-8 w-32 text-[11px]">
              <option value="all">All platforms</option>
              <option value="youtube">YouTube</option>
              <option value="instagram">Instagram</option>
              <option value="tiktok">TikTok</option>
              <option value="facebook">Facebook</option>
            </Select>
          </div>
        </div>

        {jobs.loading && !jobs.data ? (
          <div className="p-4"><PageSkeleton /></div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<CalendarClock className="h-5 w-5" />}
            title={view === "upcoming" ? "Nothing scheduled" : "No posts here"}
            description={view === "upcoming" ? "Schedule a post from Publishing or turn on auto-publish in a campaign." : "Try another filter or publish a clip."}
            action={<Link href="/publish"><Button size="sm" variant="outline">Open publishing</Button></Link>}
          />
        ) : (
          <div className="divide-y divide-white/6">
            {filtered.map((job) => (
              <div key={job.id} className="px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[12.5px] font-medium capitalize">{job.platform}</span>
                      <PublishStatusBadge status={job.status} />
                      <span className="truncate text-[11px] text-faint">{job.account_name}</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-[12px] leading-relaxed text-paper">
                      {job.title || job.caption || job.video_title || "Untitled post"}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-faint">
                      {job.scheduled_for ? (
                        <span className="flex items-center gap-1"><CalendarClock className="h-3 w-3" /> {formatDateTime(job.scheduled_for)}</span>
                      ) : job.published_at ? (
                        <span>Published {relativeTime(job.published_at)}</span>
                      ) : null}
                      <span>{job.video_title || "Rendered clip"}</span>
                      {job.error_message ? <span className="text-rose">{job.error_message}</span> : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {job.external_url ? (
                      <a
                        href={job.external_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2.5 py-1.5 text-[11px] text-paper hover:bg-white/5"
                      >
                        <ExternalLink className="h-3 w-3" /> Open post
                      </a>
                    ) : null}
                    {["scheduled", "queued"].includes(job.status) ? (
                      <Button size="sm" variant="ghost" loading={busy === job.id} onClick={() => cancel(job)}>
                        <X className="h-3.5 w-3.5" /> Cancel
                      </Button>
                    ) : null}
                    {["failed", "cancelled"].includes(job.status) ? (
                      <Button size="sm" variant="outline" loading={busy === job.id} onClick={() => retry(job)}>
                        <RefreshCw className="h-3.5 w-3.5" /> Retry
                      </Button>
                    ) : null}
                    {job.status === "published" ? (
                      <span className="flex items-center gap-1 text-[10.5px] text-mint"><Send className="h-3 w-3" /> Live</span>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
