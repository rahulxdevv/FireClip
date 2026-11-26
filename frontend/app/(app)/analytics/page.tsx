"use client";

import * as React from "react";
import { BarChart3, ExternalLink, RefreshCw, Upload } from "lucide-react";
import { PageHeader, SectionHeader, StatCard } from "@/components/shared";
import { PlatformBars, ViewsChart } from "@/components/charts";
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
  PanelHeader,
  Select,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatDateTime } from "@/lib/format";
import type { AnalyticsOverview, PublishingJob } from "@/lib/types";

export default function AnalyticsPage() {
  const overview = useApi<AnalyticsOverview>("/api/analytics/overview");
  const jobs = useApi<PublishingJob[]>("/api/publishing/jobs?limit=200");
  const [syncing, setSyncing] = React.useState(false);
  const [entryOpen, setEntryOpen] = React.useState(false);
  const [syncMessages, setSyncMessages] = React.useState<string[]>([]);

  async function sync() {
    setSyncing(true);
    try {
      const result = await api.post<{ synced: number; skipped: number; messages: string[] }>("/api/analytics/sync");
      setSyncMessages(result.messages);
      toast(
        result.synced > 0 ? `Synced ${result.synced} posts` : "Nothing new to sync",
        result.synced > 0 ? "success" : "info",
      );
      overview.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setSyncing(false);
    }
  }

  if (overview.loading && !overview.data) return <PageSkeleton />;
  if (!overview.data) {
    return (
      <div>
        <PageHeader title="Analytics" />
        <Alert title="Analytics unavailable">{overview.error}</Alert>
      </div>
    );
  }

  const data = overview.data;
  const totals = data.totals;
  const published = (jobs.data || []).filter((job) => job.status === "published");
  const engagement = Number(totals.engagement_rate || 0);

  return (
    <div>
      <PageHeader        title="Analytics"
        description="Only measured numbers appear here. FireClip never estimates views, retention or engagement."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setEntryOpen(true)}>
              <Upload className="h-3.5 w-3.5" /> Record numbers
            </Button>
            <Button size="sm" onClick={sync} loading={syncing}>
              <RefreshCw className="h-3.5 w-3.5" /> Sync from platforms
            </Button>
          </>
        }
      />

      <div className="mb-4 space-y-2">
        {data.notes.map((note) => (
          <Alert key={note} tone="info">
            {note}
          </Alert>
        ))}
        {syncMessages.length > 0 ? (
          <Alert tone="info" title="Last sync report">
            <ul className="mt-1 space-y-1">
              {syncMessages.map((message, index) => (
                <li key={index}>• {message}</li>
              ))}
            </ul>
          </Alert>
        ) : null}
      </div>

      <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Views" value={Number(totals.views || 0).toLocaleString()} hint={`${totals.measured_posts} measured posts`} icon={<BarChart3 className="h-4 w-4" />} />
        <StatCard label="Engagement rate" value={`${engagement.toFixed(1)}%`} hint={`${Number(totals.likes || 0) + Number(totals.comments || 0) + Number(totals.shares || 0)} interactions`} />
        <StatCard label="Watch time" value={`${Math.round(Number(totals.watch_time_seconds || 0) / 60)}m`} hint="only when a platform returns it" />
        <StatCard label="Published clips" value={totals.published} hint={`${data.data_sources.length > 0 ? data.data_sources.join(", ") : "no data sources"}`} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
        <div className="space-y-5">
          <Panel>
            <PanelHeader title="Views over time" description="One snapshot per measured post, plotted by capture date." />
            <div className="p-4">
              <ViewsChart data={data.series} />
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Top posts" description="Ranked by latest measured views." />
            {(data.top_posts || []).length === 0 ? (
              <EmptyState
                icon={<BarChart3 className="h-5 w-5" />}
                title="No measured posts"
                description="Sync a connected platform after publishing, or record numbers you can see in the platform dashboard."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-left text-[11.5px]">
                  <thead className="border-b border-paper/8 text-faint">
                    <tr>
                      {["Post", "Platform", "Views", "Likes", "Comments", "Source"].map((head) => (
                        <th key={head} className="px-4 py-2.5 font-medium">{head}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-paper/5">
                    {data.top_posts.map((post, index) => (
                      <tr key={`${post.publishing_job_id}-${index}`}>
                        <td className="max-w-[220px] truncate px-4 py-2.5 text-paper">
                          {post.external_url ? (
                            <a href={String(post.external_url)} target="_blank" rel="noreferrer noopener" className="hover:text-flame-400">
                              {String(post.title || "Untitled")} <ExternalLink className="inline h-2.5 w-2.5" />
                            </a>
                          ) : (
                            String(post.title || "Untitled")
                          )}
                        </td>
                        <td className="px-4 py-2.5 capitalize text-muted">{String(post.platform)}</td>
                        <td className="px-4 py-2.5 font-mono text-muted">{Number(post.views || 0).toLocaleString()}</td>
                        <td className="px-4 py-2.5 font-mono text-muted">{Number(post.likes || 0).toLocaleString()}</td>
                        <td className="px-4 py-2.5 font-mono text-muted">{Number(post.comments || 0).toLocaleString()}</td>
                        <td className="px-4 py-2.5">
                          <Badge tone={post.source === "platform_api" ? "mint" : "neutral"}>{String(post.source)}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        <div className="space-y-5">
          <Panel>
            <PanelHeader title="Platform breakdown" />
            <div className="p-4">
              <PlatformBars data={data.platform_breakdown} />
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Recorded snapshots" description="Manual entries are labelled as manual everywhere." />
            <div className="space-y-2 p-4 text-[11.5px] text-faint">
              <div className="flex justify-between"><span>Measured posts</span><span className="font-mono text-muted">{totals.measured_posts}</span></div>
              <div className="flex justify-between"><span>Total shares</span><span className="font-mono text-muted">{Number(totals.shares || 0).toLocaleString()}</span></div>
              <div className="flex justify-between"><span>Renders produced</span><span className="font-mono text-muted">{totals.renders}</span></div>
              <div className="flex justify-between"><span>Exports</span><span className="font-mono text-muted">{totals.exports}</span></div>
            </div>
          </Panel>

          <Panel className="p-4">
            <p className="text-[12px] font-medium">Feedback loop</p>
            <p className="mt-1.5 text-[11px] leading-relaxed text-faint">
              When measured data exists, its top-performing titles and retention are included as soft guidance in
              future LLM analysis prompts. The built-in heuristic engine does not pretend to learn from data it does
              not have.
            </p>
          </Panel>
        </div>
      </div>

      <div className="mt-8">
        <SectionHeader title="Published posts" description="Every published job, with its measured data status." />
        {published.length === 0 ? (
          <Panel>
            <EmptyState
              icon={<BarChart3 className="h-5 w-5" />}
              title="Nothing published yet"
              description="After a post is published, it becomes eligible for platform sync and manual measurement."
            />
          </Panel>
        ) : (
          <Panel>
            <div className="divide-y divide-paper/6">
              {published.map((job) => (
                <div key={job.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-[12.5px] text-paper">{job.caption || job.title || job.video_title}</p>
                    <p className="mt-0.5 font-mono text-[10px] text-faint">
                      {job.platform}, {job.account_name}, {formatDateTime(job.published_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone="mint">published</Badge>
                    <Button size="sm" variant="ghost" onClick={() => setEntryOpen(true)}>
                      <Upload className="h-3 w-3" /> Add numbers
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        )}
      </div>

      <ManualEntryDialog
        open={entryOpen}
        onOpenChange={setEntryOpen}
        jobs={published}
        onSaved={() => {
          overview.refresh();
          toast("Measurement recorded", "success");
        }}
      />
    </div>
  );
}

function ManualEntryDialog({
  open,
  onOpenChange,
  jobs,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jobs: PublishingJob[];
  onSaved: () => void;
}) {
  const [form, setForm] = React.useState({
    publishing_job_id: "",
    views: "",
    likes: "",
    comments: "",
    shares: "",
    watch_time_seconds: "",
    retention_pct: "",
  });
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/analytics/entry", {
        publishing_job_id: form.publishing_job_id,
        views: Number(form.views || 0),
        likes: Number(form.likes || 0),
        comments: Number(form.comments || 0),
        shares: Number(form.shares || 0),
        watch_time_seconds: Number(form.watch_time_seconds || 0),
        retention_pct: Number(form.retention_pct || 0),
      });
      onOpenChange(false);
      setForm({ publishing_job_id: "", views: "", likes: "", comments: "", shares: "", watch_time_seconds: "", retention_pct: "" });
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Record measured numbers"
      description="Use the values shown in the platform's own analytics. This is labelled as a manual source."
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={save} loading={saving} disabled={!form.publishing_job_id}>Save snapshot</Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Published post">
          <Select
            value={form.publishing_job_id}
            onChange={(event) => setForm({ ...form, publishing_job_id: event.target.value })}
          >
            <option value="">Select a post</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.platform}, {job.caption?.slice(0, 40) || job.title || job.id.slice(0, 6)}
              </option>
            ))}
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          {[
            ["views", "Views"],
            ["likes", "Likes"],
            ["comments", "Comments"],
            ["shares", "Shares"],
            ["watch_time_seconds", "Watch time (s)"],
            ["retention_pct", "Retention (%)"],
          ].map(([key, label]) => (
            <Field key={key} label={label}>
              <Input
                type="number"
                min={0}
                value={form[key as keyof typeof form]}
                onChange={(event) => setForm({ ...form, [key]: event.target.value })}
              />
            </Field>
          ))}
        </div>
        {error ? <Alert>{error}</Alert> : null}
      </div>
    </Dialog>
  );
}
