"use client";

import * as React from "react";
import { cn } from "@/lib/cn";
import { AlertCircle, Check, ChevronDown, Loader2, X } from "lucide-react";

/* Button ------------------------------------------------------------------ */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type ButtonSize = "sm" | "md" | "lg" | "icon";

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "bg-flame-500 text-white shadow-primary hover:bg-flame-600 active:bg-[#4a37e0]",
  secondary:
    "border border-paper/12 bg-paper/[0.05] text-paper hover:border-paper/20 hover:bg-paper/[0.08]",
  ghost: "bg-transparent text-muted hover:bg-paper/[0.05] hover:text-paper",
  danger: "border border-rose/25 bg-rose/10 text-rose hover:bg-rose/15",
  outline: "border border-paper/16 bg-transparent text-paper hover:border-paper/28 hover:bg-paper/[0.035]",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-10 px-4 text-[13.5px] gap-2",
  lg: "h-12 px-6 text-[15px] gap-2.5",
  icon: "h-9 w-9 rounded-[var(--radius-control)]",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", size = "md", loading, disabled, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex select-none items-center justify-center rounded-[var(--radius-control)] font-semibold transition-colors duration-150 disabled:cursor-not-allowed disabled:border-paper/[0.06] disabled:bg-paper/[0.04] disabled:text-faint disabled:shadow-none",
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
      {children}
    </button>
  );
});

/* Inputs ------------------------------------------------------------------ */

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn("input-base h-10", className)} {...props} />;
  },
);

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cn("input-base min-h-24 resize-y leading-relaxed", className)} {...props} />;
});

export function Select({
  className,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select className={cn("input-base h-10 appearance-none pr-9", className)} {...props}>
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
    </div>
  );
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("mb-1.5 block text-[12.5px] font-medium text-muted", className)} {...props} />;
}

export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label?: string;
  hint?: string;
  error?: string | null;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      {label ? <Label>{label}</Label> : null}
      {children}
      {error ? <p className="text-xs text-rose">{error}</p> : hint ? <p className="text-xs text-faint">{hint}</p> : null}
    </div>
  );
}

/* Surfaces ---------------------------------------------------------------- */

export function Panel({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("panel", className)} {...props}>
      {children}
    </div>
  );
}

export function PanelHeader({
  title,
  description,
  action,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4 border-b border-paper/[0.07] px-5 py-4", className)}>
      <div className="min-w-0">
        <h2 className="font-display text-[15px] font-semibold tracking-[-0.02em] text-paper">{title}</h2>
        {description ? <p className="mt-1 text-[13px] leading-relaxed text-muted">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

/* Badge ------------------------------------------------------------------- */

type BadgeTone = "neutral" | "flame" | "mint" | "rose" | "ember" | "outline";

const badgeTones: Record<BadgeTone, string> = {
  neutral: "bg-paper/[0.07] text-muted",
  flame: "bg-flame-500/14 text-flame-400",
  mint: "bg-mint/12 text-mint",
  rose: "bg-rose/12 text-rose",
  ember: "bg-ember/12 text-ember",
  outline: "border border-paper/14 text-muted",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: BadgeTone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
        badgeTones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* Progress ---------------------------------------------------------------- */

export function Progress({ value, className }: { value: number; className?: string }) {
  const scale = Math.max(0, Math.min(100, value)) / 100;
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-paper/[0.08]", className)}>
      {scale > 0 ? (
        <div
          className="h-full w-full origin-left rounded-full bg-flame-500 transition-transform duration-500"
          style={{ transform: "scaleX(" + scale + ")" }}
        />
      ) : null}
    </div>
  );
}

/* Skeleton ---------------------------------------------------------------- */

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-[var(--radius-card)] bg-paper/[0.05]", className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2.5">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-80" />
    </div>
  );
}

/* Empty state ------------------------------------------------------------- */

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-16 text-center", className)}>
      {icon ? (
        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-[var(--radius-card)] border border-paper/[0.08] bg-ink-850 text-flame-500">
          {icon}
        </div>
      ) : null}
      <h3 className="font-display text-[15px] font-semibold tracking-[-0.02em] text-paper">{title}</h3>
      {description ? <p className="mt-1.5 max-w-md text-[13px] leading-relaxed text-muted">{description}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

/* Tabs -------------------------------------------------------------------- */

export function Tabs({
  tabs,
  value,
  onValueChange,
  className,
}: {
  tabs: { value: string; label: string; count?: number }[];
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1 border-b border-paper/[0.07]", className)} role="tablist">
      {tabs.map((tab) => {
        const active = tab.value === value;
        return (
          <button
            key={tab.value}
            role="tab"
            aria-selected={active}
            onClick={() => onValueChange(tab.value)}
            className={cn(
              "relative -mb-px px-3 py-2.5 text-[13px] font-medium transition-colors",
              active ? "text-paper" : "text-faint hover:text-muted",
            )}
          >
            {tab.label}
            {typeof tab.count === "number" ? (
              <span className="ml-1.5 rounded-full bg-paper/[0.07] px-1.5 py-0.5 text-[10.5px] text-muted">
                {tab.count}
              </span>
            ) : null}
            {active ? <span className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-flame-500" /> : null}
          </button>
        );
      })}
    </div>
  );
}

/* Dialog ------------------------------------------------------------------ */

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  wide?: boolean;
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onOpenChange(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onOpenChange]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:items-center">
      <div className="fixed inset-0 bg-black/75" onClick={() => onOpenChange(false)} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative z-10 w-full overflow-hidden rounded-[var(--radius-card)] border border-paper/[0.09] bg-ink-900 shadow-dialog animate-rise",
          wide ? "max-w-2xl" : "max-w-md",
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-paper/[0.07] px-5 py-4">
          <div>
            <h2 className="font-display text-[16px] font-semibold tracking-[-0.02em]">{title}</h2>
            {description ? <p className="mt-1 text-[13px] text-muted">{description}</p> : null}
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="rounded-[var(--radius-control)] p-1 text-faint transition-colors hover:bg-paper/[0.06] hover:text-paper"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer ? (
          <div className="flex justify-end gap-2 border-t border-paper/[0.07] px-5 py-4">{footer}</div>
        ) : null}
      </div>
    </div>
  );
}

