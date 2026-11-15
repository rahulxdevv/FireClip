import { cn } from "@/lib/cn";

export function LogoMark({ className, size = 32 }: { className?: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="FireClip"
      className={cn("shrink-0", className)}
    >
      <defs>
        <linearGradient id="fireclip-flame" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#FF8A45" />
          <stop offset="1" stopColor="#E85812" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="#111116" />
      <path
        d="M33 9c2 9-5 12-7 19-1.6 5.6 2 8 5 8 3.4 0 6-2.6 6-6 4 4 7 8 7 13 0 7-6.7 12-12.5 12C23 55 17 48.6 17 40.5 17 27 33 23 33 9Z"
        fill="url(#fireclip-flame)"
      />
      <path d="M29 36.5 42 44l-13 7.5v-15Z" fill="#0b0b0f" />
    </svg>
  );
}

export function Logo({ className, size = 30 }: { className?: string; size?: number }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark size={size} />
      <span className="text-[17px] font-semibold tracking-tight text-paper">
        fireclip<span className="text-flame-500">.</span>
      </span>
    </span>
  );
}
