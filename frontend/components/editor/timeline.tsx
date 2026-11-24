"use client";

import * as React from "react";
import { cn } from "@/lib/cn";
import { formatTimecode } from "@/lib/format";

export function Timeline({
  durationMs,
  startMs,
  endMs,
  playheadMs,
  segments,
  onChange,
  onSeek,
}: {
  durationMs: number;
  startMs: number;
  endMs: number;
  playheadMs: number;
  segments: Array<{ start_ms: number; end_ms: number; text: string }>;
  onChange: (start: number, end: number) => void;
  onSeek: (ms: number) => void;
}) {
  const trackRef = React.useRef<HTMLDivElement>(null);
  const duration = Math.max(1000, durationMs);
  const startPct = Math.min(100, (startMs / duration) * 100);
  const endPct = Math.min(100, (endMs / duration) * 100);
  const playPct = Math.min(100, (playheadMs / duration) * 100);

  function positionToMs(clientX: number): number {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect) return 0;
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return Math.round(ratio * duration);
  }

  function startDrag(handle: "start" | "end") {
    return (event: React.PointerEvent) => {
      event.preventDefault();
      const move = (moveEvent: PointerEvent) => {
        const ms = positionToMs(moveEvent.clientX);
        if (handle === "start") onChange(Math.min(ms, endMs - 500), endMs);
        else onChange(startMs, Math.max(ms, startMs + 500));
      };
      const up = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    };
  }

  return (
    <div className="rounded-xl border border-white/8 bg-ink-850 p-3">
      <div className="mb-2.5 flex items-center justify-between gap-2 font-mono text-[10px] text-faint">
        <span>{formatTimecode(0)}</span>
        <span className="text-muted">
          {formatTimecode(startMs)} → {formatTimecode(endMs)}
        </span>
        <span>{formatTimecode(durationMs)}</span>
      </div>

      <div
        ref={trackRef}
        className="relative h-20 cursor-crosshair overflow-hidden rounded-lg border border-white/8 bg-ink-900"
        onPointerDown={(event) => {
          if ((event.target as HTMLElement).dataset.handle) return;
          const ms = positionToMs(event.clientX);
          onSeek(ms);
        }}
      >
        <div className="absolute inset-0 flex items-center gap-[1px] px-1 opacity-60">
          {Array.from({ length: 90 }).map((_, index) => (
            <span
              key={index}
              className="flex-1 rounded-sm bg-white/10"
              style={{
                height: `${12 + Math.abs(Math.sin(index * 0.55)) * 54}%`,
              }}
            />
          ))}
        </div>

        {segments.map((segment, index) => (
          <div
            key={`${segment.start_ms}-${index}`}
            className="absolute top-0 h-1 rounded-full bg-flame-500/60"
            style={{
              left: `${(segment.start_ms / duration) * 100}%`,
              width: `${Math.max(0.3, ((segment.end_ms - segment.start_ms) / duration) * 100)}%`,
            }}
            title={segment.text.slice(0, 120)}
          />
        ))}

        <div className="absolute inset-y-0 left-0 bg-black/55" style={{ width: `${startPct}%` }} />
        <div className="absolute inset-y-0 right-0 bg-black/55" style={{ width: `${100 - endPct}%` }} />
        <div
          className="absolute inset-y-0 border-x border-flame-500/70 bg-flame-500/8"
          style={{ left: `${startPct}%`, width: `${Math.max(0, endPct - startPct)}%` }}
        >
          <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-flame-500/25" />
        </div>

        <div
          className="absolute inset-y-0 z-10 w-px bg-paper/90"
          style={{ left: `${playPct}%` }}
        >
          <span className="absolute -top-0.5 left-1/2 h-2 w-2 -translate-x-1/2 rounded-full bg-paper" />
        </div>

        <button
          type="button"
          data-handle="start"
          onPointerDown={startDrag("start")}
          className="absolute inset-y-0 z-20 w-3 -translate-x-1/2 cursor-ew-resize"
          style={{ left: `${startPct}%` }}
          aria-label="Drag clip start"
        >
          <span className="absolute inset-y-2 left-1/2 w-1 -translate-x-1/2 rounded-full bg-flame-500" />
        </button>
        <button
          type="button"
          data-handle="end"
          onPointerDown={startDrag("end")}
          className="absolute inset-y-0 z-20 w-3 -translate-x-1/2 cursor-ew-resize"
          style={{ left: `${endPct}%` }}
          aria-label="Drag clip end"
        >
          <span className="absolute inset-y-2 left-1/2 w-1 -translate-x-1/2 rounded-full bg-flame-500" />
        </button>
      </div>

      <div className="mt-2.5 grid grid-cols-2 gap-3">
        <label className="flex items-center gap-2 text-[10px] text-faint">
          <span className="w-8 shrink-0 font-mono">in</span>
          <input
            type="range"
            min={0}
            max={duration}
            step={100}
            value={startMs}
            onChange={(event) => onChange(Math.min(Number(event.target.value), endMs - 500), endMs)}
            className="w-full"
          />
        </label>
        <label className="flex items-center gap-2 text-[10px] text-faint">
          <span className="w-8 shrink-0 font-mono">out</span>
          <input
            type="range"
            min={0}
            max={duration}
            step={100}
            value={endMs}
            onChange={(event) => onChange(startMs, Math.max(Number(event.target.value), startMs + 500))}
            className="w-full"
          />
        </label>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 font-mono text-[9.5px] text-faint">
        <span>
          selected {(Math.max(0, endMs - startMs) / 1000).toFixed(1)}s
        </span>
        <span>{segments.length} transcript blocks</span>
      </div>
    </div>
  );
}