/* Switch ------------------------------------------------------------------ */

export function Switch({
  checked,
  onCheckedChange,
  label,
  disabled,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <label
      className={cn(
        "inline-flex items-center gap-2.5",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
      )}
    >
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onCheckedChange(event.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden
        className={cn(
          "relative h-5 w-9 shrink-0 rounded-full border transition-colors duration-150 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-flame-500",
          checked ? "border-flame-500 bg-flame-500" : "border-paper/15 bg-ink-700",
        )}
      >
        <span
          className={cn(
            "absolute left-[2px] top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full transition-transform duration-150",
            checked ? "translate-x-[18px] bg-white" : "translate-x-0 bg-[#9b9bb2]",
          )}
        />
      </span>
      {label ? <span className="text-[13px] text-muted">{label}</span> : null}
    </label>
  );
}

/* Status bits ------------------------------------------------------------- */

export function StatusDot({ tone = "neutral" }: { tone?: "neutral" | "ok" | "warn" | "danger" }) {
  const colors = {
    neutral: "bg-ink-500",
    ok: "bg-mint",
    warn: "bg-ember",
    danger: "bg-rose",
  };
  return <span className={cn("inline-block h-1.5 w-1.5 rounded-full", colors[tone])} />;
}

export function Alert({
  tone = "error",
  title,
  children,
  className,
}: {
  tone?: "error" | "success" | "info";
  title?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const icon = tone === "success" ? <Check className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />;
  const styles =
    tone === "success"
      ? "border-mint/25 bg-mint/[0.08] text-mint"
      : tone === "info"
        ? "border-paper/10 bg-paper/[0.04] text-muted"
        : "border-rose/25 bg-rose/[0.08] text-rose";
  return (
    <div className={cn("flex gap-2.5 rounded-[var(--radius-card)] border px-3.5 py-3 text-[13px]", styles, className)}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0 leading-relaxed">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className={cn(title && "mt-0.5 opacity-90")}>{children}</div> : null}
      </div>
    </div>
  );
}

export function ScoreRing({ score, size = 44 }: { score: number; size?: number }) {
  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.max(0, Math.min(100, score)) / 100) * circumference;
  const color = score >= 75 ? "var(--color-mint)" : score >= 55 ? "var(--color-ember)" : "var(--color-flame-500)";
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--hairline)" strokeWidth="3" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="absolute font-display text-[12px] font-semibold text-paper">{Math.round(score)}</span>
    </div>
  );
}
