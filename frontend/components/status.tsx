import { Badge, StatusDot } from "@/components/ui";

const VIDEO_STATUS: Record<string, { label: string; tone: "neutral" | "flame" | "mint" | "rose" | "ember" }> = {
  uploaded: { label: "Queued", tone: "neutral" },
  downloading: { label: "Downloading", tone: "flame" },
  probing: { label: "Processing", tone: "flame" },
  ready: { label: "Ready", tone: "mint" },
  transcribing: { label: "Transcribing", tone: "flame" },
  analyzing: { label: "Analyzing", tone: "flame" },
  rendering: { label: "Rendering", tone: "flame" },
  error: { label: "Needs attention", tone: "rose" },
};

const JOB_STATUS: Record<string, { label: string; tone: "neutral" | "flame" | "mint" | "rose" | "ember" }> = {
  queued: { label: "Queued", tone: "neutral" },
  running: { label: "Running", tone: "flame" },
  completed: { label: "Completed", tone: "mint" },
  failed: { label: "Failed", tone: "rose" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

const PUBLISH_STATUS: Record<string, { label: string; tone: "neutral" | "flame" | "mint" | "rose" | "ember" }> = {
  published: { label: "Published", tone: "mint" },
  publishing: { label: "Publishing", tone: "flame" },
  queued: { label: "Queued", tone: "flame" },
  scheduled: { label: "Scheduled", tone: "ember" },
  failed: { label: "Failed", tone: "rose" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

export function VideoStatusBadge({ status }: { status: string }) {
  const item = VIDEO_STATUS[status] || { label: status, tone: "neutral" as const };
  return <Badge tone={item.tone}>{item.label}</Badge>;
}

export function JobStatusBadge({ status }: { status: string }) {
  const item = JOB_STATUS[status] || { label: status, tone: "neutral" as const };
  return <Badge tone={item.tone}>{item.label}</Badge>;
}

export function PublishStatusBadge({ status }: { status: string }) {
  const item = PUBLISH_STATUS[status] || { label: status, tone: "neutral" as const };
  return <Badge tone={item.tone}>{item.label}</Badge>;
}

export function PlatformLabel({ platform }: { platform: string }) {
  const labels: Record<string, string> = {
    youtube: "YouTube",
    tiktok: "TikTok",
    instagram: "Instagram",
    facebook: "Facebook",
  };
  return <span className="text-[13px] font-medium">{labels[platform] || platform}</span>;
}

export function LiveIndicator({ healthy, label }: { healthy: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <StatusDot tone={healthy ? "ok" : "danger"} />
      {label}
    </span>
  );
}
