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
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatDateTime } from "@/lib/format";
import type { LiveStream } from "@/lib/types";

const statusTone: Record<string, "neutral" | "flame" | "mint" | "rose" | "ember"> = {
  monitoring: "neutral",
  recording: "flame",
  recorded: "mint",
  stopped: "neutral",
  error: "rose",
};

export default function LivePage() {
  const { data, error, loading, refresh } = useApi<LiveStream[]>("/api/live-streams", { pollMs: 5000 });
  const [url, setUrl] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [actionId, setActionId] = React.useState<string | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await api.post("/api/live-streams", { url: url.trim(), title: title.trim() || null });
      setUrl("");
      setTitle("");
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
      toast("Recording stopped - the capture will finish processing", "info");
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
      <PageHeader
        eyebrow="Ingest"
        title="Live streams"
        description="Record a public live stream to disk, then let the normal transcription and clip pipeline run on the capture."
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
            {formError ? <Alert>{formError}</Alert> : null}
            <Button type="submit" loading={submitting} className="w-full">
              <Radio className="h-4 w-4" /> Add stream
            </Button>
            <p className="text-[11px] leading-relaxed text-faint">
              Recording requires yt-dlp. Streams are captured until you stop them; the file then enters the
              standard pipeline. Respect the creator's terms and platform rules.
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
                    <p className="mt-2 text-[11px] text-faint">
                      Added {formatDateTime(stream.created_at)}
                      {stream.started_at ? ` · started ${formatDateTime(stream.started_at)}` : ""}
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
