"use client";

import Link from "next/link";
import * as React from "react";
import { CircleStop, Radio, Trash2, Video } from "lucide-react";
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
import { formatDateTime } from "@/lib/format";
import type { Campaign, LiveStream } from "@/lib/types";

const statusTone: Record<string, "neutral" | "flame" | "mint" | "rose" | "ember"> = {
  monitoring: "neutral",
  recording: "flame",
  recorded: "mint",
  stopped: "neutral",
  error: "rose",
};

export default function LivePage() {
  const { data, error, loading, refresh } = useApi<LiveStream[]>("/api/live-streams", { pollMs: 5000 });
  const campaigns = useApi<Campaign[]>("/api/campaigns");
  const [url, setUrl] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [campaignId, setCampaignId] = React.useState("");
  const [autoRecord, setAutoRecord] = React.useState(false);
  const [autoClip, setAutoClip] = React.useState(true);
  const [submitting, setSubmitting] = React.useState(false);
  const [actionId, setActionId] = React.useState<string | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await api.post("/api/live-streams", {
        url: url.trim(),
        title: title.trim() || null,
        campaign_id: campaignId || null,
        auto_record: autoRecord,
        auto_clip: autoClip,
      });
      setUrl("");
      setTitle("");
      setCampaignId("");
      setAutoRecord(false);
      setAutoClip(true);
      refresh();
      toast("Stream added", "success");
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function start(stream: LiveStream) {
    setActionId(stream.id);
    try {
      await api.post(`/api/live-streams/${stream.id}/start`);
      toast("Recording started", "success");
      refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setActionId(null);
    }
  }

  async function stop(stream: LiveStream) {
    setActionId(stream.id);
    try {
      await api.post(`/api/live-streams/${stream.id}/stop`);
      toast("Recording stopped. The capture will finish processing.", "info");
      refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setActionId(null);
    }
  }

  async function updateAutomation(stream: LiveStream, patch: Partial<LiveStream>) {
    setActionId(stream.id);
    try {
      await api.patch(`/api/live-streams/${stream.id}`, patch);
      refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setActionId(null);
    }
  }

  async function remove(stream: LiveStream) {
    if (!window.confirm("Remove this live stream? Recorded videos are kept.")) return;
    setActionId(stream.id);
    try {
      await api.delete(`/api/live-streams/${stream.id}`);
      refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader        title="Live streams"
        description="Watch public live URLs, record automatically when the stream goes live, and run the capture through a campaign’s clip brief."
      />

      <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">
        <Panel className="h-fit">
          <PanelHeader title="Monitor a stream" description="YouTube, Twitch and Kick public live URLs." />
          <form onSubmit={add} className="space-y-4 p-5">
            <Field label="Live URL">
              <Input
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://twitch.tv/channel"
                required
                className="font-mono text-[12px]"
              />
            </Field>
            <Field label="Label" hint="Optional, helps identify the recording later.">
              <Input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} />
            </Field>
            <Field label="Campaign" hint="Recorded videos inherit the campaign brief, style and automation.">
              <Select value={campaignId} onChange={(event) => setCampaignId(event.target.value)}>
                <option value="">No campaign</option>
                {(campaigns.data || []).filter((item) => item.status !== "archived").map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </Select>
            </Field>
            <div className="space-y-3 rounded-[var(--radius-card)] border border-paper/8 bg-ink-850/50 p-3.5">
              <Switch
                checked={autoRecord}
                onCheckedChange={setAutoRecord}
                label="Record automatically when this URL goes live"
              />
              <Switch
                checked={autoClip}
                onCheckedChange={setAutoClip}
                label="Transcribe and analyse the capture when it ends"
              />
            </div>
            <p className="text-[10.5px] leading-relaxed text-faint">
              Automatic checks run about once a minute. A stream is only captured while the platform reports it
              live; scheduled or offline pages are skipped. Nothing bypasses access controls.
            </p>
            {formError ? <Alert>{formError}</Alert> : null}
            <Button type="submit" loading={submitting} className="w-full">
              <Radio className="h-4 w-4" /> Add stream
            </Button>
            <p className="text-[11px] leading-relaxed text-faint">
              Recording requires yt-dlp. Streams are captured until you stop them; the file then enters the
              standard pipeline. Respect the creator&apos;s terms and platform rules.
            </p>
          </form>
        </Panel>

        <div className="space-y-4">
          {error ? <Alert>{error}</Alert> : null}
          {loading && !data ? (
            <PageSkeleton />
          ) : (data || []).length === 0 ? (
            <Panel>
              <EmptyState
                icon={<Radio className="h-5 w-5" />}
                title="No streams monitored"
                description="Add a public live URL to watch it and start a recording when you are ready."
              />
            </Panel>
          ) : (
            (data || []).map((stream) => (
              <Panel key={stream.id} className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge tone={statusTone[stream.status] || "neutral"}>{stream.status}</Badge>
                      <span className="text-[11px] capitalize text-faint">{stream.platform}</span>
                    </div>
                    <p className="mt-2 truncate text-[13px] font-medium">{stream.title}</p>
                    <p className="mt-0.5 truncate font-mono text-[10.5px] text-faint">{stream.url}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      {stream.campaign_id ? (
                        <Badge tone="outline">
                          {(campaigns.data || []).find((item) => item.id === stream.campaign_id)?.name || "Campaign"}
                        </Badge>
                      ) : null}
                      {stream.auto_record ? <Badge tone="flame">auto-record</Badge> : null}
                      {stream.auto_clip ? <Badge tone="neutral">auto-clip</Badge> : null}
                    </div>
                    <p className="mt-2 text-[11px] text-faint">
                      Added {formatDateTime(stream.created_at)}
                      {stream.started_at ? `, started ${formatDateTime(stream.started_at)}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {stream.status === "recording" ? (
                      <Button variant="danger" size="sm" loading={actionId === stream.id} onClick={() => stop(stream)}>
                        <CircleStop className="h-3.5 w-3.5" /> Stop
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        loading={actionId === stream.id}
                        onClick={() => start(stream)}
                      >
                        <Radio className="h-3.5 w-3.5" /> Record
                      </Button>
                    )}
                    <Button variant="ghost" size="icon" onClick={() => remove(stream)} aria-label="Remove stream">
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
                {stream.recording_video_id ? (
                  <Link
                    href={`/videos/${stream.recording_video_id}`}
                    className="mt-3 inline-flex items-center gap-1.5 text-[11.5px] text-flame-400 hover:text-flame-500"
                  >
                    <Video className="h-3.5 w-3.5" /> Open the recorded video
                  </Link>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 border-t border-paper/6 pt-3">
                  <Switch
                    checked={stream.auto_record}
                    disabled={actionId === stream.id || stream.status === "recording"}
                    onCheckedChange={(value) => updateAutomation(stream, { auto_record: value })}
                    label="Auto-record"
                  />
                  <Switch
                    checked={stream.auto_clip}
                    disabled={actionId === stream.id}
                    onCheckedChange={(value) => updateAutomation(stream, { auto_clip: value })}
                    label="Auto-clip"
                  />
                </div>
                {stream.error_message ? (
                  <p className="mt-2 text-[11.5px] text-rose">{stream.error_message}</p>
                ) : null}
              </Panel>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
