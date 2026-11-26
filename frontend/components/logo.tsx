import { cn } from "@/lib/cn";

/**
 * The mark: one flame with a flame-shaped counter cut out of it, drawn on a 64
 * unit grid. The tip leans right and the counter sits low left, so the outline
 * still reads as fire at 16px where a thinner silhouette collapses into a comma.
 */
export function LogoMark({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="FireClip"
      className={cn("shrink-0", className)}
    >
      <path
        d="M39 4.5C41 13.5 46 21 46 31.5C46 43.4 39.2 52.5 30.4 52.5C21.6 52.5 15 44.4 15 34.6C15 26 22 20.6 27 14.6C30.4 10.4 33.4 7.6 39 4.5ZM29.5 29C33 34 34.8 37.6 34.8 41.4C34.8 45 32.4 47.6 29.2 47.6C26 47.6 23.8 45 23.8 41.4C23.8 37.4 26.4 33.6 29.5 29Z"
        fill="currentColor"
        fillRule="evenodd"
      />
    </svg>
  );
}

export function Logo({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark size={size} className="text-flame-500" />
      <span className="font-display text-[19px] font-semibold tracking-[-0.035em] text-paper">
        fireclip<span className="text-flame-500">.</span>
      </span>
    </span>
  );
}
