"use client";

import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { useToastStore } from "@/lib/stores";
import { cn } from "@/lib/cn";

export function ToastViewport() {
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[80] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((item) => {
        const Icon = item.variant === "success" ? CheckCircle2 : item.variant === "error" ? XCircle : Info;
        return (
          <div
            key={item.id}
            className={cn(
              "pointer-events-auto flex items-start gap-3 rounded-[var(--radius-card)] border bg-ink-850 px-4 py-3 shadow-dialog animate-rise",
              item.variant === "success"
                ? "border-mint/25"
                : item.variant === "error"
                  ? "border-rose/30"
                  : "border-paper/12",
            )}
          >
            <Icon
              className={cn(
                "mt-0.5 h-4 w-4 shrink-0",
                item.variant === "success" ? "text-mint" : item.variant === "error" ? "text-rose" : "text-ember",
              )}
            />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium leading-snug text-paper">{item.title}</p>
              {item.description ? (
                <p className="mt-0.5 text-xs leading-relaxed text-muted">{item.description}</p>
              ) : null}
            </div>
            <button
              onClick={() => dismiss(item.id)}
              className="rounded p-0.5 text-faint transition-colors hover:text-paper"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
