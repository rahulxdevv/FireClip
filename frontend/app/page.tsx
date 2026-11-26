"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  CalendarClock,
  Captions,
  Crop,
  Film,
  Flame,
  Play,
  Server,
  Sparkles,
  Users,
} from "lucide-react";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";

const NAV_LINKS = [
  { href: "#product", label: "Product" },
  { href: "#features", label: "Features" },
  { href: "#how", label: "How it works" },
  { href: "/docs", label: "Docs" },
];

const CLIPS = [
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

const FEATURES = [
  {
    icon: Flame,
    title: "Find the moment",
    body: "Twelve transcript signals, one score, and a written reason for every pick.",
  },
  {
    icon: Captions,
    title: "Frame and caption",
    body: "Subject aware 9:16 framing with word level captions you can restyle in seconds.",
  },
  {
    icon: CalendarClock,
    title: "Publish on schedule",
    body: "Queue an export to a connected account, or hand the link to your client.",
  },
];

const STEPS = [
  {
    number: "01",
    title: "Drop in the long version",
    body: "Upload a file or paste a YouTube, Twitch or Kick link.",
  },
  {
    number: "02",
    title: "Review what it found",
    body: "Each clip arrives with its score, its reason and its transcript range.",
  },
  {
    number: "03",
    title: "Render and ship",
    body: "Style the captions, export the presets you need, schedule the post.",
  },
];

const SIGNAL_HEIGHTS = [38, 52, 30, 64, 44, 72, 58, 36, 61, 47, 70, 55, 33, 66, 49, 74, 42, 58, 63, 39];

export default function LandingPage() {
  return (
    <div className="sheet min-h-screen">
      <SiteHeader />
      <main>
        <Hero />
        <Features />
        <Steps />
      </main>
      <SiteFooter />
    </div>
  );
}

function Wordmark() {
  return <Logo size={24} />;
}

function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className="sticky top-0 z-50 px-4 pt-4 sm:px-6 sm:pt-5">
      <div
        className={
          "mk-nav relative mx-auto flex h-[58px] w-full max-w-[1080px] items-center gap-3 rounded-full px-3 transition-shadow duration-300 sm:px-4 " +
          (scrolled ? "shadow-[var(--mk-nav-shadow)]" : "shadow-none")
        }
      >
        <Link href="/" aria-label="FireClip home" className="shrink-0">
          <Wordmark />
        </Link>
        <nav className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-0.5 lg:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-full px-3.5 py-2 text-[13px] font-medium text-ash transition-colors hover:bg-cream hover:text-night"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle tone="marketing" />
          <Link
            href="/login"
            className="hidden rounded-full px-3 py-2 text-[13px] font-medium text-ash transition-colors hover:text-night sm:inline-flex"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="inline-flex h-9 items-center gap-1.5 whitespace-nowrap rounded-full bg-[var(--mk-solid)] px-4 text-[13px] font-semibold text-[var(--mk-solid-fg)] transition-opacity hover:opacity-90"
          >
            Get started
            <ArrowRight className="hidden h-3.5 w-3.5 sm:block" />
          </Link>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative isolate overflow-hidden pb-16 pt-16 sm:pb-24 sm:pt-24">
      <div aria-hidden className="mk-hero pointer-events-none absolute inset-x-0 top-0 h-[640px]" />
      <div className="relative mx-auto w-full max-w-[1120px] px-5 sm:px-6">
        <div className="mx-auto max-w-[860px] text-center">
          <h1 className="text-[44px] font-semibold leading-[1.02] tracking-[-0.05em] text-night sm:text-[64px] lg:text-[76px]">
            Turn long videos into
            <span className="block text-ash">clips worth watching.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-[54ch] text-[15.5px] leading-relaxed text-ash sm:text-[17px]">
            FireClip reads the whole recording, finds the moments that carry, frames them for vertical,
            captions every word and schedules the post.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-2.5 sm:flex-row">
            <Link
              href="/register"
              className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-full bg-flame-600 px-6 text-[14.5px] font-semibold text-white transition-colors hover:bg-flame-500 sm:w-auto"
            >
              Get started
              <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href="#how"
              className="mk-pill inline-flex h-12 w-full items-center justify-center gap-2 px-6 text-[14.5px] font-semibold transition-colors hover:border-[var(--mk-line-strong)] sm:w-auto"
            >
              <Play className="h-4 w-4" />
              See how it works
            </a>
          </div>
          <p className="mt-4 text-[12.5px] text-faint">
            Self-hosted · No watermarks · Every pick explained
          </p>
        </div>
        <ProductFrame />
      </div>
    </section>
  );
}