export function FramingPreview({
  src,
  aspect,
  focusX,
  focusY,
  layout,
  className,
}: {
  src: string;
  aspect: string;
  focusX: number;
  focusY: number;
  layout?: { mode?: string; position?: string; size?: number; x?: number; y?: number };
  className?: string;
}) {
  const mode = layout?.mode || "fill";
  const position = layout?.position || "bottom_right";
  const manual = position === "manual";
  const bottomHalf = position === "bottom_half";
  const pipStyle: React.CSSProperties = bottomHalf
    ? { left: 0, bottom: 0, width: "100%", height: "50%" }
    : {
    width: `${Math.round((layout?.size ?? 0.4) * 100)}%`,
    aspectRatio: "3 / 4",
    ...(manual
      ? { left: `${(layout?.x ?? 0.96) * 100}%`, top: `${(layout?.y ?? 0.96) * 100}%`, transform: "translate(-100%, -100%)" }
      : position.includes("left")
        ? { left: "6%", [position.includes("top") ? "top" : "bottom"]: "6%" }
        : position === "bottom_center"
          ? { left: "50%", bottom: "6%", transform: "translateX(-50%)" }
          : position.includes("top")
            ? { right: "6%", top: "6%" }
            : { right: "6%", bottom: "6%" }),
  };
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg border border-white/10 bg-black",
        aspect === "9:16"
          ? "aspect-[9/16]"
          : aspect === "1:1"
            ? "aspect-square"
            : aspect === "4:5"
              ? "aspect-[4/5]"
              : "aspect-video",
        className,
      )}
    >
      <video
        src={src}
        muted
        playsInline
        preload="metadata"
        className={`h-full w-full ${mode === "fit" ? "object-contain" : "object-cover"}`}
        style={{ objectPosition: `${focusX * 100}% ${focusY * 100}%` }}
      />
      {mode === "facecam" ? (
        <div
          className="pointer-events-none absolute overflow-hidden rounded border-2 border-flame-500/70 bg-ink-950/40 shadow-lg"
          style={pipStyle}
        >
          <video
            src={src}
            muted
            playsInline
            preload="metadata"
            className="h-full w-full object-cover"
            style={{ objectPosition: `${focusX * 100}% ${focusY * 100}%` }}
          />
          <span className="absolute bottom-0.5 left-1 rounded bg-black/70 px-1 py-0.5 font-mono text-[7px] text-white/80">cam</span>
        </div>
      ) : null}
      <div className="pointer-events-none absolute inset-0 border border-flame-500/30" />
      <span className="absolute bottom-1.5 left-2 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[9px] text-white/80">
        {mode === "facecam" ? "face cam" : mode === "fit" ? "fit" : `${aspect} · ${Math.round(focusX * 100)}/${Math.round(focusY * 100)}`}
      </span>
    </div>
  );
}
