"use client";

import Link from "next/link";
import * as React from "react";
import { BookOpen, ExternalLink, Terminal } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { Badge, Panel } from "@/components/ui";

const SECTIONS = [
  { id: "quickstart", label: "Quick start" },
  { id: "pipeline", label: "How the pipeline works" },
  { id: "ai", label: "AI providers" },
  { id: "transcription", label: "Transcription" },
  { id: "rendering", label: "Rendering & captions" },
  { id: "publishing", label: "Publishing" },
  { id: "api", label: "REST API" },
  { id: "limits", label: "Known limitations" },
  { id: "troubleshooting", label: "Troubleshooting" },
];

export default function DocsPage() {
  const [active, setActive] = React.useState("quickstart");

  React.useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );
    SECTIONS.forEach(({ id }) => {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    });
    return () => observer.disconnect();
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="Help"
        title="Documentation"
        description="What this build does, how it is wired, and what it deliberately does not do."
      />

      <div className="grid gap-6 lg:grid-cols-[200px_1fr]">
        <aside className="hidden lg:block">
          <div className="sticky top-6 space-y-0.5">
            {SECTIONS.map((section) => (
              <a
                key={section.id}
                href={`#${section.id}`}
                className={`block rounded-lg px-3 py-2 text-[12px] transition-colors ${
                  active === section.id ? "bg-white/6 text-paper" : "text-faint hover:text-paper"
                }`}
              >
                {section.label}
              </a>
            ))}
            <a
              href="/openapi"
              target="_blank"
              rel="noreferrer"
              className="mt-2 flex items-center gap-1.5 rounded-lg px-3 py-2 text-[12px] text-flame-400 hover:text-flame-500"
            >
              OpenAPI explorer <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </aside>

        <div className="min-w-0 space-y-6">
          <Doc id="quickstart" title="Quick start" icon={<BookOpen className="h-4 w-4" />}>
            <ol className="list-decimal space-y-2 pl-4">
              <li>Register an account. A personal workspace is created automatically.</li>
              <li>Upload a file or import a URL from <Link href="/upload" className="doc-link">Upload</Link>. A URL import requires yt-dlp on the server.</li>
              <li>Wait for ingestion, transcription and analysis in the video page. Long media is processed asynchronously.</li>
              <li>Open a clip in the editor, adjust the crop and captions, then render a preset.</li>
              <li>Download the file from <Link href="/exports" className="doc-link">Exports</Link> or publish it to a connected account.</li>
            </ol>
            <p className="mt-3">
              The local development default runs with SQLite and an in-process job runner. Docker Compose switches to
              PostgreSQL, Redis and an ARQ worker without any application code changes.
            </p>
          </Doc>

          <Doc id="pipeline" title="How the pipeline works">
            <div className="space-y-2.5">
              {[
                ["Ingest", "Validate the file, probe dimensions/codecs/duration with ffprobe, extract audio to 16kHz mono WAV, generate a poster and sprite sheet."],
                ["Transcribe", "Selected engine produces segment-level timestamps and text. Optional diarization adds speaker labels."],
                ["Analyze", "Heuristic scoring combines transcript signals (hooks, questions, numbers, story shape) with audio energy and pacing. The LLM engine, when configured, returns candidates plus a per-signal explanation."],
                ["Cut", "Candidates become real clips with start/end times. Each carries a score breakdown, reason and caption style."],
                ["Edit", "The editor stores a declarative draft (crop keyframes, caption style, overlays, music, trim, fades) and auto-focus anchors faces."],
                ["Render", "FFmpeg builds the output: crop/scale, ASS subtitles, overlays, audio mix with loudnorm, then H.264/AAC or VP9/Opus."],
                ["Publish", "Official platform APIs upload the file; status, external URL and raw errors are recorded."],
                ["Measure", "Platform metrics are pulled on demand or numbers are entered manually and labelled as such."],
              ].map(([title, body], index) => (
                <div key={title} className="flex gap-3">
                  <span className="mt-0.5 font-mono text-[10px] text-flame-400">{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <p className="text-[12.5px] font-medium text-paper">{title}</p>
                    <p className="mt-0.5 text-[11.5px] leading-relaxed text-faint">{body}</p>
                  </div>
                </div>
              ))}
            </div>
          </Doc>

          <Doc id="ai" title="AI providers">
            <p>Every provider adapter speaks its native API. The heuristic engine is the only one that works with no network and no key.</p>
            <CodeBlock>{`AI_PROVIDER=heuristic        # heuristic | openai | anthropic | gemini | ollama
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1`}</CodeBlock>
            <p className="mt-3">
              Workspace keys are encrypted at rest and take precedence over environment keys. Use{" "}
              <Link href="/ai-settings" className="doc-link">AI & transcription</Link> to test a provider - the test
              performs a real request and reports latency or the provider&apos;s error.
            </p>
          </Doc>

          <Doc id="transcription" title="Transcription">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-[11.5px]">
                <thead className="border-b border-white/8 text-faint">
                  <tr><th className="py-2 pr-4 font-medium">Engine</th><th className="py-2 pr-4 font-medium">Where</th><th className="py-2 font-medium">Notes</th></tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-muted">
                  <tr><td className="py-2 pr-4 font-mono">whisper</td><td className="py-2 pr-4">local</td><td className="py-2">openai-whisper package; slower, CPU-friendly models available.</td></tr>
                  <tr><td className="py-2 pr-4 font-mono">faster_whisper</td><td className="py-2 pr-4">local</td><td className="py-2">CTranslate2 backend, optional extra, default in Docker.</td></tr>
                  <tr><td className="py-2 pr-4 font-mono">openai</td><td className="py-2 pr-4">cloud</td><td className="py-2">25MB request limit; requires OPENAI_API_KEY.</td></tr>
                  <tr><td className="py-2 pr-4 font-mono">mock</td><td className="py-2 pr-4">test only</td><td className="py-2">Requires ALLOW_MOCK_TRANSCRIPTION=true; labelled in the UI.</td></tr>
                </tbody>
              </table>
            </div>
            <p className="mt-3">
              Set <code className="doc-code">TRANSCRIPTION_ENGINE</code> explicitly. If the engine is unavailable the
              job fails with an actionable message; it never silently falls back to mock data.
            </p>
          </Doc>

          <Doc id="rendering" title="Rendering & captions">
            <p>
              Presets cover vertical 9:16 (1080×1920), square and landscape. Captions are burned in with libass using
              word-timed ASS karaoke where word timings exist. Smart crop uses OpenCV Haar face detection to place a
              static anchor; keyframed crop is stored in the draft and applied by FFmpeg.
            </p>
            <CodeBlock>{`ffmpeg -i input.mp4 -vf "crop=...,ass=captions.ass,scale=1080:1920" \\
  -c:v libx264 -preset veryfast -crf 21 -c:a aac -b:a 192k out.mp4`}</CodeBlock>
            <p className="mt-3">
              Output is probed before it is moved to storage, so a failed encode can never appear as a completed
              render. Fades, overlays and music are real FFmpeg filters, not preview-only effects.
            </p>
          </Doc>

          <Doc id="publishing" title="Publishing">
            <p>Connections require your own OAuth applications. Callback paths are:</p>
            <CodeBlock>{`/api/publishing/callback/youtube
/api/publishing/callback/tiktok
/api/publishing/callback/instagram
/api/publishing/callback/facebook`}</CodeBlock>
            <ul className="mt-3 list-disc space-y-1.5 pl-4">
              <li>YouTube and Facebook upload the file directly.</li>
              <li>Instagram Reels need a public HTTPS URL: configure S3-compatible storage and MEDIA_PUBLIC_BASE_URL.</li>
              <li>TikTok direct posting depends on app approval; the adapter reports the platform error verbatim.</li>
              <li>Scheduling is enforced by the server scheduler, and a missed schedule is reported rather than skipped silently.</li>
            </ul>
          </Doc>

          <Doc id="api" title="REST API">
            <p>
              All endpoints live under <code className="doc-code">/api</code> and are documented in the OpenAPI
              explorer. Browser sessions use an HTTP-only cookie; integrations should use an API key.
            </p>
            <CodeBlock>{`curl -H "X-API-Key: fk_..." \\
  -H "X-Workspace-Id: <workspace-id>" \\
  https://your-host/api/projects

curl -X POST https://your-host/api/videos/upload \\
  -H "X-API-Key: fk_..." \\
  -F "file=@episode.mp4"`}</CodeBlock>
            <p className="mt-3">
              To render, enqueue <code className="doc-code">POST /api/renders</code> with an editing project, preset and
              format, then poll <code className="doc-code">GET /api/renders/&#123;id&#125;</code>.
            </p>
          </Doc>

          <Doc id="limits" title="Known limitations">
            <div className="space-y-2">
              {[
                "No stock B-roll or music library: FireClip does not fabricate assets or licensing.",
                "Smart crop is a static face anchor, not per-frame speaker tracking.",
                "Diarization without pyannote is a pause-based estimate and is labelled as such.",
                "No payment provider is connected; plan limits exist but there is no checkout.",
                "Email verification, password reset and email notifications are not implemented.",
                "Speech recognition is unavailable in a Python 3.15 local environment with these wheels; use Docker or hosted Whisper.",
              ].map((item) => (
                <p key={item} className="flex gap-2">
                  <span className="text-flame-400">-</span>
                  <span>{item}</span>
                </p>
              ))}
            </div>
          </Doc>

          <Doc id="troubleshooting" title="Troubleshooting" icon={<Terminal className="h-4 w-4" />}>
            <div className="space-y-3">
              {[
                ["Jobs stay queued", "No worker is running. Locally ensure JOB_RUNNER=inline; in Docker check the worker container logs and Redis health."],
                ["FFmpeg not found", "Install FFmpeg with libx264 and libass and set FFMPEG_BINARY. The diagnostics panel shows the exact status."],
                ["Upload rejected", "Check MAX_UPLOAD_MB and allowed MIME types. Imports from private networks are blocked by SSRF protection."],
                ["Captions look empty", "Check the clip has segments, the caption style is enabled, and libass is present in the FFmpeg build."],
                ["Publishing fails with 401/403", "The platform token expired or lacks scopes. Reconnect the account and verify the app's review status."],
              ].map(([title, body]) => (
                <div key={title}>
                  <p className="text-[12.5px] font-medium text-paper">{title}</p>
                  <p className="mt-0.5 text-[11.5px] leading-relaxed text-faint">{body}</p>
                </div>
              ))}
            </div>
          </Doc>

          <Panel className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <p className="text-[12px] font-medium">Deployment guides</p>
              <p className="mt-0.5 text-[11px] text-faint">Docker Compose, environment variables and architecture.</p>
            </div>
            <Badge tone="flame">README.md · Docker · Render</Badge>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Doc({
  id,
  title,
  icon,
  children,
}: {
  id: string;
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Panel id={id} className="scroll-mt-6 p-5 sm:p-6">
      <h2 className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-paper">
        {icon} {title}
      </h2>
      <div className="doc-body space-y-2 text-[12px] leading-relaxed text-muted">{children}</div>
    </Panel>
  );
}

function CodeBlock({ children }: { children: React.ReactNode }) {
  return (
    <pre className="mt-3 overflow-x-auto rounded-lg border border-white/8 bg-ink-950/70 p-3 font-mono text-[10.5px] leading-relaxed text-muted">
      {children}
    </pre>
  );
}
