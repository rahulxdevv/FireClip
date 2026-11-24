"use client";

import Link from "next/link";
import * as React from "react";
import { ArrowRight, Clock, Film, Megaphone, Plus, Sparkles, Wand2 } from "lucide-react";
import { PageHeader } from "@/components/shared";
import {
  Alert,
  Badge,
  Button,
  Dialog,
  EmptyState,
  Field,
  Input,
  PageSkeleton,
  Panel,
  PanelHeader,
  Select,
  Switch,
  Textarea,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatDuration } from "@/lib/format";
import type { Campaign, CaptionStyle } from "@/lib/types";

const emptyForm = {
  name: "",
  description: "",
  brief: "",
  aspect_ratio: "9:16",
  target_seconds: "45",
  clip_count: "6",
  min_score: "0",
  caption_style_id: "",
  auto_approve: false,
  auto_render: false,
  accent_color: "#ff6a1f",
  logo_text: "",
};

export default function CampaignsPage() {
  const { data, error, loading, refresh } = useApi<Campaign[]>("/api/campaigns");
  const styles = useApi<CaptionStyle[]>("/api/caption-styles");
  const [open, setOpen] = React.useState(false);
  const [form, setForm] = React.useState(emptyForm);
  const [submitting, setSubmitting] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);

  function change<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await api.post<Campaign>("/api/campaigns", {
        name: form.name.trim(),
        description: form.description.trim(),
        brief: form.brief.trim(),
        aspect_ratio: form.aspect_ratio,
        target_duration_ms: Number(form.target_seconds) * 1000,
        clip_count: Number(form.clip_count),
        min_score: Number(form.min_score),
        caption_style_id: form.caption_style_id || null,
        caption_overrides: form.accent_color ? { highlight_color: form.accent_color } : {},
        auto_approve: form.auto_approve,
        auto_render: form.auto_render,
        brand: {
          accent_color: form.accent_color,
          logo_text: form.logo_text.trim(),
        },
      });
      setOpen(false);
      setForm(emptyForm);
      refresh();
      toast("Campaign created", "success");
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        eyebrow="Create"
        title="Campaigns"
        description="One brief, one target format, one automation policy for every video in a batch."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> New campaign
          </Button>
        }
      />

      {error ? <Alert className="mb-4">{error}</Alert> : null}
      {loading && !data ? (
        <PageSkeleton />
      ) : (data || []).length === 0 ? (
        <Panel>
          <EmptyState
            icon={<Megaphone className="h-5 w-5" />}
            title="No campaigns yet"
            description="Group videos under a brief, choose the clip length and style once, then let analysis and rendering run automatically."
            action={<Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> Create the first campaign</Button>}
          />
        </Panel>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {(data || []).map((campaign) => {
            const progress = campaign.clip_count_actual
              ? Math.round((campaign.approved_count / campaign.clip_count_actual) * 100)
              : 0;
            return (
              <Panel key={campaign.id} className="flex flex-col p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={campaign.status === "active" ? "mint" : campaign.status === "paused" ? "ember" : "neutral"}>
                        {campaign.status}
                      </Badge>
                      <Badge tone="outline">{campaign.aspect_ratio}</Badge>
                      {campaign.auto_render ? <Badge tone="flame">automated</Badge> : null}
                    </div>
                    <h2 className="mt-2.5 truncate text-[15px] font-semibold text-paper">{campaign.name}</h2>
                    <p className="mt-1 line-clamp-2 text-[12.5px] leading-relaxed text-muted">
                      {campaign.description || campaign.brief || "No brief yet."}
                    </p>
                  </div>
                  <Link
                    href={`/campaigns/${campaign.id}`}
                    className="shrink-0 rounded-lg border border-white/10 p-2 text-muted transition-colors hover:border-flame-500/40 hover:text-flame-400"
                    aria-label={`Open ${campaign.name}`}
                  >
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl border border-white/7 bg-ink-850/60 p-3">
                  <div>
                    <p className="font-mono text-[17px] text-paper">{campaign.video_count}</p>
                    <p className="text-[10px] uppercase tracking-wide text-faint">videos</p>
                  </div>
                  <div>
                    <p className="font-mono text-[17px] text-paper">{campaign.clip_count_actual}</p>
                    <p className="text-[10px] uppercase tracking-wide text-faint">clips</p>
                  </div>
                  <div>
                    <p className="font-mono text-[17px] text-paper">{campaign.rendered_count}</p>
                    <p className="text-[10px] uppercase tracking-wide text-faint">renders</p>
                  </div>
                </div>

                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/7">
                  <div className="h-full rounded-full bg-flame-500" style={{ width: `${progress}%` }} />
                </div>
                <div className="mt-2 flex items-center justify-between text-[10.5px] text-faint">
                  <span>{campaign.approved_count} approved</span>
                  <span>{progress}% of clips</span>
                </div>

                <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-white/6 pt-3 text-[11px] text-faint">
                  <span className="inline-flex items-center gap-1.5">
                    <Clock className="h-3 w-3" /> {formatDuration(campaign.target_duration_ms, true)} target
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Sparkles className="h-3 w-3" /> {campaign.caption_style_name || "Workspace caption"}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Film className="h-3 w-3" /> {campaign.source_minutes} source min
                  </span>
                </div>
              </Panel>
            );
          })}
        </div>
      )}

      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="New campaign"
        description="The brief guides AI clip selection. Automation only runs for connected, real jobs."
        wide
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" form="campaign-create" loading={submitting}>Create campaign</Button>
          </>
        }
      >
        <form id="campaign-create" onSubmit={create} className="space-y-4">
          <Field label="Campaign name">
            <Input
              required
              maxLength={160}
              value={form.name}
              onChange={(event) => change("name", event.target.value)}
              placeholder="Founder stories - launch week"
            />
          </Field>
          <Field label="Brief" hint="Editorial direction for clip selection: audience, angle, moments to prefer, claims to avoid.">
            <Textarea
              value={form.brief}
              onChange={(event) => change("brief", event.target.value)}
              placeholder="Find contrarian lessons for early-stage founders. Prefer concrete numbers and personal mistakes. Avoid product pitches."
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Aspect ratio">
              <Select value={form.aspect_ratio} onChange={(event) => change("aspect_ratio", event.target.value)}>
                <option value="9:16">9:16 vertical</option>
                <option value="4:5">4:5 portrait</option>
                <option value="1:1">1:1 square</option>
                <option value="16:9">16:9 landscape</option>
              </Select>
            </Field>
            <Field label="Clip length">
              <Select value={form.target_seconds} onChange={(event) => change("target_seconds", event.target.value)}>
                <option value="15">15 seconds</option>
                <option value="30">30 seconds</option>
                <option value="45">45 seconds</option>
                <option value="60">60 seconds</option>
                <option value="90">90 seconds</option>
              </Select>
            </Field>
            <Field label="Clips per video">
              <Input type="number" min={1} max={20} value={form.clip_count} onChange={(event) => change("clip_count", event.target.value)} />
            </Field>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Minimum score">
              <Input type="number" min={0} max={100} value={form.min_score} onChange={(event) => change("min_score", event.target.value)} />
            </Field>
            <Field label="Caption style">
              <Select value={form.caption_style_id} onChange={(event) => change("caption_style_id", event.target.value)}>
                <option value="">Workspace default</option>
                {(styles.data || []).map((style) => (
                  <option key={style.id} value={style.id}>{style.name}</option>
                ))}
              </Select>
            </Field>
            <Field label="Accent color">
              <Input type="color" value={form.accent_color} onChange={(event) => change("accent_color", event.target.value)} className="h-10 cursor-pointer p-1" />
            </Field>
          </div>
          <Field label="Brand mark" hint="Optional text watermark applied to automatic renders in this campaign’s accent color.">
            <Input maxLength={200} value={form.logo_text} onChange={(event) => change("logo_text", event.target.value)} placeholder="@yourbrand" />
          </Field>
          <div className="space-y-3 rounded-xl border border-white/8 bg-ink-850/50 p-3.5">
            <Switch
              checked={form.auto_approve}
              onCheckedChange={(value) => setForm((current) => ({
                ...current,
                auto_approve: value,
                auto_render: value ? current.auto_render : false,
              }))}
              label="Auto-approve clips above the minimum score"
            />
            <Switch
              checked={form.auto_render}
              disabled={!form.auto_approve}
              onCheckedChange={(value) => change("auto_render", value)}
              label="Auto-render approved clips with this campaign’s style"
            />
          </div>
          {formError ? <Alert>{formError}</Alert> : null}
        </form>
      </Dialog>
    </div>
  );
}
