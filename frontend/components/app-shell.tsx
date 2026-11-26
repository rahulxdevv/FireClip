"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";
import {
  Bell,
  BookOpen,
  CalendarClock,
  Check,
  ChevronDown,
  Clapperboard,
  CreditCard,
  Download,
  Film,
  Flame,
  LayoutDashboard,
  Link2,
  LogOut,
  Megaphone,
  Menu,
  Radio,
  RadioTower,
  Scissors,
  Settings,
  Sparkles,
  Upload,
  Users,
  Wallet,
  Webhook,
  X,
} from "lucide-react";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/cn";
import { api } from "@/lib/api";
import { useSessionStore } from "@/lib/stores";
import { relativeTime } from "@/lib/format";
import type { NotificationItem, Session, SystemStatus } from "@/lib/types";

const NAV = [
  {
    group: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/analytics", label: "Analytics", icon: Scissors },
    ],
  },
  {
    group: "Workspace",
    items: [
      { href: "/videos", label: "Video library", icon: Film },
      { href: "/upload", label: "Upload video", icon: Upload },
      { href: "/import", label: "Import from URL", icon: Link2 },
      { href: "/streamers", label: "Streamers", icon: RadioTower },
      { href: "/live", label: "Live streams", icon: Radio },
    ],
  },
  {
    group: "Create",
    items: [
      { href: "/campaigns", label: "Campaigns", icon: Megaphone },
      { href: "/clips", label: "Clip discovery", icon: Flame },
      { href: "/renders", label: "Render queue", icon: Clapperboard },
      { href: "/exports", label: "Exports", icon: Download },
    ],
  },
  {
    group: "Distribute",
    items: [
      { href: "/publish", label: "Publishing", icon: Sparkles },
      { href: "/schedule", label: "Schedule", icon: CalendarClock },
      { href: "/accounts", label: "Social accounts", icon: Users },
    ],
  },
  {
    group: "Settings",
    items: [
      { href: "/ai-settings", label: "AI settings", icon: Sparkles },
      { href: "/workspace", label: "Workspace", icon: Users },
      { href: "/billing", label: "Plan & usage", icon: CreditCard },
      { href: "/webhooks", label: "Webhooks", icon: Webhook },
      { href: "/settings", label: "My settings", icon: Settings },
    ],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = React.useState(false);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const setSession = useSessionStore((state) => state.setSession);
  const clear = useSessionStore((state) => state.clear);
  const user = useSessionStore((state) => state.user);

  React.useEffect(() => {
    let active = true;
    api
      .get<Session>("/api/auth/me")
      .then((session) => {
        if (!active) return;
        setSession(session);
        setReady(true);
      })
      .catch(() => {
        if (!active) return;
        clear();
        router.replace("/login");
      });
    return () => {
      active = false;
    };
  }, [router, setSession, clear]);

  React.useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-950">
        <div className="flex flex-col items-center gap-5">
          <Logo size={34} />
          <span className="h-[2px] w-24 overflow-hidden rounded-full bg-paper/[0.08]">
            <span className="block h-full w-1/2 animate-pulse rounded-full bg-flame-500" />
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-ink-950">
      <button
        className="fixed left-4 top-3.5 z-50 rounded-[var(--radius-control)] border border-paper/10 bg-ink-900 p-2 text-muted lg:hidden"
        onClick={() => setMobileOpen(true)}
        aria-label="Open navigation"
      >
        <Menu className="h-4.5 w-4.5" />
      </button>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 bg-black/70 lg:hidden" onClick={() => setMobileOpen(false)} />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[268px] flex-col overflow-hidden border-r border-white/[0.06] bg-[#08080e] transition-transform duration-200 lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-64"
          style={{ background: "radial-gradient(70% 60% at 18% 0%, rgba(111,92,252,0.20), transparent 70%)" }}
        />
        <div className="relative flex h-[62px] items-center justify-between px-4">
          <Link href="/dashboard" aria-label="FireClip dashboard">
            <Logo size={26} />
          </Link>
          <button
            className="rounded p-1 text-faint hover:text-paper lg:hidden"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="relative px-3 pb-1 pt-4">
          <WorkspaceSwitcher />
        </div>

        <nav className="relative mt-3 min-h-0 flex-1 overflow-y-auto px-2.5 pb-4">
          {NAV.map((section) => (
            <div key={section.group} className="mb-4 last:mb-0">
              <p className="px-2.5 pb-1.5 text-[10.5px] font-medium text-faint/75">{section.group}</p>
              <div className="space-y-0.5">
                {section.items.map((item) => (
                  <NavLink key={item.href} href={item.href} label={item.label} Icon={item.icon} />
                ))}
              </div>
            </div>
          ))}
        </nav>

        <SystemFooter />
      </aside>

      <div className="lg:pl-[268px]">
        <header className="sticky top-0 z-30 flex h-[62px] items-center gap-3 border-b border-white/[0.06] bg-ink-950/85 px-4 backdrop-blur-xl sm:px-6">
          <div className="mr-auto flex min-w-0 items-center pl-10 lg:pl-0">
            <HeaderBreadcrumb />
          </div>
          <NotificationBell />
          <UserMenu />
        </header>
        <main className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 sm:py-8">{children}</main>
      </div>
    </div>
  );
}

