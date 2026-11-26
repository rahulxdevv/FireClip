"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";
import {
  ArrowLeft,
  Check,
  Download,
  Image as ImageIcon,
  Layers,
  Loader2,
  Merge,
  Music,
  Redo2,
  Scissors,
  Sparkles,
  Trash2,
  Undo2,
  Upload,
  Volume2,
  Wand2,
} from "lucide-react";
import { Breadcrumb, PageHeader } from "@/components/shared";
import { PreviewPlayer } from "@/components/preview-player";
import { FramingPreview, Timeline } from "@/components/editor/timeline";
import {
  Alert,
  Badge,
  Button,
  Dialog,
  Field,
  Input,
  PageSkeleton,
  Panel,
  PanelHeader,
  Progress,
  Select,
  Switch,
  Tabs,
  Textarea,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { aspectSize, formatDuration, formatTimecode } from "@/lib/format";
import type {
  CaptionStyle,
  Clip,
  EditorProject,
  Overlay,
  RenderJob,
  Segment,
} from "@/lib/types";

type AudioDraft = { volume?: number; muted?: boolean; fade_in?: number; fade_out?: number };

interface Draft {
  name: string;
  aspect_ratio: string;
  width: number;
  height: number;
  trim_start_ms: number;
  trim_end_ms: number;
  focus_x: number;
  focus_y: number;
  caption_style_id: string | null;
  captions_enabled: boolean;
  caption_overrides: Record<string, unknown>;
  caption_translation: EditorProject["caption_translation"];
  layout: NonNullable<EditorProject["layout"]>;
  overlays: Overlay[];
  music: { asset_key?: string; volume?: number; name?: string } | null;
  audio: AudioDraft;
  operations: unknown[];
}

const TRANSLATION_LANGUAGES = [
  ["en", "English"], ["es", "Spanish"], ["fr", "French"], ["de", "German"],
  ["pt", "Portuguese"], ["it", "Italian"], ["nl", "Dutch"], ["hi", "Hindi"],
  ["ur", "Urdu"], ["bn", "Bengali"], ["ar", "Arabic"], ["tr", "Turkish"],
  ["id", "Indonesian"], ["ja", "Japanese"], ["ko", "Korean"], ["zh", "Chinese (Simplified)"],
  ["ru", "Russian"], ["vi", "Vietnamese"], ["th", "Thai"], ["pl", "Polish"],
];

const PRESETS = [
  { id: "tiktok", label: "TikTok", size: "1080×1920", aspect: "9:16" },
  { id: "reels", label: "Reels", size: "1080×1920", aspect: "9:16" },
  { id: "shorts", label: "Shorts", size: "1080×1920", aspect: "9:16" },
  { id: "square", label: "Square", size: "1080×1080", aspect: "1:1" },
  { id: "landscape", label: "Landscape", size: "1920×1080", aspect: "16:9" },
  { id: "portrait", label: "Portrait", size: "1080×1350", aspect: "4:5" },
];

function toDraft(project: EditorProject): Draft {
  return {
    name: project.name,
    aspect_ratio: project.aspect_ratio,
    width: project.width,
    height: project.height,
    trim_start_ms: project.trim_start_ms,
    trim_end_ms: project.trim_end_ms,
    focus_x: project.focus_x,
    focus_y: project.focus_y,
    caption_style_id: project.caption_style_id,
    captions_enabled: project.captions_enabled,
    caption_overrides: { ...(project.caption_overrides || {}) },
    caption_translation: { ...(project.caption_translation || {}) },
    layout: {
      mode: "fill",
      position: "bottom_right",
      size: 0.4,
      x: 0.96,
      y: 0.96,
      ...(project.layout || {}),
    },
    overlays: (project.overlays || []).map((overlay) => ({ ...overlay })),
    music: project.music ? { ...project.music } : null,
    audio: { ...(project.audio || {}) },
    operations: [],
  };
}

export default function EditorPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const detail = useApi<EditorProject>(`/api/editors/${id}`);
  const styles = useApi<CaptionStyle[]>("/api/caption-styles");
  const siblings = useApi<Clip[] | null>(
    detail.data ? `/api/clips?video_id=${detail.data.video_id}` : null,
  );
  const [draftState, setDraft] = React.useState<Draft | null>(null);
  const [tab, setTab] = React.useState("frame");
  const [playhead, setPlayhead] = React.useState(0);
  const [saving, setSaving] = React.useState(false);
  const [saveError, setSaveError] = React.useState<string | null>(null);
  const [savedAt, setSavedAt] = React.useState<Date | null>(null);
  const [renderId, setRenderId] = React.useState<string | null>(null);
  const [preset, setPreset] = React.useState("tiktok");
  const [format, setFormat] = React.useState("mp4");
  const [rendering, setRendering] = React.useState(false);
  const [splitOpen, setSplitOpen] = React.useState(false);
  const [mergeOpen, setMergeOpen] = React.useState(false);
  const [mergeId, setMergeId] = React.useState("");
  const [merging, setMerging] = React.useState(false);
  const [uploading, setUploading] = React.useState<string | null>(null);
  const [focusBusy, setFocusBusy] = React.useState(false);
  const [templateOpen, setTemplateOpen] = React.useState(false);
  const [templateName, setTemplateName] = React.useState("");
  const [savingTemplate, setSavingTemplate] = React.useState(false);
  const [includeLook, setIncludeLook] = React.useState(true);
  const [translationLanguage, setTranslationLanguage] = React.useState("en");
  const [translating, setTranslating] = React.useState(false);

  const history = React.useRef<Draft[]>([]);
  const future = React.useRef<Draft[]>([]);
  const initialized = React.useRef(false);
  const draftRef = React.useRef<Draft | null>(null);
  const saveTimer = React.useRef<number | null>(null);
  const lastSaved = React.useRef<string>("");

  React.useEffect(() => {
    if (detail.data && !initialized.current) {
      const next = toDraft(detail.data);
      setDraft(next);
      draftRef.current = next;
      lastSaved.current = JSON.stringify(next);
      initialized.current = true;
      setPreset(PRESETS.find((item) => item.aspect === detail.data?.aspect_ratio)?.id || "tiktok");
      const render = detail.data.latest_render;
      if (render && ["queued", "running"].includes(render.status)) setRenderId(render.id);
    }
  }, [detail.data]);

  const renderJob = useApi<RenderJob>(renderId ? `/api/renders/${renderId}` : null, {
    pollMs: 2000,
    enabled: Boolean(renderId),
  });

  React.useEffect(() => {
    if (renderJob.data?.status === "completed") {
      toast("Render complete", "success", "The export is ready in your library.");
      setRenderId(null);
      setRendering(false);
      detail.refresh();
    }
    if (renderJob.data?.status === "failed") {
      setRendering(false);
    }
  }, [renderJob.data?.status, detail]);

  const apply = React.useCallback((patch: Partial<Draft>, recordHistory = true) => {
    setDraft((current) => {
      if (!current) return current;
      if (recordHistory) {
        history.current = [...history.current, structuredClone(current)].slice(-40);
        future.current = [];
      }
      const next = { ...current, ...patch };
      draftRef.current = next;
      return next;
    });
  }, []);

  React.useEffect(() => {
    if (!draftState || !initialized.current) return;
    const serialized = JSON.stringify(draftState);
    if (serialized === lastSaved.current) return;
    setSaving(true);
    if (saveTimer.current) window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(async () => {
      try {
        await api.patch(`/api/editors/${id}`, {
          ...draftState,
          music: draftState.music,
          operations: [],
        });
        lastSaved.current = serialized;
        setSavedAt(new Date());
        setSaveError(null);
      } catch (err) {
        setSaveError(errorMessage(err));
      } finally {
        setSaving(false);
      }
    }, 700);
    return () => {
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
    };
  }, [draftState, id]);

  React.useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey)) return;
      if (event.key.toLowerCase() === "z" && !event.shiftKey) {
        event.preventDefault();
        undo();
      } else if (event.key.toLowerCase() === "z" && event.shiftKey) {
        event.preventDefault();
        redo();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function undo() {
    const previous = history.current.pop();
    if (!previous || !draftState) return;
    future.current = [...future.current, structuredClone(draftState)];
    setDraft(previous);
    draftRef.current = previous;
  }

  function redo() {
    const next = future.current.pop();
    if (!next || !draftState) return;
    history.current = [...history.current, structuredClone(draftState)];
    setDraft(next);
    draftRef.current = next;
  }

  if (detail.loading && !draftState) return <PageSkeleton />;
  if (!detail.data || !draftState) {
    return (
      <div className="space-y-4">
        <PageHeader title="Editor" />
        <Alert title="Project unavailable">{detail.error || "This editing project does not exist."}</Alert>
        <Link href="/clips">
          <Button variant="outline" size="sm">Back to clips</Button>
        </Link>
      </div>
    );
  }

  const project = detail.data;
  const draft = draftState;
  const videoId = project.video_id;
  const durationMs = Math.round((project.video_duration_seconds || 0) * 1000);
  const segments = (project.transcript?.segments || []).filter(
    (segment: Segment) => segment.end_ms > draft.trim_start_ms && segment.start_ms < draft.trim_end_ms,
  );
  const translatedSegments = (draft.caption_translation.segments || []).map((segment, index) => ({
    id: `translated-${index}`,
    start_ms: segment.start_ms,
    end_ms: segment.end_ms,
    text: segment.text,
    speaker_id: null,
    confidence: 1,
    words: [],
  }));
  const captionSegments = translatedSegments.length ? translatedSegments : segments;
  const overrides = draft.caption_overrides as Record<string, string | number | boolean>;
  const durationSeconds = Math.max(0.5, (draft.trim_end_ms - draft.trim_start_ms) / 1000);
  const siblingClips = (siblings.data || []).filter((clip) => clip.id !== project.clip_id);

  async function uploadAsset(file: File, kind: "image" | "music") {
    setUploading(kind);
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    try {
      const asset = await api.upload<{ key: string; name: string; url: string; size: number }>(
        "/api/assets",
        form,
      );
      if (kind === "music") {
        apply({ music: { asset_key: asset.key, name: asset.name, volume: draft?.music?.volume ?? 0.22 } });
      } else {
        const overlay: Overlay = {
          id: crypto.randomUUID(),
          type: "image",
          asset_key: asset.key,
          start_ms: 0,
          end_ms: Math.min(4000, draft.trim_end_ms - draft.trim_start_ms),
          x: 0.5,
          y: 0.18,
          width: 0.3,
        };
        apply({ overlays: [...draft.overlays, overlay] });
      }
      toast(`${kind === "music" ? "Music" : "Image"} uploaded`, "success");
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setUploading(null);
    }
  }

  async function detectFace() {
    setFocusBusy(true);
    try {
      const result = await api.post<{
        focus_x: number;
        focus_y: number;
        camera_x: number;
        camera_y: number;
        camera_w: number;
        camera_h: number;
        faces_detected: number;
      }>(`/api/editors/${id}/auto-focus`);
      apply({
        focus_x: result.focus_x,
        focus_y: result.focus_y,
        layout: {
          ...draft.layout,
          camera_x: result.camera_x,
          camera_y: result.camera_y,
          camera_w: result.camera_w,
          camera_h: result.camera_h,
        },
      });
      toast("Subject framed", "success", `${result.faces_detected} face detections used.`);
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setFocusBusy(false);
    }
  }

  async function translateCaptions() {
    setTranslating(true);
    try {
      const result = await api.post<EditorProject["caption_translation"]>(
        `/api/editors/${id}/translate-captions`,
        { language: translationLanguage },
      );
      apply({ caption_translation: result });
      toast(
        `Captions translated to ${result.language_name || translationLanguage}`,
        "success",
        "Render again to burn the translated captions into the clip.",
      );
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setTranslating(false);
    }
  }

  async function clearTranslation() {
    setTranslating(true);
    try {
      await api.delete(`/api/editors/${id}/translate-captions`);
      apply({ caption_translation: {} });
      toast("Translated captions cleared", "info");
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setTranslating(false);
    }
  }

  async function render() {
    setRendering(true);
    try {
      const job = await api.post<RenderJob>(`/api/editors/${id}/render`, { preset, format });
      setRenderId(job.id);
      toast("Render queued", "success");
    } catch (err) {
      toast(errorMessage(err), "error");
      setRendering(false);
    }
  }

  async function splitClip() {
    const splitAt = Math.round(
      Math.min(draft.trim_end_ms - 500, Math.max(draft.trim_start_ms + 500, playhead)),
    );
    try {
      await api.post(`/api/videos/${videoId}/clips`, {
        start_ms: draft.trim_start_ms,
        end_ms: splitAt,
        title: `${draft.name} (part 1)`,
        aspect_ratio: draft.aspect_ratio,
      });
      await api.post(`/api/videos/${videoId}/clips`, {
        start_ms: splitAt,
        end_ms: draft.trim_end_ms,
        title: `${draft.name} (part 2)`,
        aspect_ratio: draft.aspect_ratio,
      });
      if (project.clip_id) {
        await api.patch(`/api/clips/${project.clip_id}`, { status: "rejected" });
      }
      toast("Split into two clips", "success", "Both parts are in the clip review list.");
      setSplitOpen(false);
      router.push(`/videos/${videoId}`);
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  async function mergeClip() {
    if (!mergeId) return;
    setMerging(true);
    try {
      const ids = project.clip_id ? [project.clip_id, mergeId] : [mergeId];
      const merged = await api.post<Clip>("/api/clips/merge", { clip_ids: ids });
      const editor = await api.post<EditorProject>(`/api/clips/${merged.id}/editor`, {});
      toast("Clips merged", "success");
      setMergeOpen(false);
      router.push(`/editor/${editor.id}`);
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setMerging(false);
    }
  }

  function addTextOverlay() {
    const overlay: Overlay = {
      id: crypto.randomUUID(),
      type: "text",
      text: "New overlay",
      start_ms: 0,
      end_ms: Math.min(3000, draft.trim_end_ms - draft.trim_start_ms),
      x: 0.5,
      y: 0.18,
      font_size: 56,
      color: "#ffffff",
    };
    apply({ overlays: [...draft.overlays, overlay] });
  }

  function updateOverlay(overlayId: string | undefined, patch: Partial<Overlay>) {
    apply({
      overlays: draft.overlays.map((overlay) =>
        overlay.id === overlayId ? { ...overlay, ...patch } : overlay,
      ),
    });
  }

  function removeOverlay(overlayId: string | undefined) {
    apply({ overlays: draft.overlays.filter((overlay) => overlay.id !== overlayId) });
  }

  const activeStyle = (styles.data || []).find((style) => style.id === draft.caption_style_id);
  const activeConfig = (activeStyle?.config || {}) as Record<string, unknown>;
  const captionPreview = {
    textColor: String(overrides.text_color || activeConfig.text_color || "#ffffff"),
    highlightColor: String(overrides.highlight_color || activeConfig.highlight_color || "#ff6a1f"),
    uppercase: Boolean(overrides.uppercase ?? activeConfig.uppercase ?? false),
    position: String(overrides.position || activeConfig.position || "bottom"),
    box: Boolean(overrides.box ?? activeConfig.box ?? true),
    font: String(overrides.font || activeConfig.font || "inherit"),
    fontSize: Number(overrides.font_size || activeConfig.font_size || 64),
    boxColor: String(overrides.box_color || activeConfig.box_color || "#0b0b0f"),
    boxOpacity: Number(overrides.box_opacity ?? activeConfig.box_opacity ?? 0.28),
    italic: Boolean(overrides.italic ?? activeConfig.italic ?? false),
    letterSpacing: Number(overrides.letter_spacing ?? activeConfig.letter_spacing ?? 0),
    heading: String(overrides.heading || activeConfig.heading || ""),
    headingEnabled: Boolean(overrides.heading_enabled ?? activeConfig.heading_enabled ?? true),
    headingColor: String(overrides.heading_color || activeConfig.heading_color || "#ffffff"),
    headingSize: Number(overrides.heading_size || activeConfig.heading_size || 54),
    headingUppercase: Boolean(overrides.heading_uppercase ?? activeConfig.heading_uppercase ?? false),
  };

  function applyCaptionStyle(style: CaptionStyle) {
    const config = (style.config || {}) as Record<string, unknown>;
    const look = includeLook ? (config.look as Partial<Draft> | undefined) : undefined;
    const patch: Partial<Draft> = { caption_style_id: style.id, caption_overrides: {} };
    if (look && typeof look === "object") {
      if (look.layout) patch.layout = { ...draft.layout, ...look.layout };
      if (Array.isArray(look.overlays)) patch.overlays = look.overlays;
      if (look.music !== undefined) patch.music = look.music;
      if (look.audio) patch.audio = { ...draft.audio, ...look.audio };
      if (typeof look.focus_x === "number") patch.focus_x = look.focus_x;
      if (typeof look.focus_y === "number") patch.focus_y = look.focus_y;
      if (typeof look.captions_enabled === "boolean") patch.captions_enabled = look.captions_enabled;
    }
    apply(patch);
  }

  async function deleteCaptionStyle(style: CaptionStyle) {
    if (!window.confirm(`Delete the preset "${style.name}"? Existing projects keep their current look.`)) return;
    try {
      await api.delete(`/api/caption-styles/${style.id}`);
      if (draft.caption_style_id === style.id) {
        apply({ caption_style_id: null, caption_overrides: {} });
      }
      await styles.refresh();
      toast("Preset deleted", "success");
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  async function saveTemplate() {
    const name = templateName.trim();
    if (!name) return;
    setSavingTemplate(true);
    try {
      const look = {
        layout: draft.layout,
        overlays: draft.overlays,
        music: draft.music,
        audio: draft.audio,
        focus_x: draft.focus_x,
        focus_y: draft.focus_y,
        captions_enabled: draft.captions_enabled,
      };
      await api.post("/api/caption-styles", {
        name,
        config: { ...activeConfig, ...overrides, look: includeLook ? look : undefined },
      });
      await styles.refresh();
      setTemplateOpen(false);
      setTemplateName("");
      toast(includeLook ? "Full look saved" : "Caption template saved", "success");
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setSavingTemplate(false);
    }
  }
  return (
    <div>
      <div className="mb-4">
        <Breadcrumb
          items={[
            { label: "Clip discovery", href: "/clips" },
            { label: project.video_title || "Video", href: `/videos/${videoId}` },
            { label: draft.name },
          ]}
        />
      </div>

      <PageHeader
        title={draft.name}
        description={`${formatDuration(durationSeconds)} selected, ${draft.width}×${draft.height}, ${draft.audio.muted ? "audio muted" : "audio on"}`}
        actions={
          <>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" onClick={undo} disabled={history.current.length === 0} title="Undo">
                <Undo2 className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" onClick={redo} disabled={future.current.length === 0} title="Redo">
                <Redo2 className="h-4 w-4" />
              </Button>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setSplitOpen(true)}>
              <Scissors className="h-3.5 w-3.5" /> Split
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setMergeOpen(true)}
              disabled={siblingClips.length === 0}
            >
              <Merge className="h-3.5 w-3.5" /> Merge
            </Button>
            <Button variant="outline" size="sm" onClick={() => router.push(`/videos/${videoId}`)}>
              <ArrowLeft className="h-3.5 w-3.5" /> Source
            </Button>
            <Button size="sm" onClick={render} loading={rendering}>
              <Download className="h-3.5 w-3.5" /> Render
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 text-[11px]">
        {saving ? (
          <span className="flex items-center gap-1.5 text-faint">
            <Loader2 className="h-3 w-3 animate-spin" /> Saving…
          </span>
        ) : savedAt ? (
          <span className="flex items-center gap-1.5 text-faint">
            <Check className="h-3 w-3 text-mint" /> Saved {savedAt.toLocaleTimeString()}
          </span>
        ) : (
          <span className="text-faint">Changes save automatically</span>
        )}
        {saveError ? <span className="text-rose">{saveError}</span> : null}
        <Badge tone="neutral">{project.transcript ? `${project.transcript.segments.length} transcript segments` : "no transcript"}</Badge>
        {renderJob.data ? (
          <Badge tone={renderJob.data.status === "completed" ? "mint" : renderJob.data.status === "failed" ? "rose" : "flame"}>
            render {renderJob.data.status}
          </Badge>
        ) : null}
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px]">
            <Panel className="p-3">
              <PreviewPlayer
                src={`/api/videos/${videoId}/stream`}
                trimStartMs={draft.trim_start_ms}
                trimEndMs={draft.trim_end_ms}
                aspect={draft.aspect_ratio}
                captions={captionSegments}
                captionStyle={captionPreview}
                onTimeUpdate={(ms) => setPlayhead(ms)}
              />
              <p className="mt-2 px-1 text-[10.5px] text-faint">
                Preview approximates the burned captions and crop. The rendered file is produced by FFmpeg + libass.
              </p>
            </Panel>
            <div className="space-y-2">
              <p className="label-caps">Framing</p>
              <FramingPreview
                src={`/api/videos/${videoId}/stream`}
                aspect={draft.aspect_ratio}
                focusX={draft.focus_x}
                focusY={draft.focus_y}
                layout={draft.layout}
              />
              <p className="font-mono text-[9.5px] leading-relaxed text-faint">
                crop {draft.width}×{draft.height}
              </p>
            </div>
          </div>

          <Panel className="p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-[12px] font-medium">Timeline</p>
              <span className="font-mono text-[10px] text-faint">
                playhead {formatTimecode(playhead)}
              </span>
            </div>
            <Timeline
              durationMs={durationMs || draft.trim_end_ms}
              startMs={draft.trim_start_ms}
              endMs={draft.trim_end_ms}
              playheadMs={playhead}
              segments={project.transcript?.segments || []}
              onChange={(start, end) => apply({ trim_start_ms: start, trim_end_ms: end })}
              onSeek={(ms) => {
                setPlayhead(ms);
                const video = document.querySelector("video");
                if (video) video.currentTime = ms / 1000;
              }}
            />
          </Panel>

          <Panel>
            <PanelHeader title="Transcript in range" description="Edit transcript text from the source video page." />
            <div className="max-h-56 overflow-y-auto divide-y divide-white/5">
              {segments.length === 0 ? (
                <p className="px-4 py-6 text-center text-[12px] text-faint">No transcript segments overlap this range.</p>
              ) : (
                segments.map((segment) => (
                  <button
                    key={segment.id}
                    onClick={() => {
                      setPlayhead(segment.start_ms);
                      const video = document.querySelector("video");
                      if (video) video.currentTime = segment.start_ms / 1000;
                    }}
                    className="flex w-full gap-3 px-4 py-2 text-left hover:bg-white/2"
                  >
                    <span className="mt-0.5 shrink-0 font-mono text-[10px] text-flame-400">
                      {formatTimecode(segment.start_ms)}
                    </span>
                    <span className="text-[12px] leading-relaxed text-muted">{segment.text}</span>
                  </button>
                ))
              )}
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel>
            <div className="px-3 pt-2">
              <Tabs
                value={tab}
                onValueChange={setTab}
                tabs={[
                  { value: "frame", label: "Frame" },
                  { value: "captions", label: "Captions" },
                  { value: "audio", label: "Audio" },
                  { value: "overlays", label: "Overlays" },
                  { value: "export", label: "Export" },
                ]}
              />
            </div>

            {tab === "frame" ? (
              <div className="space-y-4 p-4">
                <Field label="Project name">
                  <Input value={draft.name} onChange={(event) => apply({ name: event.target.value })} maxLength={160} />
                </Field>
                <Field label="Aspect ratio">
                  <Select
                    value={draft.aspect_ratio}
                    onChange={(event) => {
                      const aspect = event.target.value;
                      const size = aspect === "custom"
                        ? { width: draft.width, height: draft.height }
                        : aspectSize(aspect);
                      apply({ aspect_ratio: aspect, width: size.width, height: size.height });
                    }}
                  >
                    <option value="9:16">9:16 vertical</option>
                    <option value="1:1">1:1 square</option>
                    <option value="4:5">4:5 portrait</option>
                    <option value="16:9">16:9 landscape</option>
                    <option value="custom">Custom</option>
                  </Select>
                </Field>
                {draft.aspect_ratio === "custom" ? (
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Width">
                      <Input
                        type="number"
                        min={240}
                        max={3840}
                        value={draft.width}
                        onChange={(event) => apply({ width: Number(event.target.value) || 1080 })}
                      />
                    </Field>
                    <Field label="Height">
                      <Input
                        type="number"
                        min={240}
                        max={3840}
                        value={draft.height}
                        onChange={(event) => apply({ height: Number(event.target.value) || 1920 })}
                      />
                    </Field>
                  </div>
                ) : null}
                <div className="space-y-3 rounded-lg border border-white/8 bg-ink-850/60 p-3">
                  <Field label="Layout">
                    <Select
                      value={draft.layout.mode || "fill"}
                      onChange={(event) =>
                        apply({ layout: { ...draft.layout, mode: event.target.value as "fill" | "fit" | "facecam" | "gameplay" } })
                      }
                    >
                      <option value="fill">Fill the screen</option>
                      <option value="fit">Fit with blurred background</option>
                      <option value="gameplay">Gameplay + camera</option>
                      <option value="facecam">Camera on blurred background</option>
                    </Select>
                  </Field>
                  {draft.layout.mode === "facecam" || draft.layout.mode === "gameplay" ? (
                    <>
                      <Field label="Camera position">
                        <Select
                          value={draft.layout.position || "bottom_right"}
                          onChange={(event) => apply({ layout: { ...draft.layout, position: event.target.value } })}
                        >
                          <option value="bottom_right">Bottom right</option>
                          <option value="bottom_left">Bottom left</option>
                          <option value="bottom_center">Bottom center</option>
                          <option value="bottom_half">Bottom half</option>
                          <option value="top_right">Top right</option>
                          <option value="top_left">Top left</option>
                          <option value="manual">Manual position</option>
                        </Select>
                      </Field>
                      <label className="flex items-center gap-2 text-[11px] text-faint">
                        <span className="w-14">Size</span>
                        <input
                          type="range"
                          min={0.15}
                          max={0.8}
                          step={0.01}
                          value={draft.layout.size ?? 0.4}
                          onChange={(event) => apply({ layout: { ...draft.layout, size: Number(event.target.value) } })}
                          className="flex-1"
                        />
                        <span className="w-8 text-right font-mono">{Math.round((draft.layout.size ?? 0.4) * 100)}%</span>
                      </label>
                      {draft.layout.position === "manual" ? (
                        <div className="grid grid-cols-2 gap-2">
                          <label className="flex items-center gap-2 text-[11px] text-faint">
                            <span>X</span>
                            <input
                              type="range"
                              min={0}
                              max={1}
                              step={0.01}
                              value={draft.layout.x ?? 0.96}
                              onChange={(event) => apply({ layout: { ...draft.layout, x: Number(event.target.value) } })}
                              className="flex-1"
                            />
                          </label>
                          <label className="flex items-center gap-2 text-[11px] text-faint">
                            <span>Y</span>
                            <input
                              type="range"
                              min={0}
                              max={1}
                              step={0.01}
                              value={draft.layout.y ?? 0.96}
                              onChange={(event) => apply({ layout: { ...draft.layout, y: Number(event.target.value) } })}
                              className="flex-1"
                            />
                          </label>
                        </div>
                      ) : null}
                      <div className="grid grid-cols-2 gap-2">
                        {([
                          ["camera_x", "Source X"],
                          ["camera_y", "Source Y"],
                          ["camera_w", "Source W"],
                          ["camera_h", "Source H"],
                        ] as const).map(([key, label]) => (
                          <label key={key} className="flex items-center gap-2 text-[10.5px] text-faint">
                            <span className="w-14">{label}</span>
                            <input
                              type="range"
                              min={0}
                              max={1}
                              step={0.01}
                              value={draft.layout[key] ?? (key.startsWith("camera_w") || key.startsWith("camera_h") ? 0.4 : 0.6)}
                              onChange={(event) => apply({ layout: { ...draft.layout, [key]: Number(event.target.value) } })}
                              className="flex-1"
                            />
                          </label>
                        ))}
                      </div>
                      <p className="text-[10px] leading-relaxed text-faint">
                        The source crop is where the face cam is taken from. Detect subject fills it automatically.
                      </p>
                    </>
                  ) : null}
                  {draft.layout.mode === "fit" ? (
                    <p className="text-[10px] leading-relaxed text-faint">
                      The whole frame stays visible, with a blurred fill behind it.
                    </p>
                  ) : null}
                </div>
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-[12px] font-medium text-muted">Subject framing</p>
                    <Button size="sm" variant="ghost" onClick={detectFace} loading={focusBusy}>
                      <Wand2 className="h-3 w-3" /> Detect subject
                    </Button>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5">
                    {[
                      ["Left", 0.15, 0.45],
                      ["Center", 0.5, 0.45],
                      ["Right", 0.85, 0.45],
                      ["Top", 0.5, 0.2],
                      ["Middle", 0.5, 0.5],
                      ["Bottom", 0.5, 0.8],
                    ].map(([label, x, y]) => (
                      <button
                        key={String(label)}
                        onClick={() => apply({ focus_x: x as number, focus_y: y as number })}
                        className={`rounded-lg border py-1.5 text-[11px] ${
                          Math.abs(draft.focus_x - (x as number)) < 0.03 &&
                          Math.abs(draft.focus_y - (y as number)) < 0.03
                            ? "border-flame-500/40 bg-flame-500/8 text-flame-400"
                            : "border-white/8 text-muted hover:border-white/16"
                        }`}
                      >
                        {label as string}
                      </button>
                    ))}
                  </div>
                  <div className="mt-3 space-y-2">
                    <label className="flex items-center gap-2 text-[11px] text-faint">
                      <span className="w-12">X</span>
                      <input type="range" min={0} max={1} step={0.01} value={draft.focus_x}
                        onChange={(event) => apply({ focus_x: Number(event.target.value) })} className="flex-1" />
                      <span className="w-8 text-right font-mono">{Math.round(draft.focus_x * 100)}</span>
                    </label>
                    <label className="flex items-center gap-2 text-[11px] text-faint">
                      <span className="w-12">Y</span>
                      <input type="range" min={0} max={1} step={0.01} value={draft.focus_y}
                        onChange={(event) => apply({ focus_y: Number(event.target.value) })} className="flex-1" />
                      <span className="w-8 text-right font-mono">{Math.round(draft.focus_y * 100)}</span>
                    </label>
                  </div>
                  <p className="mt-2 text-[10.5px] leading-relaxed text-faint">
                    Face detection uses OpenCV&apos;s Haar cascade when installed. It sets a stable crop anchor for
                    the selected range; adjust it freely.
                  </p>
                </div>
                <div className="space-y-2 rounded-lg border border-white/8 bg-ink-850/60 p-3">
                  <p className="text-[11.5px] font-medium">Transitions</p>
                  <Switch
                    checked={Number(draft.audio.fade_in || 0) > 0}
                    onCheckedChange={(value) => apply({ audio: { ...draft.audio, fade_in: value ? 0.4 : 0 } })}
                    label="Fade in (0.4s)"
                  />
                  <Switch
                    checked={Number(draft.audio.fade_out || 0) > 0}
                    onCheckedChange={(value) => apply({ audio: { ...draft.audio, fade_out: value ? 0.4 : 0 } })}
                    label="Fade out (0.4s)"
                  />
                </div>
              </div>
            ) : null}

            {tab === "captions" ? (
              <div className="space-y-4 p-4">
                <Switch
                  checked={draft.captions_enabled}
                  onCheckedChange={(value) => apply({ captions_enabled: value })}
                  label="Burn captions into the video"
                />
                <div>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="text-[11px] font-medium text-muted">Creator presets</p>
                    <Switch
                      checked={includeLook}
                      onCheckedChange={setIncludeLook}
                      label="Apply full look"
                    />
                  </div>
                  <div className="grid max-h-44 grid-cols-2 gap-1.5 overflow-y-auto pr-1">
                    {(styles.data || []).map((style) => {
                      const config = style.config as Record<string, unknown>;
                      const active = draft.caption_style_id === style.id;
                      const hasLook = Boolean(config.look);
                      return (
                        <div key={style.id} className="group relative">
                          <button
                            type="button"
                            onClick={() => applyCaptionStyle(style)}
                            className={`flex w-full items-center gap-2 rounded-md border px-2 py-1.5 pr-5 text-left text-[10.5px] ${
                              active ? "border-flame-500/40 bg-flame-500/8 text-paper" : "border-white/8 text-muted hover:border-white/16"
                            }`}
                          >
                            <span
                              className="h-5 w-5 shrink-0 rounded-sm border border-white/20"
                              style={{
                                background: String(config.box_color || "var(--color-seed)"),
                                color: String(config.highlight_color || "var(--color-flame-500)"),
                              }}
                            >
                              <span className="flex h-full items-center justify-center text-[8px] font-bold" style={{ color: String(config.highlight_color || "var(--color-flame-500)") }}>Aa</span>
                            </span>
                            <span className="min-w-0 flex-1 truncate">{style.name}</span>
                            {style.is_builtin ? (
                              <span className="text-[9px] text-faint">preset</span>
                            ) : hasLook ? (
                              <span className="text-[9px] text-mint">look</span>
                            ) : null}
                          </button>
                          {!style.is_builtin ? (
                            <button
                              type="button"
                              aria-label={`Delete ${style.name}`}
                              onClick={() => deleteCaptionStyle(style)}
                              className="absolute right-1 top-1 rounded p-0.5 text-faint opacity-0 transition hover:bg-white/10 hover:text-rose-300 group-hover:opacity-100"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </div>
                <Field label="Template">
                  <Select
                    value={draft.caption_style_id || ""}
                    onChange={(event) =>
                      apply({ caption_style_id: event.target.value || null, caption_overrides: {} })
                    }
                  >
                    <option value="">Workspace default</option>
                    {(styles.data || []).map((style) => (
                      <option key={style.id} value={style.id}>
                        {style.name}{style.is_builtin ? ", built-in" : ""}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="space-y-3 rounded-lg border border-white/8 bg-ink-850/60 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11.5px] font-medium">Translated captions</p>
                    {draft.caption_translation.language ? (
                      <Badge tone="mint">{draft.caption_translation.language_name || draft.caption_translation.language}</Badge>
                    ) : (
                      <Badge tone="neutral">original</Badge>
                    )}
                  </div>
                  <p className="text-[10px] leading-relaxed text-faint">
                    Translate the clip&apos;s transcript with your configured AI provider, then render to burn the translated lines in. No offline translation model is bundled.
                  </p>
                  <div className="flex gap-2">
                    <Select value={translationLanguage} onChange={(event) => setTranslationLanguage(event.target.value)} className="flex-1">
                      {TRANSLATION_LANGUAGES.map(([code, label]) => (
                        <option key={code} value={code}>{label}</option>
                      ))}
                    </Select>
                    <Button size="sm" variant="outline" loading={translating} onClick={translateCaptions}>
                      <Sparkles className="h-3.5 w-3.5" /> Translate
                    </Button>
                  </div>
                  {draft.caption_translation.segments?.length ? (
                    <div className="flex items-center justify-between gap-2 rounded-md bg-white/4 px-2 py-1.5">
                      <span className="truncate text-[10.5px] text-muted">{draft.caption_translation.segments[0]?.text}</span>
                      <button type="button" onClick={clearTranslation} className="shrink-0 text-[10px] text-faint hover:text-rose">Clear</button>
                    </div>
                  ) : null}
                </div>
                <div className="space-y-3 rounded-lg border border-white/8 bg-ink-850/60 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11.5px] font-medium">Heading</p>
                    <Switch
                      checked={Boolean(overrides.heading_enabled ?? true)}
                      onCheckedChange={(value) => apply({ caption_overrides: { ...overrides, heading_enabled: value } })}
                    />
                  </div>
                  <Input
                    value={String(overrides.heading || "")}
                    onChange={(event) => apply({ caption_overrides: { ...overrides, heading: event.target.value } })}
                    placeholder="Optional heading above the captions"
                    maxLength={120}
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <ColorField
                      label="Heading color"
                      value={String(overrides.heading_color || "#ffffff")}
                      onChange={(value) => apply({ caption_overrides: { ...overrides, heading_color: value } })}
                    />
                    <label className="flex items-center gap-2 text-[11px] text-faint">
                      <span className="w-12">Size</span>
                      <input
                        type="range"
                        min={28}
                        max={110}
                        value={Number(overrides.heading_size || 54)}
                        onChange={(event) => apply({ caption_overrides: { ...overrides, heading_size: Number(event.target.value) } })}
                        className="flex-1"
                      />
                      <span className="w-8 text-right font-mono">{Number(overrides.heading_size || 54)}</span>
                    </label>
                  </div>
                  <Switch
                    checked={Boolean(overrides.heading_uppercase ?? false)}
                    onCheckedChange={(value) => apply({ caption_overrides: { ...overrides, heading_uppercase: value } })}
                    label="Uppercase heading"
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <Field label="Font family" hint="Must be installed on the render server." className="flex-1">
                    <Input
                      value={String(overrides.font || activeConfig.font || "Arial")}
                      onChange={(event) => apply({ caption_overrides: { ...overrides, font: event.target.value } })}
                    />
                  </Field>
                  <Button variant="outline" size="sm" className="mt-5" onClick={() => setTemplateOpen(true)}>
                    Save preset
                  </Button>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <ColorField
                    label="Text"
                    value={String(overrides.text_color || activeConfig.text_color || "#ffffff")}
                    onChange={(value) => apply({ caption_overrides: { ...overrides, text_color: value } })}
                  />
                  <ColorField
                    label="Highlight"
                    value={String(overrides.highlight_color || activeConfig.highlight_color || "#ff6a1f")}
                    onChange={(value) => apply({ caption_overrides: { ...overrides, highlight_color: value } })}
                  />
                  <ColorField
                    label="Box"
                    value={String(overrides.box_color || activeConfig.box_color || "#0b0b0f")}
                    onChange={(value) => apply({ caption_overrides: { ...overrides, box_color: value } })}
                  />
                  <ColorField
                    label="Outline"
                    value={String(overrides.outline_color || activeConfig.outline_color || "#0b0b0f")}
                    onChange={(value) => apply({ caption_overrides: { ...overrides, outline_color: value } })}
                  />
                </div>
                <label className="flex items-center gap-2 text-[11px] text-faint">
                  <span className="w-20">Letter spacing</span>
                  <input type="range" min={0} max={12} value={Number(overrides.letter_spacing ?? activeConfig.letter_spacing ?? 0)}
                    onChange={(event) => apply({ caption_overrides: { ...overrides, letter_spacing: Number(event.target.value) } })}
                    className="flex-1" />
                  <span className="w-8 text-right font-mono">{Number(overrides.letter_spacing ?? activeConfig.letter_spacing ?? 0)}</span>
                </label>
                <label className="flex items-center gap-2 text-[11px] text-faint">
                  <span className="w-20">Size</span>
                  <input type="range" min={28} max={110} value={Number(overrides.font_size || activeConfig.font_size || 64)}
                    onChange={(event) => apply({ caption_overrides: { ...overrides, font_size: Number(event.target.value) } })}
                    className="flex-1" />
                  <span className="w-8 text-right font-mono">{Number(overrides.font_size || activeConfig.font_size || 64)}</span>
                </label>
                <label className="flex items-center gap-2 text-[11px] text-faint">
                  <span className="w-20">Words / line</span>
                  <input type="range" min={1} max={8} value={Number(overrides.max_words_per_line || activeConfig.max_words_per_line || 4)}
                    onChange={(event) => apply({ caption_overrides: { ...overrides, max_words_per_line: Number(event.target.value) } })}
                    className="flex-1" />
                  <span className="w-8 text-right font-mono">{Number(overrides.max_words_per_line || activeConfig.max_words_per_line || 4)}</span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Position">
                    <Select
                      value={String(overrides.position || activeConfig.position || "bottom")}
                      onChange={(event) => apply({ caption_overrides: { ...overrides, position: event.target.value } })}
                    >
                      <option value="top">Top</option>
                      <option value="middle">Middle</option>
                      <option value="bottom">Bottom</option>
                    </Select>
                  </Field>
                  <Field label="Animation">
                    <Select
                      value={String(overrides.animation || activeConfig.animation || "karaoke")}
                      onChange={(event) => apply({ caption_overrides: { ...overrides, animation: event.target.value } })}
                    >
                      <option value="karaoke">Word highlight</option>
                      <option value="pop">Pop</option>
                      <option value="bounce">Bounce</option>
                      <option value="typewriter">Typewriter</option>
                      <option value="fade">Fade</option>
                      <option value="none">None</option>
                    </Select>
                  </Field>
                </div>
                <div className="flex flex-col gap-2">
                  <Switch
                    checked={Boolean(overrides.uppercase ?? activeConfig.uppercase ?? false)}
                    onCheckedChange={(value) => apply({ caption_overrides: { ...overrides, uppercase: value } })}
                    label="Uppercase"
                  />
                  <Switch
                    checked={Boolean(overrides.box ?? activeConfig.box ?? true)}
                    onCheckedChange={(value) => apply({ caption_overrides: { ...overrides, box: value } })}
                    label="Background box"
                  />
                  <Switch
                    checked={Boolean(overrides.italic ?? activeConfig.italic ?? false)}
                    onCheckedChange={(value) => apply({ caption_overrides: { ...overrides, italic: value } })}
                    label="Italic"
                  />
                </div>
                <p className="text-[10.5px] leading-relaxed text-faint">
                  Captions are generated as ASS with word-level karaoke timing. Emoji support depends on the
                  fonts installed on the render server.
                </p>
                <Dialog
                  open={templateOpen}
                  onOpenChange={setTemplateOpen}
                  title="Save look preset"
                  description="Stores the current caption design and, optionally, the layout, overlays, audio and framing."
                  footer={
                    <>
                      <Button variant="ghost" onClick={() => setTemplateOpen(false)}>Cancel</Button>
                      <Button loading={savingTemplate} disabled={!templateName.trim()} onClick={saveTemplate}>
                        Save template
                      </Button>
                    </>
                  }
                >
                  <div className="mb-3 rounded-lg border border-white/8 bg-ink-850/60 p-3">
                    <Switch
                      checked={includeLook}
                      onCheckedChange={setIncludeLook}
                      label="Include layout, overlays, audio and framing"
                    />
                  </div>
                  <Field label="Preset name">
                    <Input
                      autoFocus
                      maxLength={80}
                      value={templateName}
                      onChange={(event) => setTemplateName(event.target.value)}
                      placeholder="Launch week captions"
                    />
                  </Field>
                </Dialog>
              </div>
            ) : null}

            {tab === "audio" ? (
              <div className="space-y-4 p-4">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-[12px] text-muted">
                    <Volume2 className="h-3.5 w-3.5" /> Source audio
                  </span>
                  <Switch
                    checked={Boolean(draft.audio.muted)}
                    onCheckedChange={(value) => apply({ audio: { ...draft.audio, muted: value } })}
                    label="Mute"
                  />
                </div>
                <label className="flex items-center gap-2 text-[11px] text-faint">
                  <span className="w-16">Volume</span>
                  <input type="range" min={0} max={1.5} step={0.05}
                    value={Number(draft.audio.volume ?? 1)}
                    onChange={(event) => apply({ audio: { ...draft.audio, volume: Number(event.target.value) } })}
                    className="flex-1" />
                  <span className="w-10 text-right font-mono">{Math.round(Number(draft.audio.volume ?? 1) * 100)}%</span>
                </label>
                <div className="rounded-lg border border-white/8 bg-ink-850/60 p-3">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-[12px] text-muted">
                      <Music className="h-3.5 w-3.5" /> Background music
                    </span>
                    {draft.music ? (
                      <button onClick={() => apply({ music: null })} className="text-[10.5px] text-faint hover:text-rose">
                        Remove
                      </button>
                    ) : null}
                  </div>
                  {draft.music?.asset_key ? (
                    <>
                      <p className="mt-2 truncate font-mono text-[10px] text-faint">
                        {draft.music.name || draft.music.asset_key.split("/").pop()}
                      </p>
                      <label className="mt-2 flex items-center gap-2 text-[11px] text-faint">
                        <span className="w-16">Music</span>
                        <input type="range" min={0} max={1} step={0.01}
                          value={Number(draft.music.volume ?? 0.22)}
                          onChange={(event) =>
                            apply({ music: { ...draft.music, volume: Number(event.target.value) } })
                          }
                          className="flex-1" />
                        <span className="w-10 text-right font-mono">
                          {Math.round(Number(draft.music.volume ?? 0.22) * 100)}%
                        </span>
                      </label>
                    </>
                  ) : (
                    <label className="mt-2 flex cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-dashed border-white/12 py-2.5 text-[11px] text-faint hover:border-flame-500/40 hover:text-paper">
                      {uploading === "music" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                      Upload an audio file
                      <input type="file" accept=".mp3,.wav,.m4a,.aac,.ogg,.flac,.opus" className="hidden"
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) void uploadAsset(file, "music");
                        }} />
                    </label>
                  )}
                  <p className="mt-2 text-[10px] leading-relaxed text-faint">
                    Music is looped, trimmed to the clip and mixed under the voice with loudness normalization.
                  </p>
                </div>
                <p className="text-[10.5px] leading-relaxed text-faint">
                  Output is normalized to {`-16 LUFS`} with a -1.5 dBTP ceiling. Original audio above 95% may clip
                  before normalization; lower the volume if it does.
                </p>
              </div>
            ) : null}

            {tab === "overlays" ? (
              <div className="space-y-4 p-4">
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={addTextOverlay} className="flex-1">
                    <Layers className="h-3 w-3" /> Text
                  </Button>
                  <label className="flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-white/12 px-3 py-1.5 text-[13px] text-paper hover:bg-white/4">
                    {uploading === "image" ? <Loader2 className="h-3 w-3 animate-spin" /> : <ImageIcon className="h-3 w-3" />}
                    Image / B-roll
                    <input type="file" accept=".png,.jpg,.jpeg,.webp,.gif" className="hidden"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) void uploadAsset(file, "image");
                      }} />
                  </label>
                </div>

                {draft.overlays.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-white/10 px-3 py-6 text-center text-[11px] text-faint">
                    No overlays yet. Add positioned text or upload an image.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {draft.overlays.map((overlay) => (
                      <div key={overlay.id || `${overlay.type}-${overlay.start_ms}`} className="rounded-lg border border-white/8 bg-ink-850/60 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-1.5 text-[11px] text-muted">
                            {overlay.type === "text" ? <Layers className="h-3 w-3" /> : <ImageIcon className="h-3 w-3" />}
                            {overlay.type === "text" ? "Text" : "Image"}
                          </span>
                          <button onClick={() => removeOverlay(overlay.id)} className="text-[10.5px] text-faint hover:text-rose">
                            Remove
                          </button>
                        </div>
                        {overlay.type === "text" ? (
                          <Textarea
                            className="mt-2 min-h-16 text-[12px]"
                            value={overlay.text || ""}
                            onChange={(event) => updateOverlay(overlay.id, { text: event.target.value })}
                          />
                        ) : (
                          <p className="mt-2 truncate font-mono text-[9.5px] text-faint">{overlay.asset_key}</p>
                        )}
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          <label className="text-[10px] text-faint">
                            Start s
                            <Input type="number" min={0} max={durationSeconds} step={0.1}
                              className="mt-1 h-8 text-[11px]"
                              value={Math.round(overlay.start_ms / 100) / 10}
                              onChange={(event) => updateOverlay(overlay.id, { start_ms: Math.round(Number(event.target.value) * 1000) })} />
                          </label>
                          <label className="text-[10px] text-faint">
                            End s
                            <Input type="number" min={0} max={durationSeconds} step={0.1}
                              className="mt-1 h-8 text-[11px]"
                              value={Math.round(overlay.end_ms / 100) / 10}
                              onChange={(event) => updateOverlay(overlay.id, { end_ms: Math.round(Number(event.target.value) * 1000) })} />
                          </label>
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          <label className="text-[10px] text-faint">
                            Horizontal
                            <input type="range" min={0} max={1} step={0.01} value={overlay.x}
                              onChange={(event) => updateOverlay(overlay.id, { x: Number(event.target.value) })}
                              className="mt-2 w-full" />
                          </label>
                          <label className="text-[10px] text-faint">
                            Vertical
                            <input type="range" min={0} max={1} step={0.01} value={overlay.y}
                              onChange={(event) => updateOverlay(overlay.id, { y: Number(event.target.value) })}
                              className="mt-2 w-full" />
                          </label>
                        </div>
                        {overlay.type === "text" ? (
                          <div className="mt-2 grid grid-cols-2 gap-2">
                            <ColorField label="Color" value={overlay.color || "#ffffff"}
                              onChange={(value) => updateOverlay(overlay.id, { color: value })} />
                            <label className="text-[10px] text-faint">
                              Size
                              <Input type="number" min={16} max={140} className="mt-1 h-8 text-[11px]"
                                value={overlay.font_size || 56}
                                onChange={(event) => updateOverlay(overlay.id, { font_size: Number(event.target.value) })} />
                            </label>
                          </div>
                        ) : (
                          <label className="mt-2 block text-[10px] text-faint">
                            Width {Math.round((overlay.width ?? 0.3) * 100)}%
                            <input type="range" min={0.05} max={0.9} step={0.01} value={overlay.width ?? 0.3}
                              onChange={(event) => updateOverlay(overlay.id, { width: Number(event.target.value) })}
                              className="mt-2 w-full" />
                          </label>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <Alert tone="info">
                  Stock footage and AI video B-roll search are not bundled; they require a licensed provider.
                  Uploaded images work as B-roll overlays today.
                </Alert>
              </div>
            ) : null}

            {tab === "export" ? (
              <div className="space-y-4 p-4">
                <Field label="Platform preset">
                  <Select
                    value={preset}
                    onChange={(event) => {
                      const value = event.target.value;
                      setPreset(value);
                      const match = PRESETS.find((item) => item.id === value);
                      if (match) apply({ aspect_ratio: match.aspect, width: aspectSize(match.aspect).width, height: aspectSize(match.aspect).height });
                    }}
                  >
                    {PRESETS.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}, {item.size}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Container">
                  <Select value={format} onChange={(event) => setFormat(event.target.value)}>
                    <option value="mp4">MP4, H.264 + AAC (recommended)</option>
                    <option value="mov">MOV, H.264 + AAC</option>
                    <option value="webm">WebM, VP9 + Opus</option>
                  </Select>
                </Field>
                <div className="rounded-lg border border-white/8 bg-ink-850/60 p-3 text-[11px] text-faint">
                  <div className="flex justify-between">
                    <span>Output</span>
                    <span className="font-mono text-muted">{draft.width}×{draft.height}</span>
                  </div>
                  <div className="mt-1.5 flex justify-between">
                    <span>Duration</span>
                    <span className="font-mono text-muted">{formatDuration(durationSeconds)}</span>
                  </div>
                  <div className="mt-1.5 flex justify-between">
                    <span>Captions</span>
                    <span className="font-mono text-muted">{draft.captions_enabled ? "burned in" : "off"}</span>
                  </div>
                  <div className="mt-1.5 flex justify-between">
                    <span>Loudness</span>
                    <span className="font-mono text-muted">-16 LUFS</span>
                  </div>
                </div>
                <Button className="w-full" onClick={render} loading={rendering}>
                  <Download className="h-4 w-4" /> Render clip
                </Button>

                {renderJob.data ? (
                  <div className="rounded-lg border border-white/8 bg-ink-850 p-3">
                    <div className="flex items-center justify-between text-[11.5px]">
                      <span className="text-muted capitalize">{renderJob.data.status}</span>
                      <span className="font-mono text-faint">{Math.round(renderJob.data.progress)}%</span>
                    </div>
                    <Progress value={renderJob.data.progress} className="mt-2" />
                    {renderJob.data.error_message ? (
                      <p className="mt-2 text-[11px] text-rose">{renderJob.data.error_message}</p>
                    ) : null}
                    {renderJob.data.download_url ? (
                      <a href={renderJob.data.download_url} className="mt-2 block text-[11.5px] text-flame-400 hover:text-flame-500">
                        Download the rendered file
                      </a>
                    ) : null}
                  </div>
                ) : null}

                <div className="border-t border-white/8 pt-3">
                  <p className="text-[11px] font-medium text-muted">Export library</p>
                  <Link href="/exports" className="mt-1 block text-[11px] text-faint hover:text-paper">
                    All rendered files
                  </Link>
                </div>
              </div>
            ) : null}
          </Panel>

          <Panel className="p-4">
            <p className="text-[11px] font-medium text-muted">Source clip</p>
            <p className="mt-1 text-[11.5px] leading-relaxed text-faint">
              {project.clip_id ? "Created from a reviewed clip candidate." : "Manual editing project."}{" "}
              {project.video_title}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Link href={`/videos/${videoId}`} className="text-[11px] text-flame-400 hover:text-flame-500">
                Transcript & analysis
              </Link>
              <Link href="/renders" className="text-[11px] text-faint hover:text-paper">
                Render queue
              </Link>
            </div>
          </Panel>
        </div>
      </div>

      <Dialog
        open={splitOpen}
        onOpenChange={setSplitOpen}
        title="Split this clip"
        description="Creates two new manual clips at the playhead and moves the original to rejected."
        footer={
          <>
            <Button variant="ghost" onClick={() => setSplitOpen(false)}>Cancel</Button>
            <Button onClick={splitClip}>
              <Scissors className="h-4 w-4" /> Split at {formatTimecode(playhead)}
            </Button>
          </>
        }
      >
        <p className="text-[12.5px] leading-relaxed text-muted">
          Part 1 runs {formatTimecode(draft.trim_start_ms)} → {formatTimecode(playhead)}, part 2 runs{" "}
          {formatTimecode(playhead)} → {formatTimecode(draft.trim_end_ms)}. Both are added to the source
          video&apos;s clip list, where you can open them individually.
        </p>
      </Dialog>

      <Dialog
        open={mergeOpen}
        onOpenChange={setMergeOpen}
        title="Merge with another clip"
        description="The merged clip spans from the earliest start to the latest end."
        footer={
          <>
            <Button variant="ghost" onClick={() => setMergeOpen(false)}>Cancel</Button>
            <Button onClick={mergeClip} loading={merging} disabled={!mergeId}>
              <Merge className="h-4 w-4" /> Merge clips
            </Button>
          </>
        }
      >
        <Field label="Adjacent clip">
          <Select value={mergeId} onChange={(event) => setMergeId(event.target.value)}>
            <option value="">Select a clip</option>
            {siblingClips.map((clip) => (
              <option key={clip.id} value={clip.id}>
                {formatTimecode(clip.start_ms)} / {clip.title.slice(0, 50)}
              </option>
            ))}
          </Select>
        </Field>
        {!project.clip_id ? (
          <p className="mt-3 text-[11px] text-ember">
            This editor is not linked to a candidate clip, so merging would only move the selected clip.
            Open an editor from a clip first to combine two candidates.
          </p>
        ) : null}
        <p className="mt-3 text-[11px] leading-relaxed text-faint">
          The original clips are removed and a new merged candidate opens in a fresh editor. Renders already
          produced are kept.
        </p>
      </Dialog>
    </div>
  );
}

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-[10.5px] text-faint">
      {label}
      <span className="mt-1 flex items-center gap-2 rounded-lg border border-white/10 bg-ink-850 px-2 py-1.5">
        <input
          type="color"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="h-5 w-6 cursor-pointer rounded border-0 bg-transparent p-0"
        />
        <span className="font-mono text-[10px] text-muted">{value}</span>
      </span>
    </label>
  );
}
