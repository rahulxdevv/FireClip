"use client";

import { Moon, Sun } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/cn";

type Theme = "light" | "dark";

const STORAGE_KEY = "fireclip-theme";
const EVENT = "fireclip-theme";

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function subscribe(onChange: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY) return;
    document.documentElement.dataset.theme = event.newValue === "light" ? "light" : "dark";
    onChange();
  };
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onStorage);
  };
}

export function ThemeToggle({
  tone = "app",
  className,
}: {
  tone?: "app" | "marketing";
  className?: string;
}) {
  const theme = React.useSyncExternalStore(subscribe, currentTheme, () => "dark" as Theme);

  function toggle() {
    const next: Theme = theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* storage can be blocked; the theme still changes for this page */
    }
    window.dispatchEvent(new Event(EVENT));
  }

  const label = theme === "light" ? "Switch to dark theme" : "Switch to light theme";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-colors duration-150",
        tone === "marketing"
          ? "border-hair bg-[var(--mk-card)] text-ash hover:border-[var(--mk-line-strong)] hover:text-night"
          : "border-paper/10 bg-paper/[0.02] text-muted hover:border-paper/20 hover:text-paper",
        className,
      )}
    >
      {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
    </button>
  );
}
