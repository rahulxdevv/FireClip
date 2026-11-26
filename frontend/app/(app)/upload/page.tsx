"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { CheckCircle2, FileVideo, UploadCloud, X } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { Alert, Button, Field, Input, Panel, Progress, Select, Switch } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { toast, useSessionStore } from "@/lib/stores";
import { formatBytes } from "@/lib/format";
import type { Campaign, ProjectItem, Video } from "@/lib/types";

const ACCEPT =
  ".mp4,.mov,.mkv,.webm,.avi,.m4v,.mpg,.mpeg,.flv,.ts,.mp3,.wav,.m4a,.aac,.ogg,.flac,.opus";

export default function UploadPage() {
  const router = useRouter();
  const workspaceId = useSessionStore((state) => state.activeWorkspaceId);
  const projects = useApi<ProjectItem[]>("/api/projects");
  const campaigns = useApi<Campaign[]>("/api/campaigns");
  const [file, setFile] = React.useState<File | null>(null);
  const [title, setTitle] = React.useState("");
  const [projectId, setProjectId] = React.useState("");
  const [campaignId, setCampaignId] = React.useState("");
  const [autoPipeline, setAutoPipeline] = React.useState(true);
  const [dragging, setDragging] = React.useState(false);
  const [progress, setProgress] = React.useState(0);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  function pick(selected: File | null | undefined) {
    if (!selected) return;
    setFile(selected);
    if (!title) setTitle(selected.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "));
    setError(null);
    setProgress(0);
  }

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file || !workspaceId) return;
    setUploading(true);
    setError(null);
    setProgress(0);
    const form = new FormData();
    form.append("file", file);
    if (title.trim()) form.append("title", title.trim());
    if (projectId) form.append("project_id", projectId);
    if (campaignId) form.append("campaign_id", campaignId);
    form.append("auto_pipeline", String(autoPipeline));

    try {
      const video = await new Promise<Video>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/videos/upload");
        xhr.withCredentials = true;
        xhr.setRequestHeader("X-Workspace-Id", workspaceId);
        xhr.upload.onprogress = (uploadEvent) => {
          if (uploadEvent.lengthComputable) {
            setProgress((uploadEvent.loaded / uploadEvent.total) * 100);
          }
        };
        xhr.onload = () => {
          const payload = safeParse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(payload as Video);
          } else {
            const detail =
              payload && typeof payload === "object" && "detail" in payload
                ? String((payload as { detail: unknown }).detail)
                : "Upload failed";
            reject(new ApiError(xhr.status, detail));
          }
        };
        xhr.onerror = () => reject(new ApiError(0, "The upload connection failed."));
        xhr.send(form);
      });
      toast("Upload complete. Processing started.", "success");
      router.push(`/videos/${video.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setUploading(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader        title="Upload a video"
        description="Video and audio files up to the server's configured limit. Metadata is probed with FFprobe; transcription starts automatically."
      />

      <form onSubmit={upload} className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-4">
          <Panel
            className={`relative p-6 transition-colors ${
              dragging ? "border-flame-500/50 bg-flame-500/4" : ""
            }`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              pick(event.dataTransfer.files?.[0]);
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              className="hidden"
              onChange={(event) => pick(event.target.files?.[0])}
            />
            {file ? (
              <div className="flex items-start gap-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-flame-500/12 text-flame-500">
                  <FileVideo className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-medium">{file.name}</p>
                  <p className="mt-0.5 font-mono text-[11px] text-faint">
                    {formatBytes(file.size)}, {file.type || "unknown type"}
                  </p>
                  {uploading ? (
                    <div className="mt-3 space-y-1.5">
                      <Progress value={progress} />
                      <p className="font-mono text-[10px] text-faint">
                        {progress >= 100 ? "Finishing upload…" : `${Math.round(progress)}% uploaded`}
                      </p>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setFile(null);
                        setTitle("");
                        setProgress(0);
                      }}
                      className="mt-2 inline-flex items-center gap-1 text-[11.5px] text-faint hover:text-rose"
                    >
                      <X className="h-3 w-3" /> Remove file
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center py-8 text-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-[var(--radius-card)] border border-paper/10 bg-ink-800 text-flame-500">
                  <UploadCloud className="h-5 w-5" />
                </div>
                <p className="text-[14px] font-medium">Drop a video here</p>
                <p className="mt-1 max-w-sm text-[12px] leading-relaxed text-faint">
                  MP4, MOV, MKV, WebM, AVI, audio files and more. Large files stream directly to storage.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  onClick={() => inputRef.current?.click()}
                >
                  Choose a file
                </Button>
              </div>
            )}
          </Panel>

          {error ? <Alert title="Upload failed">{error}</Alert> : null}

          <Panel className="divide-y divide-paper/6">
            <div className="px-5 py-3">
              <Field label="Title" hint="Defaults to the file name.">
                <Input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={300} />
              </Field>
            </div>
            <div className="grid gap-3 px-5 py-3 sm:grid-cols-2">
              <Field label="Project">
                <Select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
                  <option value="">No project</option>
                  {(projects.data || []).map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Campaign">
                <Select value={campaignId} onChange={(event) => setCampaignId(event.target.value)}>
                  <option value="">No campaign</option>
                  {(campaigns.data || []).filter((item) => item.status !== "archived").map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <div className="flex items-center justify-between gap-4 px-5 py-3.5">
              <div>
                <p className="text-[13px] font-medium">Run the full pipeline</p>
                <p className="mt-0.5 text-[11.5px] text-faint">
                  Probe, transcribe and analyze as soon as the upload lands.
                </p>
              </div>
              <Switch checked={autoPipeline} onCheckedChange={setAutoPipeline} />
            </div>
          </Panel>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={!file} loading={uploading}>
              <UploadCloud className="h-4 w-4" /> Upload and process
            </Button>
            <Link href="/import">
              <Button type="button" variant="ghost">
                Import from a URL instead
              </Button>
            </Link>
          </div>
        </div>

        <div className="space-y-4">
          <Panel className="p-5">
            <p className="text-[12.5px] font-medium">What happens next</p>
            <ol className="mt-3 space-y-3">
              {[
                ["Probe", "FFprobe reads duration, resolution, codecs and audio tracks."],
                ["Thumbnail", "A poster frame is generated for the library."],
                ["Transcribe", "Word-level timestamps via local Whisper or your hosted key."],
                ["Analyze", "Explainable highlight scoring produces candidate clips."],
              ].map(([step, body], index) => (
                <li key={step} className="flex gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-paper/10 font-mono text-[9px] text-flame-400">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-[12px] text-paper">{step}</p>
                    <p className="text-[11px] leading-relaxed text-faint">{body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </Panel>
          <Alert tone="info">
            Transcription is the one stage that can fail without credentials. If no engine is available,
            the job reports that clearly instead of inventing a transcript.
          </Alert>
          <div className="flex items-start gap-2 rounded-[var(--radius-card)] border border-paper/8 bg-ink-900 p-4 text-[11.5px] leading-relaxed text-faint">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-mint" />
            <p>
              Files are served only through authenticated endpoints with workspace checks. Local
              development stores media under <code className="font-mono text-muted">backend/data</code>.
            </p>
          </div>
        </div>
      </form>
    </div>
  );
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
