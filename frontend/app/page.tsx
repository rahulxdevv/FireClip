"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Captions,
  Crop,
  Film,
  Flame,
  Layers,
  Play,
  Server,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { Logo } from "@/components/logo";
import { Button, ScoreRing } from "@/components/ui";

const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0 },
};

const clips = [
  {
    title: "The one thing nobody tells you about audience growth",
    time: "04:12 - 04:54",
    score: 87,
    tag: "Strong hook",
  },
  {
    title: "Why most creators quit at the wrong moment",
    time: "12:30 - 13:08",
    score: 79,
    tag: "Story payoff",
  },
  {
    title: "\"Retention doubled when we changed one line\"",
    time: "21:05 - 21:36",
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
    body: "Twelve transcript signals, a visible breakdown and a written rationale for every candidate - no black-box virality score.",
  },
  {
    icon: Captions,
    title: "Word-level captions",
    body: "Karaoke-style highlights, outline and box controls, four built-in styles, plus custom styles saved to your workspace.",
  },
  {
    icon: Crop,
    title: "Subject-aware framing",
    body: "Turn a wide recording into 9:16, 1:1, 4:5 or 16:9 with face detection for the dominant subject and manual fine-tuning.",
  },
  {
    icon: Layers,
    title: "Real editing, not a mockup",
    body: "Trim, split, merge, overlay text and images, add music and ducking, then export at platform presets.",
  },
  {
    icon: Server,
    title: "Your infrastructure",
    body: "FastAPI, PostgreSQL, Redis and FFmpeg. Runs locally with SQLite and inline workers, scales into Docker with ARQ workers.",
  },
  {
    icon: Film,
    title: "Provider-agnostic AI",
    body: "OpenAI, Anthropic, Gemini, Ollama, or the built-in signal engine. Keys are encrypted and never reach the browser.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-ink-950">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[520px] ember-glow" />
      <header className="relative z-10 mx-auto flex h-20 w-full max-w-6xl items-center justify-between px-5">
        <Logo size={32} />
        <nav className="hidden items-center gap-7 text-[13px] text-muted md:flex">
          <a href="#workflow" className="transition-colors hover:text-paper">How it works</a>
          <a href="#features" className="transition-colors hover:text-paper">Capabilities</a>
          <a href="#ownership" className="transition-colors hover:text-paper">Self-hosting</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/login">
            <Button variant="ghost" size="sm">Sign in</Button>
          </Link>
          <Link href="/register">
            <Button size="sm">
              Start free <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      </header>

      <main className="relative z-10 mx-auto w-full max-w-6xl px-5">
        <section className="grid gap-12 pb-20 pt-14 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:pt-20">
          <motion.div initial="hidden" animate="show" variants={fadeUp} transition={{ duration: 0.55 }}>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-flame-500/25 bg-flame-500/8 px-3 py-1 text-[11.5px] text-flame-400">
              <Flame className="h-3 w-3" />
              AI clipping, editing and publishing in one place
            </div>
            <h1 className="max-w-xl text-[44px] font-semibold leading-[1.03] tracking-tight text-paper sm:text-[62px]">
              Find the moment.
              <br />
              <span className="text-flame-500">Make it viral.</span>
            </h1>
            <p className="mt-6 max-w-lg text-[15px] leading-relaxed text-muted">
              FireClip reads your long videos and streams, finds the moments worth clipping,
              cuts them to vertical with captions, and gets them ready to publish.
              Every AI decision shows its work.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/register">
                <Button size="lg">
                  Create a workspace <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/login">
                <Button variant="outline" size="lg">
                  <Play className="h-4 w-4" /> Sign in
                </Button>
              </Link>
            </div>
            <p className="mt-4 text-[11.5px] text-faint">
              No demo data, no invented analytics. Free to self-host.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.12 }}
            className="relative"
          >
            <div className="absolute -inset-8 -z-10 rounded-[32px] bg-flame-500/8 blur-2xl" />
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-ink-900 shadow-[0_40px_100px_-30px_rgba(0,0,0,0.95)]">
              <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-white/12" />
                  <span className="h-2 w-2 rounded-full bg-white/12" />
                  <span className="h-2 w-2 rounded-full bg-white/12" />
                </div>
                <span className="font-mono text-[10px] text-faint">fireclip / clip discovery</span>
                <span className="rounded bg-mint/10 px-1.5 py-0.5 font-mono text-[9px] text-mint">6 found</span>
              </div>
              <div className="grid grid-cols-[64px_1fr] sm:grid-cols-[88px_1fr]">
                <div className="border-r border-white/8 bg-ink-950/60 p-2.5">
                  <div className="mb-4 flex h-8 w-8 items-center justify-center rounded-lg bg-flame-500/15">
                    <Flame className="h-4 w-4 text-flame-500" />
                  </div>
                  {[0, 1, 2, 3].map((item) => (
                    <div
                      key={item}
                      className={`mb-2 h-6 rounded-md ${item === 0 ? "bg-white/8" : "bg-white/3"}`}
                    />
                  ))}
                </div>
                <div className="space-y-2.5 p-3 sm:p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[12px] font-medium">The Long Game - Episode 41</p>
                      <p className="font-mono text-[9.5px] text-faint">54:12 · podcast · 2 speakers</p>
                    </div>
                    <span className="rounded border border-white/10 px-1.5 py-0.5 font-mono text-[9px] text-faint">
                      9:16
                    </span>
                  </div>
                  <div className="flex h-10 items-end gap-[2px] overflow-hidden rounded bg-ink-850 px-2">
                    {Array.from({ length: 56 }).map((_, index) => (
                      <span
                        key={index}
                        className="flex-1 rounded-sm bg-flame-500/45"
                        style={{
                          height: `${18 + Math.abs(Math.sin(index * 0.7)) * 70}%`,
                          opacity: index > 18 && index < 30 ? 1 : 0.4,
                        }}
                      />
                    ))}
                  </div>
                  {clips.map((clip, index) => (
                    <div
                      key={clip.title}
                      className={`rounded-lg border p-2.5 ${index === 0 ? "border-flame-500/30 bg-flame-500/5" : "border-white/8 bg-ink-850/60"}`}
                    >
                      <div className="flex items-start gap-2.5">
                        <ScoreRing score={clip.score} size={36} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[11.5px] font-medium text-paper">{clip.title}</p>
                          <p className="mt-0.5 font-mono text-[9px] text-faint">{clip.time} · {clip.tag}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        <section className="border-y border-white/7 py-8">
          <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-[11.5px] text-faint">
            <span className="font-mono text-[10px]">WORKS WITH</span>
            {["YouTube", "Twitch", "Kick", "Whisper / faster-whisper", "OpenAI · Anthropic · Gemini", "Ollama", "FFmpeg", "S3"].map(
              (item) => (
                <span key={item} className="flex items-center gap-1.5">
                  <span className="h-1 w-1 rounded-full bg-flame-500/70" />
                  {item}
                </span>
              ),
            )}
          </div>
        </section>

        <section id="workflow" className="py-20">
          <div className="mb-10 max-w-2xl">
            <p className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-flame-500">The pipeline</p>
            <h2 className="text-[30px] font-semibold tracking-tight sm:text-[36px]">
              From a two-hour recording to publishable clips
            </h2>
            <p className="mt-3 text-[14px] leading-relaxed text-muted">
              Four stages, each one visible in the product. Nothing happens in a hidden backend you cannot inspect.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, index) => (
              <motion.div
                key={step.number}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.4, delay: index * 0.06 }}
                className="rounded-xl border border-white/8 bg-ink-900 p-5"
              >
                <span className="font-mono text-[10px] text-flame-500">{step.number}</span>
                <h3 className="mt-4 text-[14px] font-semibold">{step.title}</h3>
                <p className="mt-2 text-[12.5px] leading-relaxed text-muted">{step.body}</p>
              </motion.div>
            ))}
          </div>
        </section>

        <section id="features" className="pb-20">
          <div className="mb-10 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div className="max-w-xl">
              <p className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-flame-500">Capabilities</p>
              <h2 className="text-[30px] font-semibold tracking-tight sm:text-[36px]">
                Everything between raw footage and a post
              </h2>
            </div>
            <Link href="/register" className="text-[13px] text-flame-400 hover:text-flame-500">
              Try the full pipeline <ArrowRight className="ml-1 inline h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <div key={feature.title} className="group rounded-xl border border-white/8 bg-ink-900 p-5 transition-colors hover:border-white/16">
                <feature.icon className="h-5 w-5 text-flame-500" />
                <h3 className="mt-4 text-[14px] font-semibold">{feature.title}</h3>
                <p className="mt-2 text-[12.5px] leading-relaxed text-muted">{feature.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="ownership" className="mb-20 overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-ink-900 to-ink-850">
          <div className="grid gap-8 p-8 sm:p-10 lg:grid-cols-[1.2fr_1fr] lg:items-center">
            <div>
              <p className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-ember">Built to be owned</p>
              <h2 className="text-[26px] font-semibold tracking-tight sm:text-[32px]">
                Your footage stays on your infrastructure.
              </h2>
              <p className="mt-3 max-w-xl text-[13.5px] leading-relaxed text-muted">
                Run FireClip with Docker Compose, keep media in local storage or your own S3 bucket,
                and choose local Whisper for transcription. No lock-in to a single AI provider and no
                silent uploads to services you did not configure.
              </p>
              <div className="mt-6 flex flex-wrap gap-2">
                {["Local transcription", "PostgreSQL + Redis", "S3-compatible storage", "ARQ workers"].map((item) => (
                  <span key={item} className="rounded-md border border-white/10 bg-black/20 px-2.5 py-1 text-[11px] text-muted">
                    {item}
                  </span>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-white/8 bg-ink-950/60 p-5">
              <p className="font-mono text-[10px] text-faint">docker-compose up</p>
              <div className="mt-3 space-y-1.5 font-mono text-[11px]">
                {[
                  ["api", "ready"],
                  ["worker", "ready"],
                  ["postgres", "healthy"],
                  ["redis", "healthy"],
                  ["web", "ready"],
                ].map(([service, state]) => (
                  <div key={service} className="flex items-center justify-between">
                    <span className="text-muted">{service}</span>
                    <span className="text-mint">{state}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 border-t border-white/8 pt-3 text-[11px] text-faint">
                One command. No vendor accounts required.
              </div>
            </div>
          </div>
        </section>

        <section className="mb-20 text-center">
          <h2 className="text-[30px] font-semibold tracking-tight sm:text-[38px]">
            Your next clip is already in the footage.
          </h2>
          <p className="mx-auto mt-3 max-w-md text-[13.5px] leading-relaxed text-muted">
            Create a workspace, bring one video, and see what the analysis finds.
          </p>
          <div className="mt-7 flex justify-center gap-3">
            <Link href="/register">
              <Button size="lg">
                Start free <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/docs">
              <Button variant="outline" size="lg">
                Read the docs
              </Button>
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/7">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-5 py-7 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Logo size={24} />
            <span className="text-[11px] text-faint">Find the moment. Make it viral.</span>
          </div>
          <div className="flex items-center gap-5 text-[11.5px] text-faint">
            <Link href="/docs" className="hover:text-paper">Documentation</Link>
            <Link href="/login" className="hover:text-paper">Sign in</Link>
            <span className="font-mono">v1.0</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
