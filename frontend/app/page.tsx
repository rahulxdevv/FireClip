"use client";

import Link from "next/link";
import {
  ArrowRight,
  Captions,
  Crop,
  Film,
  Flame,
  Layers,
  Play,
  Server,
  Share2,
  Sparkles,
  Users,
  Webhook,
} from "lucide-react";
import { Logo } from "@/components/logo";
import { Button, ScoreRing } from "@/components/ui";

const clips = [
  {
    title: "Audience growth",
    caption: ["the one thing ", "nobody", " tells you"],
    time: "04:12-04:54",
    score: 87,
    tag: "Strong hook",
  },
  {
    title: "The wrong moment",
    caption: ["why creators quit at the ", "wrong", " moment"],
    time: "12:30-13:08",
    score: 79,
    tag: "Story payoff",
  },
  {
    title: "One changed line",
    caption: ["retention doubled after ", "one line", ""],
    time: "21:05-21:36",
    score: 74,
    tag: "Concrete result",
  },
];

const steps = [
  {
    number: "01",
    title: "Bring the long version",
    body: "Upload a file, paste a YouTube or Twitch link, or record a live stream. FireClip probes every file before it enters the pipeline.",
  },
  {
    number: "02",
    title: "Read every word",
    body: "Local Whisper or a hosted engine produces a word-level transcript. Speakers, pauses and language are stored with the project.",
  },
  {
    number: "03",
    title: "Find the moment",
    body: "Multi-signal analysis scores hooks, curiosity, story, payoff and boundaries. Every pick comes with a reason you can interrogate.",
  },
  {
    number: "04",
    title: "Cut, caption, ship",
    body: "Frame it vertically, style the captions, render with FFmpeg, then schedule it to the platforms you have connected.",
  },
];

const features = [
  {
    icon: Sparkles,
    title: "Explained highlight detection",
    body: "Twelve transcript signals, a visible breakdown and a written rationale for every candidate. No black-box virality score.",
    span: "sm:col-span-2",
  },
  {
    icon: Captions,
    title: "Word-level captions",
    body: "Karaoke-style highlights, outline and box controls, four built-in styles, plus custom styles saved to your workspace.",
    span: "",
  },
  {
    icon: Crop,
    title: "Subject-aware framing",
    body: "Turn a wide recording into 9:16, 1:1, 4:5 or 16:9 with face detection for the dominant subject and manual fine-tuning.",
    span: "",
  },
  {
    icon: Layers,
    title: "Real editing, not a mockup",
    body: "Trim, split, merge, overlay text and images, add music and ducking, then export at platform presets.",
    span: "",
  },
  {
    icon: Film,
    title: "Provider-agnostic AI",
    body: "OpenAI, Anthropic, Gemini, Ollama, or the built-in signal engine. Keys are encrypted and never reach the browser.",
    span: "",
  },
  {
    icon: Server,
    title: "Your infrastructure",
    body: "FastAPI, PostgreSQL, Redis and FFmpeg. Runs locally with SQLite and inline workers, scales into Docker with ARQ workers.",
    span: "sm:col-span-2",
  },
  {
    icon: Users,
    title: "Review without spreadsheets",
    body: "Invite owners, admins, editors and viewers. Leave comments on a clip, resolve feedback and approve or reject batches in one action.",
    span: "",
  },
  {
    icon: Share2,
    title: "Client-ready links",
    body: "Share an export with a password and expiry, revoke it at any time, and keep the player on your own domain with no third-party embeds.",
    span: "",
  },
  {
    icon: Webhook,
    title: "Plans, email and hooks",
    body: "SMTP for verification and invites, Stripe checkout and invoices when configured, plus HMAC-signed webhooks with a delivery log.",
    span: "sm:col-span-2",
  },
];

