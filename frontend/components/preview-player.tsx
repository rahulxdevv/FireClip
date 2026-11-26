"use client";

import * as React from "react";
import { cn } from "@/lib/cn";
import { formatMs } from "@/lib/format";
import type { Segment } from "@/lib/types";

function hexToRgba(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const full = value.length === 3 ? value.split("").map((char) => char + char).join("") : value;
  const number = Number.parseInt(full, 16);
  if (!Number.isFinite(number) || full.length !== 6) return "rgba(11, 11, 15, " + alpha + ")";
  const red = (number >> 16) & 255;
  const green = (number >> 8) & 255;
  const blue = number & 255;
  return "rgba(" + red + ", " + green + ", " + blue + ", " + alpha + ")";
}

export function PreviewPlayer({
  src,
  trimStartMs,
  trimEndMs,
  aspect,
  captions,
  captionStyle,
  className,
  autoPlay = false,
  onTimeUpdate,
}: {
  src: string;
  trimStartMs: number;
  trimEndMs: number;
  aspect: string;
  onTimeUpdate?: (ms: number) => void;
  captions?: Segment[];
  captionStyle?: {
    textColor?: string;
    highlightColor?: string;
    uppercase?: boolean;
    position?: string;
    box?: boolean;
    font?: string;
    fontSize?: number;
    boxColor?: string;
    boxOpacity?: number;
    italic?: boolean;
    letterSpacing?: number;
    heading?: string;
    headingEnabled?: boolean;
    headingColor?: string;
    headingSize?: number;
    headingUppercase?: boolean;
  };
  className?: string;
  autoPlay?: boolean;
}) {
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const [timeMs, setTimeMs] = React.useState(trimStartMs);
  const [playing, setPlaying] = React.useState(false);

  React.useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (trimStartMs > 0 || video.currentTime * 1000 > trimEndMs) {
      video.currentTime = trimStartMs / 1000;
    }
  }, [trimStartMs, trimEndMs]);

  const activeSegment = React.useMemo(() => {
    if (!captions) return null;
    return (
      captions.find((segment) => timeMs >= segment.start_ms && timeMs <= segment.end_ms) || null
    );
  }, [captions, timeMs]);

  const captionPosition =
    captionStyle?.position === "top"
      ? "items-start pt-[12%]"
      : captionStyle?.position === "middle"
        ? "items-center"
        : "items-end pb-[10%]";

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-[var(--radius-card)] border border-white/10 bg-black",
        aspect === "9:16" ? "aspect-[9/16]" : aspect === "1:1" ? "aspect-square" : aspect === "4:5" ? "aspect-[4/5]" : "aspect-video",
        className,
      )}
    >
      <video
        ref={videoRef}
        src={src}
        playsInline
        controls
        autoPlay={autoPlay}
        muted={autoPlay}
        preload="metadata"
        className="h-full w-full object-contain"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onTimeUpdate={(event) => {
          const video = event.currentTarget;
          const ms = video.currentTime * 1000;
          setTimeMs(ms);
          onTimeUpdate?.(ms);
          if (ms >= trimEndMs) {
            video.pause();
            video.currentTime = trimStartMs / 1000;
          }
        }}
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 flex justify-center bg-gradient-to-b from-black/70 to-transparent px-3 py-2">
        <span className="text-[10px] text-white/70">
          {formatMs(Math.max(0, trimEndMs - trimStartMs))} clip, {playing ? "preview" : "paused"}
        </span>
      </div>
      {captionStyle?.heading && captionStyle.headingEnabled !== false ? (
        <div className="pointer-events-none absolute inset-x-0 top-[6%] flex justify-center px-4">
          <span
            className="max-w-[92%] text-center font-bold leading-tight"
            style={{
              color: captionStyle.headingColor || "#ffffff",
              fontSize: `clamp(11px, ${Math.max(1, (captionStyle.headingSize || 54) / 32)}vw, ${Math.max(16, Math.round((captionStyle.headingSize || 54) * 0.34))}px)`,
              textShadow: "0 1px 4px rgba(0,0,0,0.9)",
              textTransform: captionStyle.headingUppercase ? "uppercase" : "none",
            }}
          >
            {captionStyle.heading}
          </span>
        </div>
      ) : null}
      {activeSegment ? (
        <div className={cn("pointer-events-none absolute inset-0 flex justify-center px-4", captionPosition)}>
          <span
            className="max-w-[92%] rounded px-2 py-1 text-center font-bold leading-tight"
            style={{
              color: captionStyle?.textColor || "#ffffff",
              backgroundColor:
                captionStyle?.box && captionStyle.boxColor
                  ? hexToRgba(captionStyle.boxColor, captionStyle.boxOpacity ?? 0.55)
                  : "transparent",
              textShadow: "0 1px 4px rgba(0,0,0,0.9)",
              fontSize: `clamp(13px, ${Math.max(1.2, (captionStyle?.fontSize || 64) / 26)}vw, ${Math.max(18, Math.round((captionStyle?.fontSize || 64) * 0.36))}px)`,
              fontFamily: captionStyle?.font || "inherit",
              fontStyle: captionStyle?.italic ? "italic" : "normal",
              letterSpacing: `${captionStyle?.letterSpacing ?? 0}px`,
              textTransform: captionStyle?.uppercase ? "uppercase" : "none",
            }}
          >
            {activeSegment.text}
          </span>
        </div>
      ) : null}
    </div>
  );
}
