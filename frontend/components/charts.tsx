"use client";

import { cn } from "@/lib/cn";

export function SignalBars({ signals }: { signals: Record<string, number> }) {
  const entries = Object.entries(signals).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return <p className="text-xs text-faint">No signal breakdown available.</p>;
  return (
    <div className="space-y-2">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-center gap-2.5">
          <span className="w-[104px] shrink-0 text-[11px] capitalize text-muted">{key.replace(/_/g, " ")}</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/6">
            <div
              className={cn(
                "h-full rounded-full",
                value >= 70 ? "bg-flame-500" : value >= 45 ? "bg-ember/80" : "bg-ink-500",
              )}
              style={{ width: `${Math.max(2, Math.min(100, value))}%` }}
            />
          </div>
          <span className="w-7 text-right font-mono text-[10.5px] text-faint">{Math.round(value)}</span>
        </div>
      ))}
    </div>
  );
}

export function ViewsChart({ data }: { data: Array<{ date: string; views: number }> }) {
  if (data.length === 0) {
    return (
      <div className="flex h-44 items-center justify-center rounded-lg border border-dashed border-white/10">
        <p className="text-[12px] text-faint">No measured performance data yet</p>
      </div>
    );
  }
  const max = Math.max(1, ...data.map((item) => item.views));
  return (
    <div className="flex h-44 items-end gap-1.5">
      {data.map((item) => (
        <div key={item.date} className="group flex h-full flex-1 flex-col justify-end gap-1">
          <div className="relative flex-1">
            <div
              className="absolute bottom-0 w-full rounded-t bg-flame-500/60 transition-colors group-hover:bg-flame-500"
              style={{ height: `${Math.max(2, (item.views / max) * 100)}%` }}
              title={`${item.date}: ${item.views} views`}
            />
          </div>
          <span className="truncate text-center font-mono text-[8.5px] text-faint">
            {item.date.slice(5)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function PlatformBars({
  data,
}: {
  data: Array<Record<string, number | string>>;
}) {
  if (data.length === 0) return <p className="text-[12px] text-faint">No platform data measured.</p>;
  const max = Math.max(1, ...data.map((row) => Number(row.views) || 0));
  return (
    <div className="space-y-3">
      {data.map((row) => (
        <div key={String(row.platform)}>
          <div className="mb-1 flex items-center justify-between text-[11.5px]">
            <span className="capitalize text-muted">{String(row.platform)}</span>
            <span className="font-mono text-faint">{Number(row.views || 0).toLocaleString()} views</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/6">
            <div
              className="h-full rounded-full bg-ember/80"
              style={{ width: `${Math.max(2, (Number(row.views || 0) / max) * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