const NAV_LINKS = [
  { href: "#workflow", label: "How it works" },
  { href: "#features", label: "Capabilities" },
  { href: "#ownership", label: "Self-hosting" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-ink-950">
      <header className="sticky top-0 z-40 border-b border-paper/[0.07] bg-ink-950">
        <div className="mx-auto flex h-[68px] w-full max-w-6xl items-center justify-between px-5">
          <Link href="/" aria-label="FireClip home">
            <Logo size={30} />
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="rounded-[var(--radius-control)] px-3 py-2 text-[13px] font-medium text-muted transition-colors hover:bg-paper/[0.04] hover:text-paper"
              >
                {link.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Sign in
              </Button>
            </Link>
            <Link href="/register">
              <Button size="sm">
                Start free
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="relative isolate">
          <div className="mx-auto w-full max-w-6xl px-5">
            <div className="grid gap-7 pt-11 sm:pt-14 lg:grid-cols-[minmax(0,1fr)_372px] lg:items-start lg:gap-16 lg:pt-20">
              <h1 className="display text-[38px] text-paper sm:text-[54px] lg:text-[70px]">
                Find the moment.
                <br />
                <span className="mt-2 inline-block rounded-[var(--radius-card)] bg-flame-500 px-[0.16em] pb-[0.07em] text-seed">
                  Make it viral.
                </span>
              </h1>
              <div className="lg:pt-3">
                <p className="max-w-[44ch] text-[14.5px] leading-relaxed text-muted sm:text-[15px]">
                  FireClip reads your long videos and streams, finds the moments worth clipping,
                  cuts them to vertical with captions, and gets them ready to publish.
                </p>
                <div className="mt-6 flex flex-col gap-2.5 sm:flex-row sm:items-center">
                  <Link href="/register" className="sm:w-auto">
                    <Button size="lg" className="w-full sm:w-auto">
                      Start free
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Link href="/login" className="sm:w-auto">
                    <Button variant="outline" size="lg" className="w-full sm:w-auto">
                      <Play className="h-4 w-4" />
                      Sign in
                    </Button>
                  </Link>
                </div>
                <p className="mt-3 text-[12px] text-faint">
                  Every AI decision shows its work. Free to self-host.
                </p>
              </div>
            </div>

            <ProductFrame />
          </div>
        </section>

        <section id="workflow" className="mx-auto w-full max-w-6xl px-5 py-20 sm:py-24">
          <div className="max-w-2xl">
            <h2 className="display text-[32px] text-paper sm:text-[40px]">
              From a two-hour stream
              <br />
              to a folder of clips.
            </h2>
            <p className="mt-4 max-w-lg text-[14px] leading-relaxed text-muted">
              Four stages, one pipeline. Each stage writes its state to the database, so a retry
              resumes where the last attempt stopped.
            </p>
          </div>
          <ol className="mt-12 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step) => (
              <li key={step.number} className="border-t border-paper/[0.09] pt-4">
                <span className="font-display text-[13px] font-semibold text-flame-500">{step.number}</span>
                <h3 className="mt-3 font-display text-[17px] font-semibold tracking-[-0.02em] text-paper">
                  {step.title}
                </h3>
                <p className="mt-2 text-[13px] leading-relaxed text-muted">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="features" className="mx-auto w-full max-w-6xl px-5 pb-20 sm:pb-24">
          <div className="mb-10 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <h2 className="display max-w-xl text-[32px] text-paper sm:text-[40px]">
              The parts of clipping that eat your week.
            </h2>
            <p className="max-w-xs text-[13px] leading-relaxed text-faint">
              Built in the open: transcription, framing, editing, review and publishing in one
              workspace.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <article
                key={feature.title}
                className={"panel panel-hover flex flex-col p-5 " + feature.span}
              >
                <h3 className="flex items-center gap-2 font-display text-[15.5px] font-semibold tracking-[-0.02em] text-paper">
                  <feature.icon className="h-4 w-4 shrink-0 text-flame-500" />
                  {feature.title}
                </h3>
                <p className="mt-2 text-[13px] leading-relaxed text-muted">{feature.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="ownership" className="mx-auto w-full max-w-6xl px-5 pb-24">
          <div className="panel p-6 sm:p-10">
            <div className="grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:items-center">
              <div>
                <h2 className="display text-[30px] text-paper sm:text-[38px]">
                  Your footage stays
                  <br />
                  on your infrastructure.
                </h2>
                <p className="mt-4 max-w-md text-[14px] leading-relaxed text-muted">
                  FireClip is a self-hosted stack: FastAPI, PostgreSQL, Redis and FFmpeg behind one
                  Compose file. Storage, models and API keys are yours to choose.
                </p>
                <div className="mt-7 flex flex-wrap gap-2">
                  <Link href="/register">
                    <Button>
                      Start free
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Link href="/docs">
                    <Button variant="outline">Read the docs</Button>
                  </Link>
                </div>
              </div>
              <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-[var(--radius-card)] border border-paper/[0.08] bg-paper/[0.06]">
                {[
                  ["Storage", "Local disk or S3"],
                  ["Transcription", "Whisper, hosted or local"],
                  ["Workers", "Inline or ARQ + Redis"],
                  ["Publishing", "Scheduled or on demand"],
                ].map(([term, detail]) => (
                  <div key={term} className="bg-ink-950/80 p-4">
                    <dt className="text-[11.5px] text-faint">{term}</dt>
                    <dd className="mt-1 text-[13px] font-medium text-paper">{detail}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-paper/[0.07]">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-5 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Logo size={26} />
            <p className="mt-3 max-w-sm text-[12.5px] leading-relaxed text-faint">
              Clipping, editing and publishing for long video. Self-hosted, explainable, no
              invented analytics.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[12.5px] text-muted">
            <a href="#workflow" className="transition-colors hover:text-paper">
              How it works
            </a>
            <a href="#features" className="transition-colors hover:text-paper">
              Capabilities
            </a>
            <Link href="/docs" className="transition-colors hover:text-paper">
              Docs
            </Link>
            <Link href="/login" className="transition-colors hover:text-paper">
              Sign in
            </Link>
            <Link href="/register" className="transition-colors hover:text-paper">
              Start free
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function ProductFrame() {
  return (
    <div className="relative mx-auto mt-12 max-w-5xl pb-4 sm:mt-14">
      <div className="panel overflow-hidden shadow-frame">
        <div className="flex h-11 items-center gap-3 border-b border-paper/[0.07] px-4">
          <Flame className="h-3.5 w-3.5 shrink-0 text-flame-500" />
          <span className="shrink-0 text-[12px] font-medium text-paper">Clip discovery</span>
          <span className="hidden truncate text-[11.5px] text-faint sm:block">The Long Game, Episode 41</span>
          <span className="ml-auto shrink-0 rounded-full bg-mint/12 px-2 py-0.5 text-[10.5px] font-medium text-mint">
            6 found
          </span>
        </div>
        <div className="grid sm:grid-cols-[190px_1fr]">
          <div className="hidden flex-col gap-1 border-r border-paper/[0.07] p-3 sm:flex">
            {[
              ["Overview", false],
              ["Transcript", false],
              ["Highlights", true],
              ["Captions", false],
              ["Framing", false],
              ["Publish", false],
            ].map(([label, active]) => (
              <div
                key={String(label)}
                className={
                  "flex items-center gap-2 rounded-[var(--radius-control)] px-2.5 py-1.5 text-[12px] " +
                  (active ? "bg-paper/[0.06] text-paper" : "text-faint")
                }
              >
                <span className={"h-1 w-1 rounded-full " + (active ? "bg-flame-500" : "bg-ink-600")} />
                {label}
              </div>
            ))}
          </div>
          <div className="p-3 sm:p-4">
            <div className="mb-3 flex items-center gap-2.5 rounded-[var(--radius-card)] border border-paper/[0.07] bg-paper/[0.02] px-3 py-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] bg-flame-500/15 text-flame-400">
                <Film className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-[12.5px] font-medium text-paper">The Long Game, Episode 41</p>
                <p className="flex flex-wrap items-center gap-x-2 text-[10.5px] text-faint">
                  <span>54:12</span>
                  <span>podcast, 2 speakers</span>
                  <span>English</span>
                </p>
              </div>
              <span className="ml-auto hidden rounded-[var(--radius-control)] border border-paper/[0.1] px-1.5 py-0.5 text-[10px] text-faint sm:block">
                9:16
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
              {clips.map((clip, index) => (
                <figure key={clip.title} className={"min-w-0" + (index === 2 ? " hidden sm:block" : "")}>
                  <div className="relative aspect-[9/16] overflow-hidden rounded-[var(--radius-card)] border border-paper/[0.08] bg-gradient-to-b from-ink-750 to-ink-950">
                    <div className="pointer-events-none absolute inset-0 ember-glow opacity-80" aria-hidden />
                    <div className="absolute inset-x-2 top-2 flex items-start justify-between">
                      <span className="rounded-full bg-ink-950/70 px-1.5 py-0.5 text-[9.5px] text-muted">
                        {clip.tag}
                      </span>
                      <ScoreRing score={clip.score} size={30} />
                    </div>
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-ink-950 via-ink-950/85 to-transparent px-2 pb-2.5 pt-10">
                      <p className="text-[10.5px] font-bold leading-snug text-paper">
                        {clip.caption[0]}
                        <span className="rounded-[3px] bg-flame-500 px-[3px] text-seed">{clip.caption[1]}</span>
                        {clip.caption[2]}
                      </p>
                      <p className="mt-1 text-[9.5px] text-faint">{clip.time}</p>
                    </div>
                    <span className="absolute left-1/2 top-1/2 hidden h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-paper/20 bg-ink-950/70 text-paper sm:flex">
                      <Play className="h-3 w-3" />
                    </span>
                  </div>
                  <figcaption className="mt-2 flex items-center justify-between gap-2">
                    <span className="truncate text-[10px] text-muted">{clip.title}</span>
                    <span className="shrink-0 text-[10px] font-medium text-mint">{clip.score} / 100</span>
                  </figcaption>
                </figure>
              ))}
            </div>
            <div className="mt-3 flex items-center gap-2 rounded-[var(--radius-card)] border border-paper/[0.07] bg-paper/[0.02] px-3 py-2">
              <span className="text-[10.5px] text-faint">Signals</span>
              <div className="flex h-9 flex-1 items-end gap-[3px]">
                {[38, 52, 30, 64, 44, 72, 58, 36, 61, 47, 70, 55, 33, 66, 49, 74, 42, 58, 63, 39].map(
                  (height, index) => (
                    <span
                      key={index}
                      className="flex-1 rounded-sm bg-flame-500/50"
                      style={{ height: String(height) + "%" }}
                    />
                  ),
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
