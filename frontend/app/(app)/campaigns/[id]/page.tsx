"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";
import {
  ArrowLeft,
  CalendarClock,
  ExternalLink,
  Film,
  Flame,
  Image as ImageIcon,
  Play,
  Plus,
  Trash2,
  Upload,
  Wand2,
} from "lucide-react";
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
import { formatDateTime, formatDuration } from "@/lib/format";
import type { CampaignDetail, CaptionStyle, Clip, SocialAccount, Video } from "@/lib/types";

interface FormState {
  name: string;
  description: string;
  brief: string;
  status: "active" | "paused" | "archived";
  aspect_ratio: string;
  target_seconds: string;
  clip_count: string;
  min_score: string;
  caption_style_id: string;
  auto_approve: boolean;
  auto_render: boolean;
  auto_publish: boolean;
  auto_publish_min_score: string;
  publish_account_ids: string[];
  publish_mode: "now" | "next_slot";
  publish_hour_utc: string;
  publish_privacy: string;
  text_color: string;
  highlight_color: string;
  outline_width: string;
  logo_text: string;
  headline: string;
  headline_enabled: boolean;
  hashtags: string;
  cta: string;
  logo_asset_key: string;
  logo_position: string;
}

function toForm(campaign: CampaignDetail): FormState {
  const overrides = campaign.caption_overrides || {};
  return {
    name: campaign.name,
    description: campaign.description,
    brief: campaign.brief,
    status: campaign.status,
    aspect_ratio: campaign.aspect_ratio,
    target_seconds: String(Math.round(campaign.target_duration_ms / 1000)),
    clip_count: String(campaign.clip_count),
    min_score: String(campaign.min_score),
    caption_style_id: campaign.caption_style_id || "",
    auto_approve: campaign.auto_approve,
    auto_render: campaign.auto_render,
    auto_publish: campaign.auto_publish,
    auto_publish_min_score: String(campaign.auto_publish_min_score ?? 0),
    publish_account_ids: campaign.publish_account_ids || [],
    publish_mode: campaign.publish_mode || "now",
    publish_hour_utc: String(campaign.publish_hour_utc ?? 18),
    publish_privacy: campaign.publish_privacy || "public",
    text_color: String(overrides.text_color || "#ffffff"),
    highlight_color: String(overrides.highlight_color || campaign.brand?.accent_color || "#ff6a1f"),
    outline_width: String(overrides.outline_width ?? 3),
    logo_text: campaign.brand?.logo_text || "",
    headline: campaign.brand?.headline || "",
    headline_enabled: campaign.brand?.headline_enabled ?? true,
    hashtags: (campaign.brand?.hashtags || []).join(" "),
    cta: campaign.brand?.cta || "",
    logo_asset_key: campaign.brand?.logo_asset_key || "",
    logo_position: campaign.brand?.logo_position || "top_center",
  };
}

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const campaign = useApi<CampaignDetail>(`/api/campaigns/${id}`);
  const styles = useApi<CaptionStyle[]>("/api/caption-styles");
  const library = useApi<Video[]>("/api/videos?limit=300");
  const accounts = useApi<SocialAccount[]>("/api/publishing/accounts");
  const [form, setForm] = React.useState<FormState | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [uploadingLogo, setUploadingLogo] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [attachOpen, setAttachOpen] = React.useState(false);
  const [selectedVideos, setSelectedVideos] = React.useState<string[]>([]);
  const [actionError, setActionError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (campaign.data) setForm(toForm(campaign.data));
  }, [campaign.data]);

  function change<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => (current ? { ...current, [key]: value } : current));
  }

  async function uploadLogo(file: File) {
    setUploadingLogo(true);
    try {
      const data = new FormData();
      data.append("file", file);
      data.append("kind", "image");
      const asset = await api.upload<{ key: string }>("/api/assets", data);
      change("logo_asset_key", asset.key);
      toast("Logo uploaded. Save the campaign to apply it.", "success");
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setUploadingLogo(false);
    }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!form) return;
    if (form.auto_publish && form.publish_account_ids.length === 0) {
      setActionError("Select at least one connected account before enabling auto-publish.");
      return;
    }
    setSaving(true);
    setActionError(null);
    try {
      await api.patch(`/api/campaigns/${id}`, {
        name: form.name.trim(),
        description: form.description.trim(),
        brief: form.brief.trim(),
        status: form.status,
        aspect_ratio: form.aspect_ratio,
        target_duration_ms: Number(form.target_seconds) * 1000,
        clip_count: Number(form.clip_count),
        min_score: Number(form.min_score),
        caption_style_id: form.caption_style_id || null,
        caption_overrides: {
          ...(campaign.data?.caption_overrides || {}),
          text_color: form.text_color,
          highlight_color: form.highlight_color,
          outline_width: Number(form.outline_width),
        },
        auto_approve: form.auto_approve,
        auto_render: form.auto_render,
        auto_publish: form.auto_publish,
        auto_publish_min_score: Number(form.auto_publish_min_score),
        publish_account_ids: form.publish_account_ids,
        publish_mode: form.publish_mode,
        publish_hour_utc: Number(form.publish_hour_utc),
        publish_privacy: form.publish_privacy,
        brand: {
          ...(campaign.data?.brand || {}),
          accent_color: form.highlight_color,
          logo_text: form.logo_text.trim(),
          headline: form.headline.trim(),
          headline_enabled: form.headline_enabled,
          hashtags: form.hashtags.split(/[\s,]+/).filter(Boolean),
          cta: form.cta.trim(),
          logo_asset_key: form.logo_asset_key || "",
          logo_position: form.logo_position,
        },
      });
      await campaign.refresh();
      toast("Campaign saved", "success");
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function attach() {
    if (selectedVideos.length === 0) return;
    setBusy("attach");
    setActionError(null);
    try {
      await api.post(`/api/campaigns/${id}/videos`, { video_ids: selectedVideos });
      setSelectedVideos([]);
      setAttachOpen(false);
      await campaign.refresh();
      toast("Videos added to campaign", "success");
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function removeVideo(video: Video) {
    if (!window.confirm(`Remove “${video.title}” from this campaign? The video and its clips stay in the library.`)) return;
    setBusy(video.id);
    try {
      await api.delete(`/api/campaigns/${id}/videos/${video.id}`);
      await campaign.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function analyze() {
    setBusy("analyze");
    setActionError(null);
    try {
      const result = await api.post<{ queued: number }>(`/api/campaigns/${id}/analyze`, {});
      toast(`${result.queued} video${result.queued === 1 ? "" : "s"} queued for campaign analysis`, "success");
      await campaign.refresh();
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function openEditor(clip: Clip) {
    setBusy(clip.id);
    try {
      const project = await api.post<{ id: string }>("/api/editors", {
        clip_id: clip.id,
        aspect_ratio: campaign.data?.aspect_ratio || clip.aspect_ratio,
      });
      router.push(`/editor/${project.id}`);
    } catch (err) {
      toast(errorMessage(err), "error");
      setBusy(null);
    }
  }

  async function removeCampaign() {
    if (!campaign.data) return;
    if (!window.confirm(`Delete “${campaign.data.name}”? Videos and clips are kept, but their campaign link is removed.`)) return;
    try {
      await api.delete(`/api/campaigns/${id}`);
      toast("Campaign deleted", "success");
      router.push("/campaigns");
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  }

  if (campaign.error) return <Alert>{campaign.error}</Alert>;
  if (campaign.loading && !campaign.data) return <PageSkeleton />;
  if (!campaign.data || !form) return null;
  const data = campaign.data;
  const attachedIds = new Set(data.videos.map((video) => video.id));
  const available = (library.data || []).filter((video) => !attachedIds.has(video.id));

  return (
    <div className="mx-auto max-w-6xl">
      <Link href="/campaigns" className="mb-4 inline-flex items-center gap-1.5 text-[11.5px] text-faint hover:text-paper">
        <ArrowLeft className="h-3.5 w-3.5" /> Campaigns
      </Link>
      <PageHeader
        title={data.name}
        description={data.description || "A reusable brief for every video in this batch."}
        actions={
          <>
            <Button variant="outline" size="sm" loading={busy === "analyze"} onClick={analyze} disabled={data.video_count === 0}>
              <Wand2 className="h-3.5 w-3.5" /> Run analysis
            </Button>
            <Button variant="danger" size="icon" onClick={removeCampaign} aria-label="Delete campaign">
              <Trash2 className="h-4 w-4" />
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 text-[11px]">
        <Badge tone={data.status === "active" ? "mint" : data.status === "paused" ? "ember" : "neutral"}>{data.status}</Badge>
        <Badge tone="outline">{data.aspect_ratio}</Badge>
        <Badge tone="outline">{formatDuration(data.target_duration_ms, true)} target</Badge>
        {data.source !== "internal" ? <Badge tone="neutral">{data.source}</Badge> : null}
        <span className="text-faint">Created {formatDateTime(data.created_at)}</span>
        {data.source_url ? (
          <a href={data.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-flame-300 hover:underline">
            <ExternalLink className="h-3 w-3" /> Campaign source
          </a>
        ) : null}
      </div>

      {actionError ? <Alert className="mb-4">{actionError}</Alert> : null}

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {[
          ["Videos", data.video_count],
          ["Clips", data.clip_count_actual],
          ["Approved", data.approved_count],
          ["Renders", data.rendered_count],
          ["Source min", data.source_minutes],
        ].map(([label, value]) => (
          <Panel key={String(label)} className="p-3.5">
            <p className="font-mono text-[22px] leading-none text-paper">{value}</p>
            <p className="mt-1.5 text-[11px] text-faint">{label}</p>
          </Panel>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5">
          <Panel>
            <PanelHeader
              title="Videos"
              description="Analysis uses the campaign brief and applies the target length, score floor and automation."
              action={<Button size="sm" variant="outline" onClick={() => setAttachOpen(true)}><Plus className="h-3.5 w-3.5" /> Add</Button>}
            />
            {data.videos.length === 0 ? (
              <EmptyState
                icon={<Film className="h-5 w-5" />}
                title="No videos in this campaign"
                description="Attach existing library videos, or import new ones and pick this campaign during import."
                action={<Button size="sm" onClick={() => setAttachOpen(true)}><Plus className="h-4 w-4" /> Add videos</Button>}
              />
            ) : (
              <div className="divide-y divide-white/6">
                {data.videos.map((video) => (
                  <div key={video.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                    <div className="min-w-0">
                      <Link href={`/videos/${video.id}`} className="truncate text-[12.5px] font-medium text-paper hover:text-flame-400">
                        {video.title}
                      </Link>
                      <p className="mt-0.5 text-[10.5px] text-faint">
                        {formatDuration(video.duration_seconds)}, {video.status}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      loading={busy === video.id}
                      onClick={() => removeVideo(video)}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel>
            <PanelHeader title="Clips" description="Sorted by predicted strength. Opening a clip creates or reuses its editor project." />
            {data.clips.length === 0 ? (
              <EmptyState
                icon={<Flame className="h-5 w-5" />}
                title="No clips yet"
                description="Run campaign analysis on the attached videos. Existing transcripts are reused automatically."
              />
            ) : (
              <div className="divide-y divide-white/6">
                {data.clips.map((clip) => (
                  <div key={clip.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                    <span className="w-9 shrink-0 font-mono text-[13px] text-flame-400">{Math.round(clip.virality_score)}</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12.5px] font-medium">{clip.title}</p>
                      <p className="mt-0.5 truncate text-[10.5px] text-faint">
                        {formatDuration(clip.duration_ms, true)}, {clip.status}, {clip.hook || clip.description}
                      </p>
                    </div>
                    <Button size="sm" variant="outline" loading={busy === clip.id} onClick={() => openEditor(clip)}>
                      <Play className="h-3.5 w-3.5" /> Edit
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>

        <Panel className="h-fit">
          <PanelHeader title="Campaign brief" description="Changes apply to the next analysis, not already-generated clips." />
          <form onSubmit={save} className="space-y-4 p-5">
            <Field label="Name">
              <Input required maxLength={160} value={form.name} onChange={(event) => change("name", event.target.value)} />
            </Field>
            <Field label="Description">
              <Input maxLength={2000} value={form.description} onChange={(event) => change("description", event.target.value)} />
            </Field>
            <Field label="Editorial brief">
              <Textarea value={form.brief} onChange={(event) => change("brief", event.target.value)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Status">
                <Select value={form.status} onChange={(event) => change("status", event.target.value as FormState["status"])}>
                  <option value="active">Active</option>
                  <option value="paused">Paused</option>
                  <option value="archived">Archived</option>
                </Select>
              </Field>
              <Field label="Aspect">
                <Select value={form.aspect_ratio} onChange={(event) => change("aspect_ratio", event.target.value)}>
                  <option value="9:16">9:16</option>
                  <option value="4:5">4:5</option>
                  <option value="1:1">1:1</option>
                  <option value="16:9">16:9</option>
                </Select>
              </Field>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Seconds">
                <Input type="number" min={5} max={180} value={form.target_seconds} onChange={(event) => change("target_seconds", event.target.value)} />
              </Field>
              <Field label="Clips">
                <Input type="number" min={1} max={20} value={form.clip_count} onChange={(event) => change("clip_count", event.target.value)} />
              </Field>
              <Field label="Min score">
                <Input type="number" min={0} max={100} value={form.min_score} onChange={(event) => change("min_score", event.target.value)} />
              </Field>
            </div>
            <Field label="Caption style">
              <Select value={form.caption_style_id} onChange={(event) => change("caption_style_id", event.target.value)}>
                <option value="">Workspace default</option>
                {(styles.data || []).map((style) => (
                  <option key={style.id} value={style.id}>{style.name}</option>
                ))}
              </Select>
            </Field>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Text">
                <Input type="color" value={form.text_color} onChange={(event) => change("text_color", event.target.value)} className="h-10 cursor-pointer p-1" />
              </Field>
              <Field label="Highlight">
                <Input type="color" value={form.highlight_color} onChange={(event) => change("highlight_color", event.target.value)} className="h-10 cursor-pointer p-1" />
              </Field>
              <Field label="Outline">
                <Input type="number" min={0} max={12} value={form.outline_width} onChange={(event) => change("outline_width", event.target.value)} />
              </Field>
            </div>
            <div className="rounded-xl border border-white/8 bg-ink-850/50 p-3.5">
              <p className="mb-3 text-[11px] font-semibold text-faint">Brand kit</p>
              <div className="space-y-3">
                <Field label="Headline overlay" hint="Short hook shown at the top of every auto-render.">
                  <Input maxLength={160} value={form.headline} onChange={(event) => change("headline", event.target.value)} placeholder="The part nobody tells you" />
                </Field>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[11px] text-muted">Show headline</span>
                  <Switch checked={form.headline_enabled} onCheckedChange={(value) => change("headline_enabled", value)} />
                </div>
                <Field label="Required hashtags" hint="Added to every automatic post. Space or comma separated.">
                  <Input maxLength={300} value={form.hashtags} onChange={(event) => change("hashtags", event.target.value)} placeholder="#shorts #creator" />
                </Field>
                <Field label="Call to action overlay">
                  <Input maxLength={120} value={form.cta} onChange={(event) => change("cta", event.target.value)} placeholder="Follow for more" />
                </Field>
                <Field label="Text mark fallback">
                  <Input maxLength={200} value={form.logo_text} onChange={(event) => change("logo_text", event.target.value)} placeholder="@yourbrand" />
                </Field>
                <div>
                  <p className="mb-1.5 text-[11px] text-muted">Logo image</p>
                  <div className="flex items-center gap-2">
                    {form.logo_asset_key ? (
                      <Image
                        src={`/api/assets/${form.logo_asset_key}`}
                        alt="Campaign logo"
                        width={44}
                        height={44}
                        unoptimized
                        className="h-11 w-11 rounded border border-white/10 bg-ink-950 object-contain"
                      />
                    ) : (
                      <span className="flex h-11 w-11 items-center justify-center rounded border border-dashed border-white/15 text-faint"><ImageIcon className="h-4 w-4" /></span>
                    )}
                    <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-white/10 px-2.5 py-1.5 text-[11px] hover:bg-white/5">
                      <Upload className="h-3.5 w-3.5" /> {uploadingLogo ? "Uploading..." : form.logo_asset_key ? "Replace" : "Upload"}
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp,image/gif"
                        className="hidden"
                        disabled={uploadingLogo}
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) uploadLogo(file);
                          event.target.value = "";
                        }}
                      />
                    </label>
                    {form.logo_asset_key ? (
                      <button type="button" onClick={() => change("logo_asset_key", "")} className="text-[10.5px] text-faint hover:text-rose">Remove</button>
                    ) : null}
                  </div>
                </div>
                <Field label="Logo position">
                  <Select value={form.logo_position} onChange={(event) => change("logo_position", event.target.value)}>
                    <option value="top_center">Top center</option>
                    <option value="top_left">Top left</option>
                    <option value="top_right">Top right</option>
                  </Select>
                </Field>
              </div>
            </div>

            <div className="space-y-3 rounded-xl border border-white/8 bg-ink-850/50 p-3.5">
              <p className="mb-3 text-[11px] font-semibold text-faint">Automation</p>
              <Switch
                checked={form.auto_approve}
                onCheckedChange={(value) => setForm((current) => current ? {
                  ...current,
                  auto_approve: value,
                  auto_render: value ? current.auto_render : false,
                  auto_publish: value ? current.auto_publish : false,
                } : current)}
                label="Auto-approve clips above minimum score"
              />
              <Switch
                checked={form.auto_render}
                disabled={!form.auto_approve}
                onCheckedChange={(value) => setForm((current) => current ? {
                  ...current,
                  auto_render: value,
                  auto_publish: value ? current.auto_publish : false,
                } : current)}
                label="Auto-render approved clips"
              />
              <Switch
                checked={form.auto_publish}
                disabled={!form.auto_render}
                onCheckedChange={(value) => change("auto_publish", value)}
                label="Auto-publish rendered clips"
              />
              {form.auto_publish ? (
                <div className="space-y-3 border-t border-white/6 pt-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Quality floor" hint="Skip below this score.">
                      <Input type="number" min={0} max={100} value={form.auto_publish_min_score} onChange={(event) => change("auto_publish_min_score", event.target.value)} />
                    </Field>
                    <Field label="When">
                      <Select value={form.publish_mode} onChange={(event) => change("publish_mode", event.target.value as "now" | "next_slot")}>
                        <option value="now">Post now</option>
                        <option value="next_slot">Next preferred slot</option>
                      </Select>
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Preferred hour (UTC)">
                      <Input type="number" min={0} max={23} value={form.publish_hour_utc} onChange={(event) => change("publish_hour_utc", event.target.value)} />
                    </Field>
                    <Field label="Privacy">
                      <Select value={form.publish_privacy} onChange={(event) => change("publish_privacy", event.target.value)}>
                        <option value="public">Public</option>
                        <option value="unlisted">Unlisted</option>
                        <option value="private">Private</option>
                      </Select>
                    </Field>
                  </div>
                  <div>
                    <p className="mb-1.5 text-[11px] text-muted">Publish to</p>
                    {(accounts.data || []).filter((account) => account.status === "connected").length === 0 ? (
                      <p className="rounded-md border border-ember/20 bg-ember/5 px-2.5 py-2 text-[10.5px] text-ember">
                        Connect a social account first. Nothing is posted without an authorised account.
                      </p>
                    ) : (
                      <div className="space-y-1.5">
                        {(accounts.data || []).filter((account) => account.status === "connected").map((account) => (
                          <label key={account.id} className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-1 hover:bg-white/4">
                            <input
                              type="checkbox"
                              className="h-3.5 w-3.5 accent-flame-500"
                              checked={form.publish_account_ids.includes(account.id)}
                              onChange={(event) => {
                                const next = event.target.checked
                                  ? [...form.publish_account_ids, account.id]
                                  : form.publish_account_ids.filter((value) => value !== account.id);
                                change("publish_account_ids", next);
                              }}
                            />
                            <span className="min-w-0 flex-1 truncate text-[11px]">{account.account_name}</span>
                            <span className="text-[10.5px] text-faint">{account.platform}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                  <p className="flex items-start gap-1.5 text-[10px] leading-relaxed text-faint">
                    <CalendarClock className="mt-0.5 h-3 w-3 shrink-0" />
                    Preferred slots are UTC. Posts wait for the next chosen hour and can be cancelled from Schedule.
                  </p>
                </div>
              ) : null}
            </div>
            <Button type="submit" loading={saving} className="w-full">Save campaign</Button>
          </form>
        </Panel>
      </div>

      <Dialog
        open={attachOpen}
        onOpenChange={setAttachOpen}
        title="Add videos"
        description="Videos already in another campaign will move to this one."
        wide
        footer={
          <>
            <Button variant="ghost" onClick={() => setAttachOpen(false)}>Cancel</Button>
            <Button loading={busy === "attach"} onClick={attach} disabled={selectedVideos.length === 0}>
              Add {selectedVideos.length || ""} video{selectedVideos.length === 1 ? "" : "s"}
            </Button>
          </>
        }
      >
        {available.length === 0 ? (
          <p className="py-8 text-center text-[13px] text-muted">Every library video is already in this campaign.</p>
        ) : (
          <div className="max-h-80 space-y-1 overflow-y-auto">
            {available.map((video) => (
              <label key={video.id} className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 hover:bg-white/4">
                <input
                  type="checkbox"
                  checked={selectedVideos.includes(video.id)}
                  onChange={(event) =>
                    setSelectedVideos((current) =>
                      event.target.checked ? [...current, video.id] : current.filter((value) => value !== video.id),
                    )
                  }
                  className="h-4 w-4 accent-flame-500"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px]">{video.title}</span>
                  <span className="block text-[10.5px] text-faint">
                    {formatDuration(video.duration_seconds)}, {video.status}
                    {video.campaign_id ? ", in another campaign" : ""}
                  </span>
                </span>
              </label>
            ))}
          </div>
        )}
      </Dialog>
    </div>
  );
}
