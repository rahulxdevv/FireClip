"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import * as React from "react";
import { CalendarClock, ExternalLink, RefreshCw, Send, Users, X } from "lucide-react";
import { PageHeader } from "@/components/shared";
import {
  Alert,
  Badge,
  Button,
  EmptyState,
  Field,
  Input,
  PageSkeleton,
  Panel,
  PanelHeader,
  Select,
  Tabs,
  Textarea,
} from "@/components/ui";
import { PublishStatusBadge } from "@/components/status";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatDateTime, relativeTime } from "@/lib/format";
import type { ExportItem, PublishingJob, SocialAccount } from "@/lib/types";

export default function PublishPage() {
  const params = useSearchParams();
  const preselected = params.get("export") || "";
  const exportsList = useApi<ExportItem[]>("/api/exports?limit=200");
  const accounts = useApi<SocialAccount[]>("/api/publishing/accounts");
  const jobs = useApi<PublishingJob[]>("/api/publishing/jobs?limit=100", { pollMs: 5000 });
  const [tab, setTab] = React.useState("all");
  const [form, setForm] = React.useState({
    exported_video_id: preselected,
    social_account_id: "",
    title: "",
    caption: "",
    hashtags: "",
    privacy: "public",
    scheduled_for: "",
  });
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (preselected) setForm((current) => ({ ...current, exported_video_id: preselected }));
  }, [preselected]);

  React.useEffect(() => {
    if (accounts.data && accounts.data.length > 0 && !form.social_account_id) {
      setForm((current) => ({ ...current, social_account_id: accounts.data?.[0]?.id || "" }));
    }
  }, [accounts.data, form.social_account_id]);

  const selectedExport = (exportsList.data || []).find((item) => item.id === form.exported_video_id);
  const filtered = (jobs.data || []).filter((job) => tab === "all" || job.status === tab);

  async function submit(event: React.FormEvent, publishNow: boolean) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/api/publishing/jobs", {
        exported_video_id: form.exported_video_id,
        social_account_id: form.social_account_id,
        title: form.title,
        caption: form.caption,
        hashtags: form.hashtags,
        privacy: form.privacy,
        scheduled_for: form.scheduled_for ? new Date(form.scheduled_for).toISOString() : null,
        publish_now: publishNow,
      });
      toast(publishNow ? "Publishing started" : "Post scheduled", "success");
      setForm((current) => ({ ...current, caption: "", title: "", hashtags: "", scheduled_for: "" }));
      jobs.refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function retry(job: PublishingJob) {
    setBusy(job.id);
    try {
      await api.post(`/api/publishing/jobs/${job.id}/retry`);
      jobs.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function cancel(job: PublishingJob) {
    setBusy(job.id);
    try {
      await api.post(`/api/publishing/jobs/${job.id}/cancel`);
      jobs.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  const connected = (accounts.data || []).filter((account) => account.status === "connected");

  return (
    <div>
      <PageHeader        title="Publishing"
        description="Queue an export to a connected platform, immediately or on a schedule. A failed API call is reported as failed, never as published."
        actions={
          <Link href="/accounts">
            <Button size="sm" variant="outline">
              <Users className="h-3.5 w-3.5" /> Manage accounts
            </Button>
          </Link>
        }
      />

      {connected.length === 0 ? (
        <Alert title="No connected accounts" tone="info" className="mb-5">
          Connect YouTube, TikTok, Instagram or Facebook in{" "}
          <Link href="/accounts" className="underline decoration-paper/30 underline-offset-2 hover:text-paper">
            social accounts
          </Link>{" "}
          before scheduling a post.
        </Alert>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[1fr_1.25fr]">
        <Panel className="h-fit">
          <PanelHeader title="New publish" description="The caption you submit is exactly what the platform receives." />
          <form onSubmit={(event) => submit(event, false)} className="space-y-4 p-5">
            <Field label="Export">
              <Select
                value={form.exported_video_id}
                onChange={(event) => setForm({ ...form, exported_video_id: event.target.value })}
                required
              >
                <option value="">Select a rendered file</option>
                {(exportsList.data || []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title || item.filename}, {item.format.toUpperCase()}
                  </option>
                ))}
              </Select>
            </Field>
            {selectedExport ? (
              <p className="font-mono text-[10.5px] text-faint">
                {selectedExport.width}×{selectedExport.height}, {formatDateTime(selectedExport.created_at)}
              </p>
            ) : null}
            <Field label="Account">
              <Select
                value={form.social_account_id}
                onChange={(event) => setForm({ ...form, social_account_id: event.target.value })}
                required
              >
                <option value="">Select a connected account</option>
                {connected.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.platform}, {account.account_name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Title">
                <Input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} maxLength={240} />
              </Field>
              <Field label="Privacy">
                <Select value={form.privacy} onChange={(event) => setForm({ ...form, privacy: event.target.value })}>
                  <option value="public">Public</option>
                  <option value="unlisted">Unlisted</option>
                  <option value="private">Private</option>
                </Select>
              </Field>
            </div>
            <Field label="Caption">
              <Textarea
                value={form.caption}
                onChange={(event) => setForm({ ...form, caption: event.target.value })}
                rows={5}
                maxLength={5000}
                placeholder="Write the caption exactly as it should appear."
              />
            </Field>
            <Field label="Hashtags">
              <Input
                value={form.hashtags}
                onChange={(event) => setForm({ ...form, hashtags: event.target.value })}
                placeholder="#shorts #podcast"
                maxLength={500}
              />
            </Field>
            <Field label="Schedule" hint="Leave empty and use publish now, or pick a future time.">
              <Input
                type="datetime-local"
                value={form.scheduled_for}
                onChange={(event) => setForm({ ...form, scheduled_for: event.target.value })}
              />
            </Field>
            {error ? <Alert>{error}</Alert> : null}
            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={(event) => submit(event, true)} loading={submitting} disabled={!connected.length}>
                <Send className="h-4 w-4" /> Publish now
              </Button>
              <Button type="submit" variant="outline" loading={submitting} disabled={!connected.length || !form.scheduled_for}>
                <CalendarClock className="h-4 w-4" /> Schedule
              </Button>
            </div>
            <p className="text-[10.5px] leading-relaxed text-faint">
              Publishing uses official platform APIs. Permissions, review status and rate limits are enforced by
              the platform; FireClip reports the exact error when one occurs.
            </p>
          </form>
        </Panel>

        <div className="space-y-4">
          <Panel>
            <div className="px-3 pt-1">
              <Tabs
                value={tab}
                onValueChange={setTab}
                tabs={[
                  { value: "all", label: "All", count: (jobs.data || []).length },
                  { value: "scheduled", label: "Scheduled" },
                  { value: "published", label: "Published" },
                  { value: "failed", label: "Failed" },
                ]}
              />
            </div>
            {jobs.loading && !jobs.data ? (
              <div className="p-4"><PageSkeleton /></div>
            ) : filtered.length === 0 ? (
              <EmptyState
                title="Nothing here yet"
                description="Publishing jobs you create will appear in this queue."
              />
            ) : (
              <div className="divide-y divide-paper/6">
                {filtered.map((job) => (
                  <div key={job.id} className="px-4 py-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[12.5px] font-medium capitalize">{job.platform}</span>
                          <PublishStatusBadge status={job.status} />
                          <span className="truncate text-[11px] text-faint">{job.account_name}</span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-[11.5px] leading-relaxed text-muted">
                          {job.caption || job.title || job.video_title || "No caption"}
                        </p>
                        <p className="mt-1 font-mono text-[9.5px] text-faint">
                          {job.scheduled_for ? `scheduled ${formatDateTime(job.scheduled_for)}` : `created ${relativeTime(job.created_at)}`}
                          {job.published_at ? `, published ${relativeTime(job.published_at)}` : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {job.external_url ? (
                          <a href={job.external_url} target="_blank" rel="noreferrer noopener">
                            <Button size="sm" variant="ghost">
                              <ExternalLink className="h-3 w-3" /> Open
                            </Button>
                          </a>
                        ) : null}
                        {["scheduled", "queued"].includes(job.status) ? (
                          <Button size="sm" variant="ghost" loading={busy === job.id} onClick={() => cancel(job)}>
                            <X className="h-3 w-3" />
                          </Button>
                        ) : null}
                        {["failed", "cancelled"].includes(job.status) ? (
                          <Button size="sm" variant="ghost" loading={busy === job.id} onClick={() => retry(job)}>
                            <RefreshCw className="h-3 w-3" /> Retry
                          </Button>
                        ) : null}
                      </div>
                    </div>
                    {job.error_message ? (
                      <p className="mt-2 rounded-[var(--radius-control)] border border-rose/20 bg-rose/5 px-2.5 py-1.5 text-[10.5px] leading-relaxed text-rose">
                        {job.error_message}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel className="p-4">
            <p className="text-[12px] font-medium">Platform reality check</p>
            <ul className="mt-2 space-y-1.5 text-[11px] leading-relaxed text-faint">
              <li>YouTube: resumable uploads with the channel token; privacy is respected.</li>
              <li>Facebook: page video uploads through the Graph API.</li>
              <li>Instagram: Reels require a publicly reachable video URL (S3 + MEDIA_PUBLIC_BASE_URL).</li>
              <li>TikTok: direct post requires an approved developer app and its own audit.</li>
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  );
}