function NavLink({
  href,
  label,
  Icon,
}: {
  href: string;
  label: string;
  Icon: React.ComponentType<{ className?: string }>;
}) {
  const pathname = usePathname();
  const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/"));
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[12.5px] transition-colors duration-150",
        active
          ? "bg-white/[0.07] text-paper shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]"
          : "text-muted hover:bg-white/[0.035] hover:text-paper",
      )}
    >
      <Icon className={cn("h-[15px] w-[15px] shrink-0", active ? "text-flame-400" : "text-faint group-hover:text-muted")} />
      <span className="truncate">{label}</span>
    </Link>
  );
}

function WorkspaceSwitcher() {
  const workspaces = useSessionStore((state) => state.workspaces);
  const activeId = useSessionStore((state) => state.activeWorkspaceId);
  const setActive = useSessionStore((state) => state.setActiveWorkspace);
  const [open, setOpen] = React.useState(false);
  const current = workspaces.find((workspace) => workspace.id === activeId);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2.5 rounded-[var(--radius-control)] border border-paper/[0.07] bg-paper/[0.03] px-2.5 py-2 text-left transition-colors hover:border-paper/[0.14] hover:bg-paper/[0.05]"
      >
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-flame-500/15 font-display text-[11px] font-semibold text-flame-400">
          {(current?.name || "F").slice(0, 2).toUpperCase()}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12.5px] font-semibold text-paper">
            {current?.name || "No workspace"}
          </span>
          <span className="block truncate text-[11px] capitalize text-faint">
            {current ? current.role : "Create one"}
          </span>
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-faint" />
      </button>
      {open ? (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute left-0 right-0 top-full z-20 mt-1.5 overflow-hidden rounded-[var(--radius-card)] border border-paper/10 bg-ink-850 p-1">
            {workspaces.map((workspace) => (
              <button
                key={workspace.id}
                onClick={() => {
                  setActive(workspace.id);
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between gap-2 rounded-[var(--radius-control)] px-2.5 py-2 text-left text-[12.5px] text-muted transition-colors hover:bg-paper/[0.06] hover:text-paper"
              >
                <span className="truncate">{workspace.name}</span>
                {workspace.id === activeId ? <Check className="h-3.5 w-3.5 text-flame-500" /> : null}
              </button>
            ))}
            <Link
              href="/workspace"
              className="mt-1 block border-t border-paper/[0.07] px-2.5 py-2 text-[11.5px] text-faint hover:text-paper"
              onClick={() => setOpen(false)}
            >
              Manage workspaces
            </Link>
          </div>
        </>
      ) : null}
    </div>
  );
}

