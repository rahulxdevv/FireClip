"use client";

import { useRouter } from "next/navigation";
import * as React from "react";
import { Check, ChevronDown, Copy, MessageSquare, Pencil, Sparkles, X } from "lucide-react";
import { Badge, Button, Dialog, ScoreRing, Skeleton, Textarea } from "@/components/ui";
import { SignalBars } from "@/components/charts";
import { api, errorMessage } from "@/lib/api";
import { formatDuration, formatTimecode, relativeTime } from "@/lib/format";
import { toast } from "@/lib/stores";
import type { Clip, ClipComment, ClipContent } from "@/lib/types";
import { cn } from "@/lib/cn";

export function ClipCard({
  clip,
  onChanged,
  compact = false,
  selected = false,
  onToggleSelect,
}: {
  clip: Clip;
  onChanged?: () => void;
  compact?: boolean;
  selected?: boolean;
  onToggleSelect?: (clip: Clip) => void;
}) {
  const router = useRouter();
  const [expanded, setExpanded] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [contentOpen, setContentOpen] = React.useState(false);
  const [content, setContent] = React.useState<ClipContent | null>(null);
  const [contentError, setContentError] = React.useState<string | null>(null);
  const [loadingContent, setLoadingContent] = React.useState(false);
  const [comments, setComments] = React.useState<ClipComment[]>([]);
  const [commentsLoading, setCommentsLoading] = React.useState(false);
  const [commentText, setCommentText] = React.useState("");
  const [commentBusy, setCommentBusy] = React.useState<string | null>(null);

  const loadComments = React.useCallback(async () => {
    setCommentsLoading(true);
    try {
      const rows = await api.get<ClipComment[]>(`/api/clips/${clip.id}/comments`);
      setComments(rows);
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setCommentsLoading(false);
    }
  }, [clip.id]);

  React.useEffect(() => {
    if (expanded) void loadComments();
  }, [expanded, loadComments]);

  async function submitComment(event: React.FormEvent) {
    event.preventDefault();
    if (!commentText.trim()) return;
    setCommentBusy("create");
    try {
      const created = await api.post<ClipComment>(`/api/clips/${clip.id}/comments`, { body: commentText.trim() });
      setComments((current) => [...current, created]);
      setCommentText("");
      toast("Comment added", "success");
      onChanged?.();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setCommentBusy(null);
    }
  }

  async function toggleResolved(comment: ClipComment) {
    setCommentBusy(comment.id);
    try {
      const updated = await api.patch<ClipComment>(`/api/clips/${clip.id}/comments/${comment.id}`, {
        resolved: !comment.resolved_at,
      });
      setComments((current) => current.map((item) => (item.id === comment.id ? updated : item)));
      onChanged?.();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setCommentBusy(null);
    }
  }

  async function removeComment(comment: ClipComment) {
    if (!window.confirm("Delete this comment?")) return;
    setCommentBusy(comment.id);
    try {
      await api.delete(`/api/clips/${clip.id}/comments/${comment.id}`);
      setComments((current) => current.filter((item) => item.id !== comment.id));
      onChanged?.();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setCommentBusy(null);
    }
  }

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
    <div className="overflow-hidden rounded-[var(--radius-card)] border border-paper/8 bg-ink-900">
      <div className={cn("p-4", compact && "p-3.5")}>
        <div className="flex items-start gap-3">
          {onToggleSelect ? (
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onToggleSelect(clip)}
              aria-label={"Select " + clip.title}
              className="mt-1 h-3.5 w-3.5 shrink-0 accent-flame-500"
            />
          ) : null}
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
            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10.5px] text-faint">
              <span className="font-mono">{formatTimecode(clip.start_ms)} → {formatTimecode(clip.end_ms)}</span>
              <span className="border-l border-paper/[0.1] pl-2">{formatDuration(clip.duration_ms, true)}</span>
              <span className="border-l border-paper/[0.1] pl-2">{clip.aspect_ratio}</span>
              {clip.source === "manual" ? (
                <span className="border-l border-paper/[0.1] pl-2 text-ember">manual</span>
              ) : null}
            </p>
          </div>
        </div>

        {topSignals.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {topSignals.map(([key, value]) => (
              <span
                key={key}
                className="rounded border border-paper/8 bg-ink-850 px-1.5 py-0.5 font-mono text-[9.5px] capitalize text-muted"
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
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setExpanded((value) => !value)}
          >
            <MessageSquare className="h-3 w-3" /> Comments
            {(clip.comment_count || 0) > 0 ? (
              <span className="ml-0.5 rounded bg-paper/8 px-1 font-mono text-[9.5px]">
                {clip.comment_count}
              </span>
            ) : null}
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
        <div className="space-y-4 border-t border-paper/7 bg-ink-850/40 p-4">
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

          <div className="border-t border-paper/7 pt-3">
            <div className="mb-2 flex items-center justify-between">
              <p className="label-caps">Review comments</p>
              {(clip.open_comment_count || 0) > 0 ? (
                <Badge tone="ember">{clip.open_comment_count} open</Badge>
              ) : null}
            </div>
            {commentsLoading && comments.length === 0 ? (
              <Skeleton className="h-12" />
            ) : comments.length === 0 ? (
              <p className="rounded-[var(--radius-control)] border border-paper/8 bg-ink-900/60 px-3 py-3 text-[11.5px] text-faint">
                No comments yet. Leave timing or copy feedback for your team.
              </p>
            ) : (
              <div className="space-y-2">
                {comments.map((comment) => (
                  <div
                    key={comment.id}
                    className={
                      "rounded-[var(--radius-control)] border px-3 py-2.5 " +
                      (comment.resolved_at ? "border-paper/6 bg-ink-900/40 opacity-65" : "border-paper/8 bg-ink-900/70")
                    }
                  >
                    <div className="flex items-center gap-2">
                      <span className="flex h-5 w-5 items-center justify-center rounded bg-flame-500/12 font-mono text-[9px] text-flame-400">
                        {(comment.author_name || comment.author_email).slice(0, 2).toUpperCase()}
                      </span>
                      <span className="text-[11px] font-medium text-paper">
                        {comment.author_name || comment.author_email}
                      </span>
                      <span className="font-mono text-[9.5px] text-faint">{relativeTime(comment.created_at)}</span>
                      {comment.resolved_at ? <Badge tone="mint">resolved</Badge> : null}
                      <div className="ml-auto flex items-center gap-1">
                        <button
                          onClick={() => toggleResolved(comment)}
                          disabled={commentBusy === comment.id}
                          className="rounded px-1.5 py-0.5 text-[10px] text-faint hover:bg-paper/5 hover:text-paper disabled:opacity-40"
                        >
                          {comment.resolved_at ? "Reopen" : "Resolve"}
                        </button>
                        {comment.mine ? (
                          <button
                            onClick={() => removeComment(comment)}
                            disabled={commentBusy === comment.id}
                            className="rounded px-1.5 py-0.5 text-[10px] text-faint hover:bg-paper/5 hover:text-rose disabled:opacity-40"
                          >
                            Delete
                          </button>
                        ) : null}
                      </div>
                    </div>
                    <p className="mt-1.5 whitespace-pre-wrap text-[11.5px] leading-relaxed text-muted">{comment.body}</p>
                  </div>
                ))}
              </div>
            )}
            <form onSubmit={submitComment} className="mt-2.5 space-y-2">
              <Textarea
                value={commentText}
                onChange={(event) => setCommentText(event.target.value)}
                placeholder="Leave feedback for the editor..."
                className="min-h-16 text-[12px]"
                maxLength={2000}
              />
              <div className="flex justify-end">
                <Button size="sm" type="submit" loading={commentBusy === "create"} disabled={!commentText.trim()}>
                  Comment
                </Button>
              </div>
            </form>
          </div>
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
                  <div key={platform} className="rounded-[var(--radius-control)] border border-paper/8 bg-ink-850 p-3">
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
            <p className="text-[10.5px] text-faint">
              Generated by {content.provider}, {content.model}
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
            className="flex items-start justify-between gap-3 rounded-[var(--radius-control)] border border-paper/8 bg-ink-850 px-3 py-2"
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
