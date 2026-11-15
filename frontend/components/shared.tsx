"use client";

import Link from "next/link";
import { ChevronRight, Plus } from "lucide-react";
import { Button, Panel, Progress } from "@/components/ui";
import { cn } from "@/lib/cn";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-7">
      {eyebrow ? <p className="mb-1.5 font-mono text-[10.5px] uppercase tracking-[0.18em] text-flame-500">{eyebrow}</p> : null}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-paper sm:text-[28px]">{title}</h1>
          {description ? <p className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-muted">{description}</p> : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
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
    <Panel className={cn("h-full p-4", href && "panel-hover")}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[12px] text-muted">{label}</p>
        {icon ? <span className="text-faint">{icon}</span> : null}
      </div>
      <p className="mt-3 text-[26px] font-semibold leading-none tracking-tight text-paper">{value}</p>
      <div className="mt-2 flex items-center gap-2">
        {hint ? <p className="text-[11.5px] text-faint">{hint}</p> : null}
        {trend ? (
          <span className={cn("font-mono text-[10.5px]", trend.value >= 0 ? "text-mint" : "text-rose")}>
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
        <h2 className="text-[14px] font-semibold text-paper">{title}</h2>
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
        <span key={`${item.label}-${index}`} className="flex items-center gap-1">
          {item.href ? (
            <Link href={item.href} className="hover:text-paper">
              {item.label}
            </Link>
          ) : (
            <span className="text-muted">{item.label}</span>
          )}
          {index < items.length - 1 ? <ChevronRight className="h-3 w-3" /> : null}
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
        <span className="font-mono text-faint">{status || `${Math.round(value)}%`}</span>
      </div>
      <Progress value={value} />
    </div>
  );
}