function NotificationBell() {
  const [open, setOpen] = React.useState(false);
  const [items, setItems] = React.useState<NotificationItem[]>([]);

  const load = React.useCallback(async () => {
    try {
      const data = await api.get<NotificationItem[]>("/api/notifications?limit=12");
      setItems(data);
    } catch {
      /* notification errors should not break the shell */
    }
  }, []);

  React.useEffect(() => {
    void load();
    const timer = window.setInterval(load, 20000);
    return () => window.clearInterval(timer);
  }, [load]);

  const unread = items.filter((item) => !item.read_at).length;

  async function markAll() {
    try {
      await api.post("/api/notifications/read-all");
      setItems((current) => current.map((item) => ({ ...item, read_at: item.read_at || new Date().toISOString() })));
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        className="relative rounded-[var(--radius-control)] border border-paper/[0.07] bg-paper/[0.02] p-2 text-muted transition-colors hover:border-paper/[0.14] hover:text-paper"
        aria-label="Notifications"
      >
        <Bell className="h-4 w-4" />
        {unread > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-flame-500 px-1 text-[9px] font-bold text-white">
            {unread}
          </span>
        ) : null}
      </button>
      {open ? (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 top-full z-20 mt-2 w-[340px] overflow-hidden rounded-[var(--radius-card)] border border-paper/10 bg-ink-850">
            <div className="flex items-center justify-between border-b border-paper/[0.07] px-4 py-3">
              <p className="text-[13px] font-semibold">Notifications</p>
              {unread > 0 ? (
                <button onClick={markAll} className="text-[11px] text-flame-400 hover:text-flame-500">
                  Mark all read
                </button>
              ) : null}
            </div>
            <div className="max-h-[360px] overflow-y-auto">
              {items.length === 0 ? (
                <p className="px-4 py-8 text-center text-[13px] text-faint">Nothing yet.</p>
              ) : (
                items.map((item) => (
                  <div key={item.id} className="border-b border-paper/[0.05] px-4 py-3 last:border-0">
                    <div className="flex items-start gap-2">
                      <span
                        className={cn(
                          "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                          item.type === "error" ? "bg-rose" : item.type === "success" ? "bg-mint" : "bg-ember",
                        )}
                      />
                      <div className="min-w-0">
                        <p className={cn("text-[12.5px] leading-snug", item.read_at ? "text-muted" : "text-paper")}>
                          {item.title}
                        </p>
                        {item.body ? <p className="mt-0.5 line-clamp-2 text-[11.5px] text-faint">{item.body}</p> : null}
                        <p className="mt-1 text-[10.5px] text-faint">{relativeTime(item.created_at)}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function UserMenu() {
  const user = useSessionStore((state) => state.user);
  const clear = useSessionStore((state) => state.clear);
  const router = useRouter();
  const [open, setOpen] = React.useState(false);

  async function logout() {
    try {
      await api.post("/api/auth/logout");
    } catch {
      /* continue regardless */
    }
    clear();
    router.replace("/login");
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded-[var(--radius-control)] border border-paper/[0.07] bg-paper/[0.02] py-1 pl-1 pr-2.5 transition-colors hover:border-paper/[0.14]"
      >
        <span
          className="flex h-6 w-6 items-center justify-center rounded-[var(--radius-control)] text-[11px] font-semibold text-seed"
          style={{ backgroundColor: user?.avatar_color || "var(--color-flame-500)" }}
        >
          {(user?.name || user?.email || "?").slice(0, 1).toUpperCase()}
        </span>
        <span className="hidden max-w-[120px] truncate text-[12.5px] text-muted sm:block">{user?.name}</span>
        <ChevronDown className="h-3 w-3 text-faint" />
      </button>
      {open ? (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 top-full z-20 mt-2 w-56 overflow-hidden rounded-[var(--radius-card)] border border-paper/10 bg-ink-850">
            <div className="border-b border-paper/[0.07] px-4 py-3">
              <p className="truncate text-[13px] font-semibold">{user?.name}</p>
              <p className="truncate text-[11px] text-faint">{user?.email}</p>
            </div>
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2.5 text-[13px] text-muted hover:bg-paper/[0.05] hover:text-paper"
            >
              <Settings className="h-3.5 w-3.5" /> Account settings
            </Link>
            <Link
              href="/billing"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2.5 text-[13px] text-muted hover:bg-paper/[0.05] hover:text-paper"
            >
              <Wallet className="h-3.5 w-3.5" /> Plan & usage
            </Link>
            <button
              onClick={logout}
              className="flex w-full items-center gap-2 border-t border-paper/[0.07] px-4 py-2.5 text-left text-[13px] text-muted hover:bg-paper/[0.05] hover:text-rose"
            >
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

function SystemFooter() {
  const [status, setStatus] = React.useState<SystemStatus | null>(null);
  React.useEffect(() => {
    api
      .get<SystemStatus>("/api/system/status")
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);
  return (
    <div className="relative z-10 border-t border-paper/[0.06] bg-[#08080e] px-3.5 py-3">
      <div className="flex items-center justify-between gap-2 text-[11px]">
        <Link
          href="/docs"
          className="flex items-center gap-1.5 text-faint transition-colors hover:text-paper"
        >
          <BookOpen className="h-3 w-3" />
          Docs
        </Link>
        <span className="flex items-center gap-1.5 text-faint">
          <span className={cn("h-1.5 w-1.5 rounded-full", status ? "bg-mint" : "bg-rose")} />
          {status ? (status.ffmpeg ? "Engine ready" : "FFmpeg off") : "Checking"}
        </span>
      </div>
    </div>
  );
}

function HeaderBreadcrumb() {
  const pathname = usePathname();
  const section = NAV.find((entry) =>
    entry.items.some((item) => pathname === item.href || pathname.startsWith(item.href + "/")),
  );
  const item = section?.items.find(
    (entry) => pathname === entry.href || pathname.startsWith(entry.href + "/"),
  );
  return (
    <div className="flex min-w-0 items-center gap-2 text-[12.5px]">
      <span className="hidden text-faint sm:inline">{section?.group || "Workspace"}</span>
      <span className="hidden text-white/15 sm:inline">/</span>
      <span className="truncate font-medium text-paper">{item?.label || "FireClip"}</span>
    </div>
  );
}
