"use client";

import Link from "next/link";
import * as React from "react";
import { Check, Flame, Merge, Search, Sparkles, Trash2, X } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { ClipCard } from "@/components/clip-card";
import { Alert, Button, EmptyState, Input, PageSkeleton, Panel, Select, Tabs } from "@/components/ui";
import { useApi, useDebounced } from "@/lib/hooks";
import type { Clip, Video } from "@/lib/types";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";

export default function ClipsPage() {
  const [status, setStatus] = React.useState("all");
  const [sort, setSort] = React.useState("score");
  const [videoId, setVideoId] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = React.useState<string | null>(null);
  const debounced = useDebounced(search, 300);

  const query = new URLSearchParams();
  if (status !== "all") query.set("status", status);
  query.set("sort", sort);
  if (videoId) query.set("video_id", videoId);
  if (debounced.trim()) query.set("search", debounced.trim());

  const { data, error, loading, refresh } = useApi<Clip[]>(`/api/clips?${query.toString()}`, {
    pollMs: 8000,
  });
  const videos = useApi<Video[]>("/api/videos?limit=300");

  const clips = data || [];
  const approved = clips.filter((clip) => clip.status === "approved").length;

  React.useEffect(() => {
    setSelected((current) => {
      const visible = new Set(clips.map((clip) => clip.id));
      const next = new Set([...current].filter((id) => visible.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [clips]);

  function toggleSelect(clip: Clip) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(clip.id)) next.delete(clip.id);
      else next.add(clip.id);
      return next;
    });
  }

  async function bulkAction(action: "approve" | "reject" | "delete" | "merge") {
    if (selected.size === 0) return;
    if (action === "delete" && !window.confirm("Delete " + selected.size + " clips? This cannot be undone.")) return;
    if (action === "merge" && selected.size < 2) {
      toast("Select at least two clips to merge", "error");
      return;
    }
    setBulkBusy(action);
    try {
      await api.post("/api/clips/bulk", { action, clip_ids: [...selected] });
      toast(
        action === "merge" ? "Clips merged" : action === "delete" ? "Clips deleted" : "Clips " + action + "d",
        "success",
      );
      setSelected(new Set());
      refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBulkBusy(null);
    }
  }
  const avgScore = clips.length
    ? Math.round(clips.reduce((sum, clip) => sum + clip.virality_score, 0) / clips.length)
    : 0;

  return (
    <div>
      <PageHeader        title="Clip discovery"
        description="Review every candidate the analysis found across this workspace. Approve what earns a render, reject what does not."
        actions={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setSelected(new Set(clips.map((clip) => clip.id)))}
              disabled={clips.length === 0}
            >
              Select all
            </Button>
            <Link href="/videos">
              <Button size="sm">
                <Sparkles className="h-3.5 w-3.5" /> Find more clips
              </Button>
            </Link>
          </div>
        }
      />

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["Candidates", clips.length],
          ["Approved", approved],
          ["Average score", avgScore],
          ["With transcript", clips.filter((clip) => clip.transcript_text).length],
        ].map(([label, value]) => (
          <Panel key={String(label)} className="px-4 py-3">
            <p className="text-[11px] text-faint">{label}</p>
            <p className="mt-1 font-mono text-[20px] font-semibold text-paper">{value}</p>
          </Panel>
        ))}
      </div>

      <Panel className="mb-5">
        <div className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
            <Input
              className="pl-9"
              placeholder="Search clip titles and transcripts"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Select value={videoId} onChange={(event) => setVideoId(event.target.value)} className="sm:w-[220px]">
            <option value="">All videos</option>
            {(videos.data || []).map((video) => (
              <option key={video.id} value={video.id}>
                {video.title.slice(0, 48)}
              </option>
            ))}
          </Select>
          <Select value={sort} onChange={(event) => setSort(event.target.value)} className="sm:w-[150px]">
            <option value="score">Highest score</option>
            <option value="recent">Newest</option>
            <option value="duration">Longest</option>
          </Select>
        </div>
        <div className="px-3">
          <Tabs
            value={status}
            onValueChange={setStatus}
            tabs={[
              { value: "all", label: "All" },
              { value: "suggested", label: "Suggested" },
              { value: "approved", label: "Approved", count: approved },
              { value: "rejected", label: "Rejected" },
            ]}
          />
        </div>
      </Panel>

      {error ? <Alert className="mb-4">{error}</Alert> : null}

      {selected.size > 0 ? (
        <Panel className="mb-4 flex flex-wrap items-center gap-2 px-3 py-2.5">
          <span className="mr-2 text-[12px] text-muted">
            <span className="font-mono text-paper">{selected.size}</span> selected
          </span>
          <Button size="sm" variant="ghost" loading={bulkBusy === "approve"} onClick={() => bulkAction("approve")}>
            <Check className="h-3 w-3" /> Approve
          </Button>
          <Button size="sm" variant="ghost" loading={bulkBusy === "reject"} onClick={() => bulkAction("reject")}>
            <X className="h-3 w-3" /> Reject
          </Button>
          <Button
            size="sm"
            variant="ghost"
            loading={bulkBusy === "merge"}
            disabled={selected.size < 2}
            onClick={() => bulkAction("merge")}
          >
            <Merge className="h-3 w-3" /> Merge
          </Button>
          <Button size="sm" variant="danger" loading={bulkBusy === "delete"} onClick={() => bulkAction("delete")}>
            <Trash2 className="h-3 w-3" /> Delete
          </Button>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => setSelected(new Set(clips.map((clip) => clip.id)))}
              className="text-[11px] text-faint hover:text-paper"
            >
              Select all
            </button>
            <button onClick={() => setSelected(new Set())} className="text-[11px] text-faint hover:text-paper">
              Clear
            </button>
          </div>
        </Panel>
      ) : null}

      {loading && !data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <PageSkeleton key={index} />
          ))}
        </div>
      ) : clips.length === 0 ? (
        <Panel>
          <EmptyState
            icon={<Flame className="h-5 w-5" />}
            title="No candidates in view"
            description="Open a transcribed video and run clip analysis, or clear these filters."
            action={
              <Link href="/videos">
                <Button size="sm">Go to the library</Button>
              </Link>
            }
          />
        </Panel>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {clips.map((clip) => (
            <ClipCard
              key={clip.id}
              clip={clip}
              onChanged={refresh}
              selected={selected.has(clip.id)}
              onToggleSelect={toggleSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}