function ProductFrame() {
  const points = SIGNAL_HEIGHTS.map(
    (value, index) =>
      (index / (SIGNAL_HEIGHTS.length - 1)) * 120 + "," + (24 - (value / 100) * 20),
  ).join(" L ");

  return (
    <div className="relative mx-auto mt-14 max-w-[1040px] sm:mt-20">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-16 -bottom-8 h-24 rounded-[50%] bg-flame-500/20 blur-3xl"
      />
      <div className="relative rounded-[28px] border border-[var(--mk-line)] bg-[var(--mk-card)] p-1.5 shadow-[var(--mk-frame-shadow)] sm:p-2">
        <div className="overflow-hidden rounded-[21px] border border-hair">
          <div className="flex h-11 items-center gap-2 border-b border-hair bg-[var(--mk-bg-soft)] px-4">
            <span className="flex gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[var(--mk-line-strong)]" />
              <span className="h-2 w-2 rounded-full bg-[var(--mk-line-strong)]" />
              <span className="h-2 w-2 rounded-full bg-[var(--mk-line-strong)]" />
            </span>
            <span className="ml-3 text-[11.5px] font-medium text-ash">Clip discovery</span>
            <span className="ml-auto hidden rounded-full bg-mist px-2.5 py-1 text-[10.5px] font-medium text-flame-600 sm:block">
              6 clips found
            </span>
          </div>
          <div className="grid bg-[var(--mk-card)] sm:grid-cols-[184px_1fr]">
            <div className="hidden flex-col gap-1 border-r border-hair p-3 sm:flex">
              {["Overview", "Transcript", "Highlights", "Captions", "Framing", "Publish"].map((label) => {
                const active = label === "Highlights";
                return (
                  <span
                    key={label}
                    className={
                      "flex items-center gap-2 rounded-[10px] px-2.5 py-1.5 text-[12px] " +
                      (active ? "bg-cream font-medium text-night" : "text-ash")
                    }
                  >
                    <span className={"h-1 w-1 rounded-full " + (active ? "bg-flame-500" : "bg-[var(--mk-line-strong)]")} />
                    {label}
                  </span>
                );
              })}
            </div>
            <div className="p-3 sm:p-4">
              <div className="mb-3 flex items-center gap-2.5 rounded-[12px] border border-hair bg-[var(--mk-bg-soft)] px-3 py-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-mist text-flame-600">
                  <Film className="h-4 w-4" />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-[12.5px] font-semibold text-night">The Long Game, Episode 41</p>
                  <p className="text-[10.5px] text-faint">54:12, podcast, English</p>
                </div>
                <span className="ml-auto hidden rounded-[8px] border border-hair px-2 py-0.5 text-[10px] text-ash sm:block">
                  9:16
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                {CLIPS.map((clip, index) => (
                  <figure key={clip.title} className={index === 2 ? "hidden min-w-0 sm:block" : "min-w-0"}>
                    <div className="relative aspect-[9/16] overflow-hidden rounded-[12px] bg-[radial-gradient(90%_70%_at_50%_10%,#3b2f7d_0%,#1a1533_55%,#0a0912_100%)]">
                      <span
                        aria-hidden
                        className="absolute inset-0"
                        style={{
                          background:
                            "radial-gradient(110% 60% at 76% 12%, rgba(111,92,252,0.5), rgba(10,9,18,0) 68%)",
                        }}
                      />
                      <span className="absolute left-1/2 top-[40%] flex h-7 w-7 -translate-x-1/2 items-center justify-center rounded-full border border-white/20 bg-white/10 text-white backdrop-blur">
                        <Play className="h-2.5 w-2.5 translate-x-[1px]" fill="currentColor" />
                      </span>
                      <span className="absolute inset-x-2 top-2 flex items-start justify-between gap-1">
                        <span className="rounded-full bg-black/45 px-1.5 py-0.5 text-[8.5px] text-white/75">
                          {clip.tag}
                        </span>
                        <span className="flex h-6 min-w-6 items-center justify-center rounded-full border border-white/15 bg-black/40 px-1 text-[9px] font-semibold text-white">
                          {clip.score}
                        </span>
                      </span>
                      <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/55 to-transparent px-2 pb-2.5 pt-8">
                        <span className="block text-[10px] font-semibold leading-snug text-white">
                          {clip.caption[0]}
                          <span className="rounded-[3px] bg-flame-500 px-[3px] text-white">{clip.caption[1]}</span>
                          {clip.caption[2]}
                        </span>
                        <span className="mt-1 block text-[8.5px] text-white/55">{clip.time}</span>
                      </span>
                    </div>
                    <figcaption className="mt-2 flex items-center justify-between gap-2">
                      <span className="truncate text-[10px] text-ash">{clip.title}</span>
                      <span className="shrink-0 text-[10px] font-medium text-flame-600">{clip.score}</span>
                    </figcaption>
                  </figure>
                ))}
              </div>
              <div className="mt-3 flex items-center gap-2.5 rounded-[12px] border border-hair bg-[var(--mk-bg-soft)] px-3 py-2">
                <span className="text-[10px] text-faint">Signals</span>
                <svg viewBox="0 0 120 24" preserveAspectRatio="none" className="h-8 flex-1" aria-hidden>
                  <defs>
                    <linearGradient id="signal-fill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6f5cfc" stopOpacity="0.32" />
                      <stop offset="100%" stopColor="#6f5cfc" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <path d={"M " + points + " L 120 24 L 0 24 Z"} fill="url(#signal-fill)" />
                  <path
                    d={"M " + points}
                    fill="none"
                    stroke="#6f5cfc"
                    strokeWidth="1.4"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Features() {
  return (
    <section id="product" className="mx-auto w-full max-w-[1120px] scroll-mt-28 px-5 py-20 sm:px-6 sm:py-28">
      <div id="features" className="mx-auto max-w-2xl scroll-mt-28 text-center">
        <h2 className="text-[32px] font-semibold leading-[1.08] tracking-[-0.04em] text-night sm:text-[46px]">
          Everything after the upload.
        </h2>
        <p className="mx-auto mt-4 max-w-[48ch] text-[14.5px] leading-relaxed text-ash">
          Three jobs, done in one workspace: choose the clip, make it look right, put it out.
        </p>
      </div>
      <div className="mt-12 grid gap-4 lg:grid-cols-3">
        <FeatureCard feature={FEATURES[0]}>
          <div className="space-y-2.5">
            {[
              ["Audience growth", 87],
              ["The wrong moment", 79],
              ["One changed line", 74],
            ].map(([label, score]) => (
              <div key={String(label)} className="flex items-center gap-3 rounded-[12px] border border-hair bg-[var(--mk-card)] px-3 py-2.5">
                <span className="w-7 text-center text-[12px] font-semibold text-flame-600">{score}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12px] font-medium text-night">{label}</span>
                  <span className="mt-1 block h-1 w-full overflow-hidden rounded-full bg-[var(--mk-line)]">
                    <span
                      className="block h-full rounded-full bg-flame-500"
                      style={{ width: String(score) + "%" }}
                    />
                  </span>
                </span>
              </div>
            ))}
          </div>
        </FeatureCard>
        <FeatureCard feature={FEATURES[1]}>
          <div className="flex items-center justify-center gap-3">
            <div className="relative aspect-[9/16] w-[116px] overflow-hidden rounded-[14px] border border-[var(--mk-line-strong)] bg-[radial-gradient(90%_70%_at_50%_10%,#3b2f7d_0%,#1a1533_55%,#0a0912_100%)]">
              <span className="absolute inset-x-2 bottom-3 text-center text-[10px] font-semibold leading-snug text-white">
                retention doubled after
                <br />
                <span className="rounded-[3px] bg-flame-500 px-1">one line</span>
              </span>
            </div>
            <div className="flex flex-col gap-1.5">
              {["Bold", "Karaoke", "Box", "Outline"].map((style, index) => (
                <span
                  key={style}
                  className={
                    "rounded-full px-2.5 py-1 text-[10.5px] font-medium " +
                    (index === 1 ? "bg-flame-500 text-white" : "border border-hair bg-[var(--mk-card)] text-ash")
                  }
                >
                  {style}
                </span>
              ))}
            </div>
          </div>
        </FeatureCard>
        <FeatureCard feature={FEATURES[2]}>
          <div className="space-y-2">
            {[
              ["YouTube Shorts", "Today, 18:30"],
              ["Instagram Reels", "Tomorrow, 09:00"],
              ["TikTok", "Tomorrow, 14:15"],
            ].map(([platform, time]) => (
              <div key={platform} className="flex items-center gap-2.5 rounded-[12px] border border-hair bg-[var(--mk-card)] px-3 py-2.5">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-mist text-flame-600">
                  <CalendarClock className="h-3 w-3" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12px] font-medium text-night">{platform}</span>
                  <span className="block text-[10.5px] text-faint">{time}</span>
                </span>
                <span className="h-1.5 w-1.5 rounded-full bg-mint" />
              </div>
            ))}
          </div>
        </FeatureCard>
      </div>
      <div className="mt-14 grid gap-x-8 gap-y-7 border-t border-hair pt-10 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { icon: Sparkles, title: "Explained picks", body: "Score, signals and a reason for every candidate." },
          { icon: Crop, title: "Subject framing", body: "9:16, 1:1, 4:5 and 16:9 with face detection." },
          { icon: Users, title: "Review built in", body: "Comments, approvals and roles per workspace." },
          { icon: Server, title: "Your infrastructure", body: "Compose it, own the storage and the keys." },
        ].map((item) => (
          <div key={item.title}>
            <item.icon className="h-4 w-4 text-flame-600" />
            <h3 className="mt-3 text-[14px] font-semibold text-night">{item.title}</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-ash">{item.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function FeatureCard({ feature, children }: { feature: (typeof FEATURES)[number]; children: React.ReactNode }) {
  return (
    <article className="mk-card flex flex-col p-5">
      <div className="mb-5 flex h-9 w-9 items-center justify-center rounded-[11px] bg-mist text-flame-600">
        <feature.icon className="h-4 w-4" />
      </div>
      <h3 className="text-[16px] font-semibold tracking-[-0.02em] text-night">{feature.title}</h3>
      <p className="mb-4 mt-1.5 text-[13px] leading-relaxed text-ash">{feature.body}</p>
      <div className="mt-auto">{children}</div>
    </article>
  );
}

function Steps() {
  return (
    <section id="how" className="scroll-mt-28 border-y border-hair bg-[var(--mk-bg-soft)] py-20 sm:py-28">
      <div className="mx-auto w-full max-w-[1120px] px-5 sm:px-6">
        <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:gap-20">
          <div>
            <h2 className="text-[32px] font-semibold leading-[1.08] tracking-[-0.04em] text-night sm:text-[42px]">
              Three steps, one loop.
            </h2>
            <p className="mt-4 max-w-[34ch] text-[14.5px] leading-relaxed text-ash">
              No timelines to learn, no settings to memorise. FireClip proposes, you decide.
            </p>
          </div>
          <div className="grid gap-8 sm:grid-cols-3 sm:gap-6">
            {STEPS.map((step) => (
              <div key={step.number} className="border-t border-[var(--mk-line-strong)] pt-5">
                <span className="font-mono text-[11.5px] font-medium text-flame-600">{step.number}</span>
                <h3 className="mt-3 text-[16px] font-semibold tracking-[-0.02em] text-night">{step.title}</h3>
                <p className="mt-2 text-[13px] leading-relaxed text-ash">{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function SiteFooter() {
  return (
    <footer>
      <div className="mx-auto flex w-full max-w-[1120px] flex-col gap-8 px-5 py-12 sm:flex-row sm:items-start sm:justify-between sm:px-6">
        <div>
          <Wordmark />
          <p className="mt-3 max-w-xs text-[12.5px] leading-relaxed text-ash">
            Clipping, editing and scheduling for long video.
          </p>
        </div>
        <div className="flex flex-wrap gap-x-7 gap-y-2 text-[12.5px] text-ash">
          <a href="#product" className="transition-colors hover:text-night">Product</a>
          <a href="#features" className="transition-colors hover:text-night">Features</a>
          <Link href="/docs" className="transition-colors hover:text-night">Docs</Link>
          <Link href="/login" className="transition-colors hover:text-night">Sign in</Link>
          <Link href="/register" className="transition-colors hover:text-night">Get started</Link>
        </div>
      </div>
      <div className="mx-auto w-full max-w-[1120px] border-t border-hair px-5 py-5 text-[11.5px] text-faint sm:px-6">
        FireClip. Built for people who ship clips.
      </div>
    </footer>
  );
}
