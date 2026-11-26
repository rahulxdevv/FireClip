"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";
import {
  Captions,
  Clock,
  FileText,
  Flame,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Scissors,
  Sparkles,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { PageHeader, Breadcrumb, SectionHeader, InlineProgress } from "@/components/shared";
import { ClipCard } from "@/components/clip-card";
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
  Tabs,
  Textarea,
} from "@/components/ui";
import { JobStatusBadge, VideoStatusBadge } from "@/components/status";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatBytes, formatDateTime, formatDuration, formatTimecode, relativeTime } from "@/lib/format";
import type { AIProvider, Clip, Job, Segment, Transcript, VideoDetail } from "@/lib/types";

interface EngineStatus {
  configured: string;
  diarization: string;
  engines: Record<string, { available: boolean; model: string; local: boolean; note: string | null }>;
}

export default function VideoDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const video = useApi<VideoDetail>(`/api/videos/${id}`, { pollMs: 3500 });
  const jobs = useApi<Job[]>(`/api/videos/${id}/jobs`, { pollMs: 2500 });
  const clips = useApi<Clip[]>(`/api/videos/${id}/clips`, { pollMs: 6000 });
  const transcript = useApi<Transcript>(`/api/videos/${id}/transcript`, {
    enabled: Boolean(video.data?.has_transcript),
  });
  const engines = useApi<EngineStatus>("/api/ai/transcription");
  const providers = useApi<AIProvider[]>("/api/ai/providers");
  const [tab, setTab] = React.useState("clips");
  const [transcribeOpen, setTranscribeOpen] = React.useState(false);
  const [analyzeOpen, setAnalyzeOpen] = React.useState(false);
  const [manualOpen, setManualOpen] = React.useState(false);
  const [renameOpen, setRenameOpen] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [editSegment, setEditSegment] = React.useState<Segment | null>(null);
  const playerRef = React.useRef<HTMLVideoElement>(null);
  const [titleDraft, setTitleDraft] = React.useState("");

  React.useEffect(() => {
    if (video.data) setTitleDraft(video.data.title);
  }, [video.data]);

  if (video.loading && !video.data) return <PageSkeleton />;
  if (!video.data) {
    return (
      <div className="space-y-4">
        <PageHeader title="Video" />
        <Alert title="Video unavailable">{video.error || "This video is not in your workspace."}</Alert>
        <Link href="/videos">
          <Button variant="outline" size="sm">Back to library</Button>
        </Link>
      </div>
    );
  }

  const data = video.data;
  const activeJob = (jobs.data || []).find((job) => job.status === "running" || job.status === "queued");
  const processing = ["uploaded", "downloading", "probing", "transcribing", "analyzing"].includes(data.status);

  function seek(ms: number) {
    const player = playerRef.current;
    if (!player) return;
    player.currentTime = ms / 1000;
    void player.play().catch(() => undefined);
  }

  async function runTranscription(form: { engine: string; language: string; force: boolean }) {
    setBusy("transcribe");
    try {
      await api.post(`/api/videos/${id}/transcribe`, {
        engine: form.engine,
        language: form.language || null,
        force: form.force,
      });
      toast("Transcription queued", "success");
      setTranscribeOpen(false);
      jobs.refresh();
      video.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function runAnalysis(form: { provider: string; target_duration_ms: number; clip_count: number; ignore_static: boolean }) {
    setBusy("analyze");
    try {
      await api.post(`/api/videos/${id}/analyze`, {
        ...form,
        replace_existing: true,
      });
      toast("Analysis queued", "success");
      setAnalyzeOpen(false);
      jobs.refresh();
      video.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function createManualClip(form: { start: number; end: number; title: string; aspect: string }) {
    setBusy("manual");
    try {
      await api.post(`/api/videos/${id}/clips`, {
        start_ms: Math.round(form.start * 1000),
        end_ms: Math.round(form.end * 1000),
        title: form.title || "Manual cut",
        aspect_ratio: form.aspect,
      });
      toast("Manual clip created", "success");
      setManualOpen(false);
      clips.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function saveTitle() {
    if (!titleDraft.trim() || titleDraft === data.title) {
      setRenameOpen(false);
      return;
    }
    try {
      await api.patch(`/api/videos/${id}`, { title: titleDraft.trim() });
      setRenameOpen(false);
      video.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  async function removeVideo() {
    if (!window.confirm(`Delete “${data.title}” and all of its clips? This cannot be undone.`)) return;
    setBusy("delete");
    try {
      await api.delete(`/api/videos/${id}`);
      toast("Video deleted", "success");
      router.push("/videos");
    } catch (err) {
      toast(errorMessage(err), "error");
      setBusy(null);
    }
  }

  async function retry() {
    setBusy("retry");
    try {
      await api.post(`/api/videos/${id}/retry`);
      video.refresh();
      jobs.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function saveSegment(segment: Segment, text: string, speakerId: string | null) {
    try {
      await api.patch(`/api/videos/${id}/transcript/segments/${segment.id}`, {
        text,
        speaker_id: speakerId,
      });
      toast("Transcript updated", "success");
      setEditSegment(null);
      transcript.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  async function renameSpeaker(speakerId: string, current: string) {
    const display = window.prompt("Speaker name", current);
    if (!display?.trim()) return;
    try {
      await api.patch(`/api/videos/${id}/transcript/speakers/${speakerId}`, { display_name: display.trim() });
      transcript.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  return (
    <div>
      <div className="mb-4">
        <Breadcrumb items={[{ label: "Video library", href: "/videos" }, { label: data.title }]} />
      </div>
      <PageHeader
        title={data.title}
        description={`${data.source_type === "upload" ? "Uploaded file" : `Imported from ${data.source_type}`}, ${formatDuration(data.duration_seconds)}, ${data.width}×${data.height}, ${formatBytes(data.size_bytes)}`}
        actions={
          <>
            <Button variant="ghost" size="sm" onClick={() => setRenameOpen(true)}>
              <Pencil className="h-3.5 w-3.5" /> Rename
            </Button>
            <Button variant="ghost" size="sm" onClick={removeVideo} loading={busy === "delete"}>
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setTranscribeOpen(true)}
              disabled={processing}
            >
              <Captions className="h-3.5 w-3.5" /> {data.has_transcript ? "Re-transcribe" : "Transcribe"}
            </Button>
            <Button
              size="sm"
              onClick={() => setAnalyzeOpen(true)}
              disabled={!data.has_transcript || processing}
            >
              <Sparkles className="h-3.5 w-3.5" /> Find clips
            </Button>
          </>
        }
      />

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <VideoStatusBadge status={data.status} />
        <Badge tone="neutral">{data.language.toUpperCase()}</Badge>
        {data.has_audio ? <Badge tone="neutral">audio</Badge> : <Badge tone="ember">no audio</Badge>}
        {data.analysis_provider ? <Badge tone="flame">{data.analysis_provider} analysis</Badge> : null}
        <span className="text-[11px] text-faint">Added {formatDateTime(data.created_at)}</span>
        {data.status === "error" ? (
          <Button size="sm" variant="outline" onClick={retry} loading={busy === "retry"}>
            <RefreshCw className="h-3 w-3" /> Retry processing
          </Button>
        ) : null}
      </div>

      {data.status === "error" ? (
        <Alert title="Processing stopped" className="mb-5">
          {data.error_message || "The pipeline failed without a message."}
        </Alert>
      ) : null}

      {(data.static_ranges || []).length ? (
        <Panel className="mb-5 flex flex-wrap items-start gap-3 p-4">
          <div className="min-w-0 flex-1">
            <p className="text-[12px] font-medium text-foreground">Still screens and ad breaks were skipped</p>
            <p className="mt-1 text-[11px] leading-relaxed text-faint">
              {formatDuration(data.static_screen_seconds || 0)} of near-frozen footage was found. 
              New clips are kept at least 65% outside these ranges.
            </p>
          </div>
          <div className="flex max-w-full flex-wrap gap-1.5">
            {(data.static_ranges || []).slice(0, 8).map((range) => (
              <span key={`${range.start_ms}-${range.end_ms}`} className="rounded-md border border-white/8 px-2 py-1 font-mono text-[10px] text-faint">
                {formatDuration(range.start_ms, true)}-{formatDuration(range.end_ms, true)}
              </span>
            ))}
          </div>
        </Panel>
      ) : null}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          <Panel className="overflow-hidden">
            <div className="relative bg-black">
              <video
                ref={playerRef}
                src={`/api/videos/${id}/stream`}
                poster={data.thumbnail_key ? `/api/videos/${id}/thumbnail` : undefined}
                controls
                preload="metadata"
                className="mx-auto max-h-[520px] w-full bg-black"
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/7 px-4 py-2.5 text-[11px] text-faint">
              <span className="font-mono">
                {data.fps ? `${data.fps.toFixed(1)} fps` : ""} {data.original_filename || ""}
              </span>
              {data.source_url ? (
                <a
                  href={data.source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="truncate text-flame-400 hover:text-flame-500"
                >
                  Original source ↗
                </a>
              ) : (
                <span>{formatBytes(data.size_bytes)}</span>
              )}
            </div>
          </Panel>

          <Panel>
            <div className="px-4 pt-1">
              <Tabs
                value={tab}
                onValueChange={setTab}
                tabs={[
                  { value: "clips", label: "Candidate clips", count: (clips.data || []).length },
                  { value: "transcript", label: "Transcript" },
                ]}
              />
            </div>

            {tab === "clips" ? (
              <div className="p-4">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <p className="text-[12px] text-faint">
                    Ranked by explainable signals. Regenerating analysis replaces suggested clips.
                  </p>
                  <Button size="sm" variant="ghost" onClick={() => setManualOpen(true)}>
                    <Plus className="h-3 w-3" /> Manual cut
                  </Button>
                </div>
                {(clips.data || []).length === 0 ? (
                  <EmptyState
                    icon={<Flame className="h-5 w-5" />}
                    title={data.has_transcript ? "No clips found yet" : "Transcribe first"}
                    description={
                      data.has_transcript
                        ? "Run AI analysis to find the strongest standalone moments."
                        : "FireClip needs a transcript before it can score moments."
                    }
                    action={
                      data.has_transcript ? (
                        <Button size="sm" onClick={() => setAnalyzeOpen(true)}>
                          <Sparkles className="h-3.5 w-3.5" /> Find clips
                        </Button>
                      ) : (
                        <Button size="sm" onClick={() => setTranscribeOpen(true)}>
                          <Captions className="h-3.5 w-3.5" /> Transcribe
                        </Button>
                      )
                    }
                  />
                ) : (
                  <div className="space-y-3">
                    {(clips.data || []).map((clip) => (
                      <ClipCard key={clip.id} clip={clip} onChanged={clips.refresh} compact />
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="max-h-[640px] overflow-y-auto">
                {!data.has_transcript ? (
                  <EmptyState
                    icon={<FileText className="h-5 w-5" />}
                    title="No transcript yet"
                    description="Choose a transcription engine. If none is configured, the job reports the requirement instead of inventing text."
                    action={
                      <Button size="sm" onClick={() => setTranscribeOpen(true)}>
                        Transcribe this video
                      </Button>
                    }
                  />
                ) : transcript.loading && !transcript.data ? (
                  <div className="p-4">
                    <PageSkeleton />
                  </div>
                ) : transcript.data ? (
                  <div>
                    <div className="flex flex-wrap items-center gap-2 border-b border-white/7 px-4 py-2.5">
                      <Badge tone="neutral">{transcript.data.language}</Badge>
                      <Badge tone="neutral">{transcript.data.engine}</Badge>
                      <span className="text-[10px] text-faint">
                        {transcript.data.word_count} words, {transcript.data.segments.length} segments
                      </span>
                      {transcript.data.speakers.length > 0 ? (
                        <div className="ml-auto flex flex-wrap gap-1.5">
                          {transcript.data.speakers.map((speaker) => (
                            <button
                              key={speaker.id}
                              onClick={() =>
                                renameSpeaker(speaker.id, speaker.display_name || speaker.label)
                              }
                              className="rounded border border-white/10 px-1.5 py-0.5 font-mono text-[9.5px] text-muted hover:text-paper"
                              title="Rename speaker"
                            >
                              {speaker.display_name || speaker.label}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    <div className="divide-y divide-white/5">
                      {transcript.data.segments.map((segment) => {
                        const speaker = transcript.data?.speakers.find((s) => s.id === segment.speaker_id);
                        return (
                          <div key={segment.id} className="group flex gap-3 px-4 py-2.5 hover:bg-white/2">
                            <button
                              onClick={() => seek(segment.start_ms)}
                              className="mt-0.5 shrink-0 font-mono text-[10px] text-flame-400 hover:text-flame-500"
                            >
                              {formatTimecode(segment.start_ms)}
                            </button>
                            <div className="min-w-0 flex-1">
                              {speaker ? (
                                <span className="mr-1.5 font-mono text-[9.5px] text-ember">
                                  {speaker.display_name || speaker.label}
                                </span>
                              ) : null}
                              <span className="text-[12.5px] leading-relaxed text-muted">{segment.text}</span>
                            </div>
                            <button
                              onClick={() => setEditSegment(segment)}
                              className="mt-0.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                              aria-label="Edit segment"
                            >
                              <Pencil className="h-3 w-3 text-faint hover:text-paper" />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <Alert className="m-4">{transcript.error || "Transcript unavailable."}</Alert>
                )}
              </div>
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel>
            <PanelHeader title="Pipeline" description="Stages recorded for this source." />
            <div className="space-y-3 px-4 py-4">
              <PipelineStep
                done={Boolean(data.duration_seconds)}
                active={["downloading", "probing"].includes(data.status)}
                label="Probe media"
                detail={`${data.width}×${data.height}, ${formatDuration(data.duration_seconds)}`}
              />
              <PipelineStep
                done={Boolean(data.has_transcript)}
                active={data.status === "transcribing" || activeJob?.kind === "transcription"}
                label="Transcribe"
                detail={
                  data.has_transcript
                    ? `${transcript.data?.word_count ?? 0} words, ${transcript.data?.engine ?? "stored"}`
                    : "Waiting for an engine"
                }
              />
              <PipelineStep
                done={(clips.data || []).length > 0}
                active={data.status === "analyzing" || activeJob?.kind === "analysis"}
                label="Find highlights"
                detail={
                  (clips.data || []).length > 0
                    ? `${clips.data?.length} candidates`
                    : "No analysis yet"
                }
              />
              <PipelineStep
                done={(clips.data || []).some((clip) => clip.status === "approved")}
                active={false}
                label="Clips & rendering"
                detail="Open a clip to edit and export"
              />
            </div>
            {activeJob ? (
              <div className="border-t border-white/7 px-4 py-3">
                <InlineProgress
                  value={activeJob.progress}
                  label={`${activeJob.kind}, ${activeJob.stage}`}
                  status={activeJob.status}
                />
              </div>
            ) : null}
          </Panel>

          <Panel>
            <PanelHeader title="Technical details" />
            <dl className="divide-y divide-white/6 text-[11.5px]">
              {[
                ["Duration", formatDuration(data.duration_seconds)],
                ["Resolution", `${data.width}×${data.height}`],
                ["Frame rate", data.fps ? `${data.fps.toFixed(2)} fps` : "-"],
                ["Audio", data.has_audio ? "yes" : "no"],
                ["Language", data.language],
                ["Segments", data.has_transcript ? String(transcript.data?.segments.length ?? "-") : "-"],
                ["Checksum", data.original_filename ? "stored" : "-"],
                ["Source", data.source_type],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between gap-3 px-4 py-2">
                  <dt className="text-faint">{label}</dt>
                  <dd className="text-right font-mono text-muted">{value}</dd>
                </div>
              ))}
            </dl>
          </Panel>

          <Panel>
            <PanelHeader
              title="Job history"
              action={
                <button onClick={() => jobs.refresh()} className="text-[11px] text-faint hover:text-paper">
                  Refresh
                </button>
              }
            />
            {(jobs.data || []).length === 0 ? (
              <p className="px-4 py-6 text-center text-[12px] text-faint">No jobs recorded.</p>
            ) : (
              <div className="max-h-64 divide-y divide-white/6 overflow-y-auto">
                {(jobs.data || []).slice(0, 8).map((job) => (
                  <div key={job.id} className="px-4 py-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11.5px] capitalize text-muted">{job.kind}</span>
                      <JobStatusBadge status={job.status} />
                    </div>
                    <p className="mt-0.5 font-mono text-[9.5px] text-faint">
                      {job.stage}, {relativeTime(job.created_at)}
                    </p>
                    {job.error_message ? (
                      <p className="mt-1 line-clamp-2 text-[10.5px] text-rose">{job.error_message}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel className="p-4">
            <div className="flex items-start gap-2.5">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-ember" />
              <p className="text-[11.5px] leading-relaxed text-faint">
                Scores rank editorial potential from transcript signals. They are not a guarantee of reach,
                and FireClip never uses audio loudness as a virality proxy.
              </p>
            </div>
          </Panel>
        </div>
      </div>

      <TranscribeDialog
        open={transcribeOpen}
        onOpenChange={setTranscribeOpen}
        engines={engines.data}
        busy={busy === "transcribe"}
        onSubmit={runTranscription}
      />
      <AnalyzeDialog
        open={analyzeOpen}
        onOpenChange={setAnalyzeOpen}
        providers={providers.data || []}
        busy={busy === "analyze"}
        onSubmit={runAnalysis}
        durationSeconds={data.duration_seconds}
      />
      <ManualClipDialog
        open={manualOpen}
        onOpenChange={setManualOpen}
        duration={data.duration_seconds}
        busy={busy === "manual"}
        onSubmit={createManualClip}
      />
      <RenameDialog
        open={renameOpen}
        onOpenChange={setRenameOpen}
        value={titleDraft}
        onChange={setTitleDraft}
        onSave={saveTitle}
      />
      <SegmentDialog
        segment={editSegment}
        speakers={transcript.data?.speakers || []}
        onClose={() => setEditSegment(null)}
        onSave={saveSegment}
      />
    </div>
  );
}

function PipelineStep({
  done,
  active,
  label,
  detail,
}: {
  done: boolean;
  active: boolean;
  label: string;
  detail: string;
}) {
  return (
    <div className="flex items-start gap-2.5">
      <span
        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border font-mono text-[8px] ${
          done
            ? "border-mint/40 bg-mint/10 text-mint"
            : active
              ? "border-flame-500/50 bg-flame-500/10 text-flame-400"
              : "border-white/12 text-faint"
        }`}
      >
        {done ? "✓" : active ? "•" : ""}
      </span>
      <div className="min-w-0">
        <p className={`text-[11.5px] ${done ? "text-muted" : "text-faint"}`}>{label}</p>
        <p className="font-mono text-[9.5px] text-faint">{detail}</p>
      </div>
    </div>
  );
}

function TranscribeDialog({
  open,
  onOpenChange,
  engines,
  busy,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  engines: EngineStatus | null;
  busy: boolean;
  onSubmit: (form: { engine: string; language: string; force: boolean }) => void;
}) {
  const [engine, setEngine] = React.useState("auto");
  const [language, setLanguage] = React.useState("");
  const [force, setForce] = React.useState(false);
  const options = engines
    ? Object.entries(engines.engines).filter(([, value]) => value.available)
    : [];
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Transcribe this video"
      description="Engines are detected on the server. Unavailable options are hidden rather than faked."
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button loading={busy} onClick={() => onSubmit({ engine, language, force })}>
            Start transcription
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Engine">
          <Select value={engine} onChange={(event) => setEngine(event.target.value)}>
            <option value="auto">Auto (best available)</option>
            {options.map(([key, value]) => (
              <option key={key} value={key}>
                {key}, {value.model}{value.local ? ", local" : ""}
              </option>
            ))}
          </Select>
        </Field>
        {engines ? (
          <div className="space-y-1.5">
            {Object.entries(engines.engines).map(([key, value]) => (
              <p key={key} className="flex items-start gap-2 text-[11px] leading-relaxed text-faint">
                <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${value.available ? "bg-mint" : "bg-ink-600"}`} />
                <span>
                  <span className="text-muted">{key}</span>
                  {value.note ? `, ${value.note}` : ", available"}
                </span>
              </p>
            ))}
          </div>
        ) : null}
        <Field label="Language" hint="Leave empty for automatic detection.">
          <Input value={language} onChange={(event) => setLanguage(event.target.value)} placeholder="en" maxLength={16} />
        </Field>
        <label className="flex items-center gap-2 text-[12px] text-muted">
          <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
          Replace an existing transcript
        </label>
      </div>
    </Dialog>
  );
}

function AnalyzeDialog({
  open,
  onOpenChange,
  providers,
  busy,
  onSubmit,
  durationSeconds,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  providers: AIProvider[];
  busy: boolean;
  onSubmit: (form: { provider: string; target_duration_ms: number; clip_count: number; ignore_static: boolean }) => void;
  durationSeconds: number;
}) {
  const [provider, setProvider] = React.useState("auto");
  const [duration, setDuration] = React.useState(45);
  const [count, setCount] = React.useState(6);
  const [ignoreStatic, setIgnoreStatic] = React.useState(false);
  const configured = providers.filter((item) => item.provider !== "heuristic" && item.configured && item.enabled);
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Find clip candidates"
      description="Choose how long the clips should be. Analysis replaces unapproved suggestions."
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            loading={busy}
            onClick={() => onSubmit({ provider, target_duration_ms: duration * 1000, clip_count: count, ignore_static: ignoreStatic })}
          >
            Run analysis
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Engine">
          <Select value={provider} onChange={(event) => setProvider(event.target.value)}>
            <option value="auto">Auto (your default provider, else built-in signals)</option>
            <option value="heuristic">Built-in signal engine (offline)</option>
            {configured.map((item) => (
              <option key={item.provider} value={item.provider}>
                {item.label}, {item.model}
              </option>
            ))}
          </Select>
        </Field>
        <div>
          <p className="mb-1.5 text-[13px] font-medium text-muted">Target clip length</p>
          <div className="grid grid-cols-6 gap-1.5">
            {[15, 30, 45, 60, 90].map((seconds) => (
              <button
                key={seconds}
                type="button"
                onClick={() => setDuration(seconds)}
                className={`rounded-lg border py-2 text-[11.5px] transition-colors ${
                  duration === seconds
                    ? "border-flame-500/50 bg-flame-500/10 text-flame-400"
                    : "border-white/8 text-muted hover:border-white/18"
                }`}
              >
                {seconds}s
              </button>
            ))}
            <div className="col-span-1">
              <Input
                type="number"
                min={5}
                max={180}
                value={duration}
                onChange={(event) => setDuration(Math.max(5, Math.min(180, Number(event.target.value) || 45)))}
                className="h-full text-center text-[11.5px]"
                aria-label="Custom duration in seconds"
              />
            </div>
          </div>
          <p className="mt-1.5 text-[10.5px] text-faint">
            Source is {formatDuration(durationSeconds)} long. Very long targets can yield one clip.
          </p>
        </div>
        <Field label={`Number of candidates (${count})`}>
          <input
            type="range"
            min={1}
            max={12}
            value={count}
            onChange={(event) => setCount(Number(event.target.value))}
            className="w-full"
          />
        </Field>
        <label className="flex items-start gap-2 rounded-lg border border-white/8 bg-ink-850/60 px-3 py-2 text-[11px] text-muted">
          <input
            type="checkbox"
            checked={ignoreStatic}
            onChange={(event) => setIgnoreStatic(event.target.checked)}
            className="mt-0.5 h-3.5 w-3.5 accent-orange-500"
          />
          <span>
            Keep moments on still screens, slates or ad cards. Normally those are skipped because they
            make weak clips.
          </span>
        </label>
        <Alert tone="info">
          Every candidate includes a score breakdown and a written explanation. Loudness is not a signal.
        </Alert>
      </div>
    </Dialog>
  );
}

function ManualClipDialog({
  open,
  onOpenChange,
  duration,
  busy,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  duration: number;
  busy: boolean;
  onSubmit: (form: { start: number; end: number; title: string; aspect: string }) => void;
}) {
  const [start, setStart] = React.useState(0);
  const [end, setEnd] = React.useState(Math.min(45, Math.max(5, duration)));
  const [title, setTitle] = React.useState("");
  const [aspect, setAspect] = React.useState("9:16");
  React.useEffect(() => {
    if (open) {
      setStart(0);
      setEnd(Math.min(45, Math.max(5, Math.round(duration))));
    }
  }, [open, duration]);
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Create a manual clip"
      description="Pick exact boundaries. You can refine them again in the editor."
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            loading={busy}
            onClick={() => onSubmit({ start, end, title, aspect })}
            disabled={end <= start}
          >
            Create clip
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Start (seconds)">
            <Input
              type="number"
              min={0}
              max={duration}
              step={0.1}
              value={start}
              onChange={(event) => setStart(Number(event.target.value) || 0)}
            />
          </Field>
          <Field label="End (seconds)">
            <Input
              type="number"
              min={0}
              max={duration}
              step={0.1}
              value={end}
              onChange={(event) => setEnd(Number(event.target.value) || 0)}
            />
          </Field>
        </div>
        <p className="font-mono text-[10.5px] text-faint">
          {formatTimecode(start * 1000)} to {formatTimecode(end * 1000)}, {Math.max(0, end - start).toFixed(1)}s
        </p>
        <Field label="Title">
          <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Manual cut" />
        </Field>
        <Field label="Aspect ratio">
          <Select value={aspect} onChange={(event) => setAspect(event.target.value)}>
            <option value="9:16">9:16 vertical</option>
            <option value="1:1">1:1 square</option>
            <option value="4:5">4:5 portrait</option>
            <option value="16:9">16:9 landscape</option>
          </Select>
        </Field>
      </div>
    </Dialog>
  );
}

function RenameDialog({
  open,
  onOpenChange,
  value,
  onChange,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Rename video"
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={onSave}>Save</Button>
        </>
      }
    >
      <Field label="Title">
        <Input value={value} onChange={(event) => onChange(event.target.value)} maxLength={300} />
      </Field>
    </Dialog>
  );
}

function SegmentDialog({
  segment,
  speakers,
  onClose,
  onSave,
}: {
  segment: Segment | null;
  speakers: { id: string; label: string; display_name: string | null }[];
  onClose: () => void;
  onSave: (segment: Segment, text: string, speakerId: string | null) => void;
}) {
  const [text, setText] = React.useState("");
  const [speakerId, setSpeakerId] = React.useState<string>("");
  React.useEffect(() => {
    if (segment) {
      setText(segment.text);
      setSpeakerId(segment.speaker_id || "");
    }
  }, [segment]);
  if (!segment) return null;
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Edit transcript segment"
      description="Edited text no longer has word-level timings, so captions fall back to an even split."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => onSave(segment, text, speakerId || null)}>Save segment</Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="font-mono text-[10.5px] text-faint">
          <Clock className="mr-1 inline h-3 w-3" />
          {formatTimecode(segment.start_ms)} → {formatTimecode(segment.end_ms)}
        </p>
        <Field label="Text">
          <Textarea value={text} onChange={(event) => setText(event.target.value)} rows={5} />
        </Field>
        {speakers.length > 0 ? (
          <Field label="Speaker">
            <Select value={speakerId} onChange={(event) => setSpeakerId(event.target.value)}>
              <option value="">Unassigned</option>
              {speakers.map((speaker) => (
                <option key={speaker.id} value={speaker.id}>
                  {speaker.display_name || speaker.label}
                </option>
              ))}
            </Select>
          </Field>
        ) : null}
      </div>
    </Dialog>
  );
}
