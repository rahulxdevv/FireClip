"use client";

import { useRouter } from "next/navigation";
import * as React from "react";
import { Link2, Radio, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { Alert, Button, Field, Input, Panel, Select } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { toast } from "@/lib/stores";
import type { Campaign, ProjectItem, Video } from "@/lib/types";

const PLATFORMS = [
  { id: "youtube", label: "YouTube", hint: "Public videos and live replays" },
  { id: "twitch", label: "Twitch", hint: "Public VODs and streams" },
  { id: "kick", label: "Kick", hint: "Public streams via yt-dlp" },
  { id: "direct", label: "Direct URL", hint: "Any public MP4/audio URL" },
];

function detect(value: string): string {
  if (/youtu\.?be|youtube\.com/i.test(value)) return "youtube";
  if (/twitch\.tv/i.test(value)) return "twitch";
  if (/kick\.com/i.test(value)) return "kick";
  return "direct";
}

export default function ImportPage() {
  const router = useRouter();
  const [url, setUrl] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [projectId, setProjectId] = React.useState("");
  const [campaignId, setCampaignId] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const projects = useApi<ProjectItem[]>("/api/projects");
  const campaigns = useApi<Campaign[]>("/api/campaigns");
  const platform = detect(url);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const video = await api.post<Video>("/api/videos/import", {
        url: url.trim(),
        project_id: projectId || null,
        campaign_id: campaignId || null,
        title: title.trim() || null,
      });
      toast("Import started", "success");
      router.push(`/videos/${video.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Ingest"
        title="Import from a URL"
        description="FireClip fetches the source with yt-dlp when available, probes it, then runs the same pipeline as an upload."
      />

      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <form onSubmit={submit} className="space-y-4">
          <Panel className="p-5">
            <Field label="Video URL" hint="Public URLs only. Nothing bypasses logins, paywalls or DRM.">
              <div className="relative">
                <Link2 className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
                <Input
                  className="pl-9 font-mono text-[12.5px]"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://www.youtube.com/watch?v=…"
                  required
                  minLength={8}
                />
              </div>
            </Field>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {PLATFORMS.map((item) => (
                <div
                  key={item.id}
                  className={`rounded-lg border px-3 py-2.5 ${
                    platform === item.id && url
                      ? "border-flame-500/35 bg-flame-500/5"
                      : "border-white/8 bg-ink-850/60"
                  }`}
                >
                  <p className="text-[12px] font-medium">{item.label}</p>
                  <p className="mt-0.5 text-[10.5px] text-faint">{item.hint}</p>
                </div>
              ))}
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <Field label="Title override" hint="Optional">
                <Input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={300} />
              </Field>
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

            {error ? <Alert className="mt-4">{error}</Alert> : null}

            <div className="mt-5 flex items-center gap-2">
              <Button type="submit" loading={submitting} disabled={!url.trim()}>
                <Radio className="h-4 w-4" /> Start import
              </Button>
              <span className="font-mono text-[10.5px] text-faint">
                {url ? `detected: ${platform}` : "paste a link to begin"}
              </span>
            </div>
          </Panel>
        </form>

        <div className="space-y-4">
          <Panel className="p-5">
            <div className="flex items-center gap-2 text-[12.5px] font-medium">
              <ShieldCheck className="h-4 w-4 text-mint" /> Platform rules
            </div>
            <ul className="mt-3 space-y-2.5 text-[11.5px] leading-relaxed text-muted">
              <li>Only publicly accessible content is supported.</li>
              <li>Downloading must comply with the platform&apos;s terms and copyright.</li>
              <li>
                FireClip does not accept cookies, credentials, DRM keys or any access-control bypass.
              </li>
              <li>You are responsible for having the rights to repurpose imported footage.</li>
            </ul>
          </Panel>

          <Panel className="p-5">
            <p className="text-[12.5px] font-medium">Server requirements</p>
            <p className="mt-2 text-[11.5px] leading-relaxed text-muted">
              Platform imports use <code className="font-mono text-paper">yt-dlp</code>. If it is missing,
              the API returns a clear configuration error rather than a fake job. Direct video URLs are
              fetched over HTTP with SSRF protection.
            </p>
            <div className="mt-3 rounded-lg border border-white/8 bg-ink-950/50 px-3 py-2 font-mono text-[10.5px] text-faint">
              pip install yt-dlp
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
