"use client";

import Link from "next/link";
import * as React from "react";
import { CircleStop, ExternalLink, Plus, Radio, Trash2, Users, Video } from "lucide-react";
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
  Switch,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatDateTime, relativeTime } from "@/lib/format";
import type { Campaign, LiveStream } from "@/lib/types";

const statusTone: Record<string, "neutral" | "flame" | "mint" | "rose" | "ember"> = {
  monitoring: "neutral",
  recording: "flame",
  recorded: "mint",
  stopped: "neutral",
  error: "rose",
};

export default function StreamersPage() {
  const { data, error, loading, refresh } = useApi<LiveStream[]>("/api/live-streams", { pollMs: 10000 });
  const campaigns = useApi<Campaign[]>("/api/campaigns");
  const [form, setForm] = React.useState({
    name: "",
    url: "",
    campaign_id: "",
    auto_record: true,
    auto_clip: true,
  });
  const [submitting, setSubmitting] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);

  const streams = data || [];
  const recording = streams.filter((stream) => stream.status === "recording").length;
  const monitoring = streams.filter((stream) => stream.status === "monitoring").length;
  const autoRecord = streams.filter((stream) => stream.auto_record).length;

  async function add(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await api.post("/api/live-streams", {
        url: form.url.trim(),
        title: form.name.trim() || null,
        campaign_id: form.campaign_id || null,
        auto_record: form.auto_record,
        auto_clip: form.auto_clip,
      });
      setForm({ name: "", url: "", campaign_id: "", auto_record: true, auto_clip: true });
      refresh();
      toast("Streamer added", "success");
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function act(stream: LiveStream, action: "start" | "stop" | "delete") {
    if (action === "delete" && !window.confirm("Remove this streamer? Recorded videos are kept.")) return;
    setBusy(stream.id);
    try {
      if (action === "delete") {
        await api.delete(`/api/live-streams/${stream.id}`);
        toast("Streamer removed", "success");
      } else {
        await api.post(`/api/live-streams/${stream.id}/${action}`);
        toast(action === "start" ? "Recording started" : "Recording stopped", "info");
      }
      refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function toggle(stream: LiveStream, patch: Partial<LiveStream>) {
    setBusy(stream.id);
    try {
      await api.patch(`/api/live-streams/${stream.id}`, patch);
      refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        eyebrow="Ingest"
        title="Streamers"
        description="A roster of the creators you monitor. Each streamer keeps its own campaign, recording and analysis rules."
      />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["Streamers", streams.length],
          ["Monitoring", monitoring],
          ["Recording", recording],
          ["Auto-record", autoRecord],
        ].map(([label, value]) => (
          <Panel key={String(label)} className="p-4">
            <p className="text-[10px] uppercase tracking-[0.14em] text-faint">{label}</p>
            <p className="mt-1 font-display text-2xl">{value}</p>
          </Panel>
        ))}
      </div>

      {error ? <Alert className="mb-4">{error}</Alert> : null}

      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Panel>
          <PanelHeader
            title="Roster"
            description="Automatic checks run about once a minute. Only public live URLs are monitored."
            action={<Badge tone="neutral">{streams.length} total</Badge>}
          />
          {loading && !data ? (
            <div className="p-4"><PageSkeleton /></div>
          ) : streams.length === 0 ? (
            <EmptyState
              icon={<Users className="h-5 w-5" />}
              title="No streamers yet"
              description="Add a public YouTube, Twitch or Kick live URL to start monitoring."
            />
          ) : (
            <div className="divide-y divide-white/6">
              {streams.map((stream) => {
                const campaign = (campaigns.data || []).find((item) => item.id === stream.campaign_id);
                return (
                  <div key={stream.id} className="px-4 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate text-[13px] font-medium">{stream.title}</span>
                          <Badge tone={statusTone[stream.status] || "neutral"}>{stream.status}</Badge>
                          <Badge tone="neutral">{stream.platform}</Badge>
                        </div>
                        <p className="mt-1 truncate font-mono text-[10px] text-faint">{stream.url}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-faint">
                          <span>{campaign ? `Campaign: ${campaign.name}` : "No campaign"}</span>
                          <span>Checked {stream.last_checked_at ? relativeTime(stream.last_checked_at) : "not yet"}</span>
                          {stream.started_at ? <span>Started {formatDateTime(stream.started_at)}</span> : null}
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {stream.status === "recording" ? (
                          <Button size="sm" variant="outline" loading={busy === stream.id} onClick={() => act(stream, "stop")}>
                            <CircleStop className="h-3.5 w-3.5" /> Stop
                          </Button>
                        ) : (
                          <Button size="sm" variant="outline" loading={busy === stream.id} onClick={() => act(stream, "start")}>
                            <Radio className="h-3.5 w-3.5" /> Record
                          </Button>
                        )}
                        {stream.recording_video_id ? (
                          <Link href={`/videos/${stream.recording_video_id}`} className="text-[10.5px] text-flame-300 hover:underline">
                            Open recording
                          </Link>
                        ) : null}
                        <button
                          className="rounded p-1.5 text-faint hover:bg-white/5 hover:text-rose"
                          onClick={() => act(stream, "delete")}
                          aria-label="Remove streamer"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-4 rounded-lg border border-white/6 bg-ink-850/40 px-3 py-2">
                      <Switch
                        checked={stream.auto_record}
                        onCheckedChange={(value) => toggle(stream, { auto_record: value })}
                        label="Auto-record"
                      />
                      <Switch
                        checked={stream.auto_clip}
                        onCheckedChange={(value) => toggle(stream, { auto_clip: value })}
                        label="Analyze after capture"
                      />
                    </div>
                    {stream.error_message ? (
                      <p className="mt-2 rounded-md border border-rose/20 bg-rose/5 px-2.5 py-1.5 text-[10.5px] text-rose">
                        {stream.error_message}
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </Panel>

        <Panel className="h-fit">
          <PanelHeader title="Add a streamer" description="Public live URL, campaign and automation." />
          <form onSubmit={add} className="space-y-3.5 p-4">
            <Field label="Streamer name">
              <Input
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="Creator or channel name"
                maxLength={200}
              />
            </Field>
            <Field label="Live URL">
              <Input
                value={form.url}
                onChange={(event) => setForm((current) => ({ ...current, url: event.target.value }))}
                placeholder="https://twitch.tv/channel"
                required
                className="font-mono text-[11px]"
              />
            </Field>
            <Field label="Campaign">
              <Select
                value={form.campaign_id}
                onChange={(event) => setForm((current) => ({ ...current, campaign_id: event.target.value }))}
              >
                <option value="">No campaign</option>
                {(campaigns.data || []).filter((item) => item.status !== "archived").map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </Select>
            </Field>
            <div className="space-y-2 rounded-lg border border-white/8 bg-ink-850/50 p-3">
              <Switch
                checked={form.auto_record}
                onCheckedChange={(value) => setForm((current) => ({ ...current, auto_record: value }))}
                label="Record when the stream goes live"
              />
              <Switch
                checked={form.auto_clip}
                onCheckedChange={(value) => setForm((current) => ({ ...current, auto_clip: value }))}
                label="Transcribe and analyze after capture"
              />
            </div>
            {formError ? <Alert>{formError}</Alert> : null}
            <Button type="submit" loading={submitting} className="w-full">
              <Plus className="h-4 w-4" /> Add streamer
            </Button>
            <Link
              href="/live"
              className="flex items-center justify-center gap-1.5 text-[10.5px] text-faint hover:text-paper"
            >
              <ExternalLink className="h-3 w-3" /> Open live capture controls
            </Link>
          </form>
        </Panel>
      </div>

      <p className="mt-4 flex items-center gap-2 text-[10.5px] leading-relaxed text-faint">
        <Video className="h-3.5 w-3.5" />
        Recording respects platform terms and access controls. Nothing bypasses authentication, DRM or paywalls.
      </p>
    </div>
  );
}
