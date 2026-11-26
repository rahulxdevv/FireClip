"use client";

import Link from "next/link";
import { ChevronRight, Plus } from "lucide-react";
import { Button, Panel, Progress } from "@/components/ui";
import { cn } from "@/lib/cn";

export function PageHeader({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-7">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <h1 className="page-title text-paper">{title}</h1>
          {description ? (
            <p className="mt-2 max-w-[56ch] text-[13.5px] leading-relaxed text-muted">{description}</p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">{actions}</div>
        ) : null}
      </div>
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  href,
  trend,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: React.ReactNode;
  href?: string;
  trend?: { value: number; label: string };
}) {
  const content = (
    <Panel className={cn("group h-full p-4", href && "panel-hover")}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[12px] font-medium text-muted">{label}</p>
        {icon ? (
          <span className="shrink-0 text-ink-500 transition-colors group-hover:text-flame-500">
            {icon}
          </span>
        ) : null}
      </div>
      <p className="mt-4 font-display text-[30px] font-semibold leading-none tracking-[-0.03em] text-paper">
        {value}
      </p>
      <div className="mt-2.5 flex items-center gap-2">
        {hint ? <p className="truncate text-[11.5px] text-faint">{hint}</p> : null}
        {trend ? (
          <span className={cn("text-[11px] font-medium", trend.value >= 0 ? "text-mint" : "text-rose")}>
            {trend.value >= 0 ? "+" : ""}
            {trend.value}% {trend.label}
          </span>
        ) : null}
      </div>
    </Panel>
  );
  if (href) return <Link href={href}>{content}</Link>;
  return content;
}

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3">
      <div>
        <h2 className="font-display text-[15px] font-semibold tracking-[-0.02em] text-paper">{title}</h2>
        {description ? <p className="mt-0.5 text-[12px] text-faint">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function NewButton({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href}>
      <Button size="sm">
        <Plus className="h-3.5 w-3.5" /> {label}
      </Button>
    </Link>
  );
}

export function Breadcrumb({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-1 text-[12px] text-faint">
      {items.map((item, index) => (
        <span key={item.label + "-" + index} className="flex items-center gap-1">
          {item.href ? (
            <Link href={item.href} className="transition-colors hover:text-paper">
              {item.label}
            </Link>
          ) : (
            <span className="text-muted">{item.label}</span>
          )}
          {index < items.length - 1 ? <ChevronRight className="h-3 w-3 text-ink-500" /> : null}
        </span>
      ))}
    </div>
  );
}

export function InlineProgress({
  value,
  label,
  status,
}: {
  value: number;
  label: string;
  status?: string;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3 text-[11.5px]">
        <span className="text-muted">{label}</span>
        <span className="text-faint">{status || String(Math.round(value)) + "%"}</span>
      </div>
      <Progress value={value} />
    </div>
  );
}
