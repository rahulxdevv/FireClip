"use client";

import Link from "next/link";
import { Film, Play } from "lucide-react";
import { VideoStatusBadge } from "@/components/status";
import { Progress } from "@/components/ui";
import { formatDuration, relativeTime } from "@/lib/format";
import type { Video } from "@/lib/types";

export function VideoCard({ video }: { video: Video }) {
  const processing = ["uploaded", "downloading", "probing", "transcribing", "analyzing"].includes(video.status);
  return (
    <Link
      href={`/videos/${video.id}`}
      className="group overflow-hidden rounded-[var(--radius-card)] border border-paper/8 bg-ink-900 transition-colors hover:border-paper/16"
    >
      <div className="relative aspect-video overflow-hidden bg-ink-850">
        {video.thumbnail_key ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`/api/videos/${video.id}/thumbnail?v=${encodeURIComponent(video.updated_at)}`}
            alt=""
            className="h-full w-full object-cover opacity-90 transition-opacity group-hover:opacity-100"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-ink-600">
            <Film className="h-7 w-7" />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
        <div className="absolute bottom-2 left-2 flex items-center gap-1.5">
          <span className="rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-paper">
            {formatDuration(video.duration_seconds)}
          </span>
          <span className="rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-paper">
            {video.width}×{video.height}
          </span>
        </div>
        <span className="absolute right-2 top-2">
          <VideoStatusBadge status={video.status} />
        </span>
        <span className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity group-hover:opacity-100">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-black/60">
            <Play className="ml-0.5 h-4 w-4 fill-paper text-paper" />
          </span>
        </span>
      </div>
      <div className="p-3.5">
        <p className="truncate text-[13.5px] font-medium text-paper">{video.title}</p>
        <p className="mt-1 flex items-center gap-1.5 text-[11.5px] text-faint">
          <span className="capitalize">{video.source_type === "upload" ? "Uploaded" : video.source_type}</span>
          <span>{relativeTime(video.created_at)}</span>
          {video.has_audio ? null : (
            <>
              <span className="text-ember">No audio</span>
            </>
          )}
        </p>
        {processing ? (
          <div className="mt-2.5">
            <Progress value={video.progress} />
          </div>
        ) : null}
        {video.status === "error" ? (
          <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-rose">{video.error_message}</p>
        ) : null}
      </div>
    </Link>
  );
}
