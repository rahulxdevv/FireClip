"use client";

import { useRouter } from "next/navigation";
import * as React from "react";
import { Check, ChevronDown, Copy, Pencil, Sparkles, X } from "lucide-react";
import { Badge, Button, Dialog, ScoreRing, Skeleton } from "@/components/ui";
import { SignalBars } from "@/components/charts";
import { api, errorMessage } from "@/lib/api";
import { formatDuration, formatTimecode } from "@/lib/format";
import { toast } from "@/lib/stores";
import type { Clip, ClipContent } from "@/lib/types";
import { cn } from "@/lib/cn";

export function ClipCard({
  clip,
  onChanged,
  compact = false,
}: {
  clip: Clip;
  onChanged?: () => void;
  compact?: boolean;
}) {
  const router = useRouter();
  const [expanded, setExpanded] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [contentOpen, setContentOpen] = React.useState(false);
  const [content, setContent] = React.useState<ClipContent | null>(null);
  const [contentError, setContentError] = React.useState<string | null>(null);
  const [loadingContent, setLoadingContent] = React.useState(false);

  const topSignals = Object.entries(clip.signals || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  async function setStatus(status: "approved" | "rejected") {
    setBusy(status);
    try {
      await api.post(`/api/clips/${clip.id}/${status === "approved" ? "approve" : "reject"}`);
      toast(status === "approved" ? "Clip approved" : "Clip rejected", "success");
      onChanged?.();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function openEditor() {
    setBusy("editor");
    try {
      const project = await api.post<{ id: string }>(`/api/clips/${clip.id}/editor`, {});
      router.push(`/editor/${project.id}`);
    } catch (err) {
      toast(errorMessage(err), "error");
      setBusy(null);
    }
  }

  async function openContent() {
    setContentOpen(true);
    if (content) return;
    setLoadingContent(true);
    setContentError(null);
    try {
      const data = await api.post<ClipContent>(`/api/clips/${clip.id}/content`);
      setContent(data);
    } catch (err) {
      setContentError(errorMessage(err));
    } finally {
      setLoadingContent(false);
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-white/8 bg-ink-900">
      <div className={cn("p-4", compact && "p-3.5")}>
        <div className="flex items-start gap-3">
          <ScoreRing score={clip.virality_score} size={compact ? 38 : 44} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="min-w-0 flex-1 text-[13px] font-medium leading-snug text-paper">{clip.title}</p>
              <Badge
                tone={clip.status === "approved" ? "mint" : clip.status === "rejected" ? "rose" : "neutral"}
              >
                {clip.status}
              </Badge>
            </div>
            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[10.5px] text-faint">
              <span>{formatTimecode(clip.start_ms)} → {formatTimecode(clip.end_ms)}</span>
              <span>·</span>
              <span>{formatDuration(clip.duration_ms, true)}</span>
              <span>·</span>
              <span>{clip.aspect_ratio}</span>
              {clip.source === "manual" ? (
                <>
                  <span>·</span>
                  <span className="text-ember">manual</span>
                </>
              ) : null}
            </p>
          </div>
        </div>

        {topSignals.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {topSignals.map(([key, value]) => (
              <span
                key={key}
                className="rounded border border-white/8 bg-ink-850 px-1.5 py-0.5 font-mono text-[9.5px] capitalize text-muted"
              >
                {key.replace(/_/g, " ")} {Math.round(value)}
              </span>
            ))}
          </div>
        ) : null}

        <p className="mt-3 line-clamp-2 text-[12px] leading-relaxed text-muted">{clip.explanation}</p>

        <div className="mt-3.5 flex flex-wrap items-center gap-1.5">
          <Button size="sm" onClick={openEditor} loading={busy === "editor"}>
            <Pencil className="h-3 w-3" /> Edit clip
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setStatus("approved")}
            loading={busy === "approved"}
            disabled={clip.status === "approved"}
          >
            <Check className="h-3 w-3" /> Approve
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setStatus("rejected")}
            loading={busy === "rejected"}
            disabled={clip.status === "rejected"}
          >
            <X className="h-3 w-3" /> Reject
          </Button>
          <Button size="sm" variant="ghost" onClick={openContent}>
            <Sparkles className="h-3 w-3" /> Social copy
          </Button>
          <button
            onClick={() => setExpanded((value) => !value)}
            className="ml-auto flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-faint hover:text-paper"
          >
            Details
            <ChevronDown className={cn("h-3 w-3 transition-transform", expanded && "rotate-180")} />
          </button>
        </div>
      </div>

      {expanded ? (
        <div className="space-y-4 border-t border-white/7 bg-ink-850/40 p-4">
          <div>
            <p className="label-caps mb-2">Signal breakdown</p>
            <SignalBars signals={clip.signals || {}} />
          </div>
          <div>
            <p className="label-caps mb-1.5">Original transcript</p>
            <p className="max-h-40 overflow-y-auto whitespace-pre-wrap text-[12px] leading-relaxed text-muted">
              {clip.transcript_text || "No transcript text stored for this clip."}
            </p>
          </div>
          {clip.hook ? (
            <div>
              <p className="label-caps mb-1">Hook</p>
              <p className="text-[12px] text-paper">{clip.hook}</p>
            </div>
          ) : null}
        </div>
      ) : null}

      <Dialog
        open={contentOpen}
        onOpenChange={setContentOpen}
        title="Social copy"
        description="Generated from this clip's transcript. Review before publishing."
        wide
      >
        {loadingContent ? (
          <div className="space-y-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        ) : contentError ? (
          <p className="text-[13px] text-rose">{contentError}</p>
        ) : content ? (
          <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
            <CopyBlock title="Titles" items={content.titles} />
            <CopyBlock title="Hooks" items={content.hooks} />
            <CopyBlock title="Hashtags" items={[content.hashtags.join(" ")]} mono />
            <div>
              <p className="label-caps mb-1.5">Platform captions</p>
              <div className="space-y-2">
                {Object.entries(content.captions).map(([platform, caption]) => (
                  <div key={platform} className="rounded-lg border border-white/8 bg-ink-850 p-3">
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-[11px] capitalize text-muted">{platform}</span>
                      <CopyButton text={caption} />
                    </div>
                    <p className="whitespace-pre-wrap text-[11.5px] leading-relaxed text-faint">{caption}</p>
                  </div>
                ))}
              </div>
            </div>
            <CopyBlock title="Thumbnail ideas" items={content.thumbnail_ideas} />
            <CopyBlock title="Calls to action" items={content.calls_to_action} />
            <p className="font-mono text-[10px] text-faint">
              generated by {content.provider} · {content.model}
            </p>
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}

function CopyBlock({ title, items, mono }: { title: string; items: string[]; mono?: boolean }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="label-caps mb-1.5">{title}</p>
      <div className="space-y-1.5">
        {items.map((item, index) => (
          <div
            key={`${title}-${index}`}
            className="flex items-start justify-between gap-3 rounded-lg border border-white/8 bg-ink-850 px-3 py-2"
          >
            <p className={cn("text-[11.5px] leading-relaxed text-muted", mono && "font-mono")}>{item}</p>
            <CopyButton text={item} />
          </div>
        ))}
      </div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        } catch {
          toast("Clipboard permission denied", "error");
        }
      }}
      className="shrink-0 rounded p-1 text-faint transition-colors hover:text-paper"
      aria-label="Copy"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-mint" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}
