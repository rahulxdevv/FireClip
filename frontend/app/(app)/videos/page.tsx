"use client";

import Link from "next/link";
import * as React from "react";
import { FolderPlus, Film, Plus, Search, UploadCloud } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { VideoCard } from "@/components/video-card";
import {
  Alert,
  Button,
  Dialog,
  EmptyState,
  Field,
  Input,
  PageSkeleton,
  Panel,
  Select,
  Textarea,
  Tabs,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { useDebounced } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { relativeTime } from "@/lib/format";
import type { Campaign, ProjectItem, Video } from "@/lib/types";

export default function VideosPage() {
  const [status, setStatus] = React.useState("all");
  const [search, setSearch] = React.useState("");
  const [projectId, setProjectId] = React.useState("");
  const [campaignId, setCampaignId] = React.useState("");
  const debouncedSearch = useDebounced(search, 300);
  const [projectDialog, setProjectDialog] = React.useState(false);
  const [projectForm, setProjectForm] = React.useState({ name: "", description: "" });
  const [saving, setSaving] = React.useState(false);

  const query = new URLSearchParams();
  if (status !== "all") query.set("status", status === "processing" ? "transcribing" : status);
  if (projectId) query.set("project_id", projectId);
  if (campaignId) query.set("campaign_id", campaignId);
  if (debouncedSearch.trim()) query.set("search", debouncedSearch.trim());
  const path = `/api/videos?${query.toString()}`;

  const { data, error, loading, refresh } = useApi<Video[]>(path, {
    pollMs: 4000,
  });
  const projects = useApi<ProjectItem[]>("/api/projects");
  const campaigns = useApi<Campaign[]>("/api/campaigns");

  const videos = data || [];
  const processing = videos.filter((video) =>
    ["uploaded", "downloading", "probing", "transcribing", "analyzing"].includes(video.status),
  );
  const visible =
    status === "processing" ? processing : videos.filter((video) => status === "all" || video.status === status);

  async function createProject(event: React.FormEvent) {
    event.preventDefault();
    if (!projectForm.name.trim()) return;
    setSaving(true);
    try {
      await api.post("/api/projects", projectForm);
      setProjectDialog(false);
      setProjectForm({ name: "", description: "" });
      projects.refresh();
      toast("Project created", "success");
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PageHeader        title="Video library"
        description="Every source video in this workspace, with its processing state and metadata."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => setProjectDialog(true)}>
              <FolderPlus className="h-3.5 w-3.5" /> New project
            </Button>
            <Link href="/upload">
              <Button size="sm">
                <Plus className="h-3.5 w-3.5" /> Add video
              </Button>
            </Link>
          </>
        }
      />

      <Panel className="mb-5">
        <div className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by title or description"
              className="pl-9"
            />
          </div>
          <Select value={projectId} onChange={(event) => setProjectId(event.target.value)} className="sm:w-[180px]">
            <option value="">All projects</option>
            {(projects.data || []).map((project) => (
              <option key={project.id} value={project.id}>
                {project.name} ({project.video_count})
              </option>
            ))}
          </Select>
          <Select value={campaignId} onChange={(event) => setCampaignId(event.target.value)} className="sm:w-[180px]">
            <option value="">All campaigns</option>
            {(campaigns.data || []).map((campaign) => (
              <option key={campaign.id} value={campaign.id}>
                {campaign.name} ({campaign.video_count})
              </option>
            ))}
          </Select>
        </div>
        <div className="px-3">
          <Tabs
            value={status}
            onValueChange={setStatus}
            tabs={[
              { value: "all", label: "All", count: videos.length },
              { value: "ready", label: "Ready" },
              { value: "processing", label: "Processing", count: processing.length },
              { value: "error", label: "Needs attention", count: videos.filter((v) => v.status === "error").length },
            ]}
          />
        </div>
      </Panel>

      {error ? <Alert className="mb-4">{error}</Alert> : null}

      {loading && !data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <PageSkeleton key={index} />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <Panel>
          <EmptyState
            icon={<Film className="h-5 w-5" />}
            title={videos.length === 0 ? "Your library is empty" : "No videos match these filters"}
            description={
              videos.length === 0
                ? "Upload a file or import a public URL. Processing starts automatically."
                : "Try clearing the search or switching the status filter."
            }
            action={
              videos.length === 0 ? (
                <div className="flex gap-2">
                  <Link href="/upload">
                    <Button size="sm">
                      <UploadCloud className="h-3.5 w-3.5" /> Upload
                    </Button>
                  </Link>
                  <Link href="/import">
                    <Button variant="outline" size="sm">
                      Import URL
                    </Button>
                  </Link>
                </div>
              ) : undefined
            }
          />
        </Panel>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {visible.map((video) => (
            <VideoCard key={video.id} video={video} />
          ))}
        </div>
      )}

      {projects.data && projects.data.length > 0 ? (
        <div className="mt-8">
          <h2 className="mb-3 text-[13px] font-semibold text-paper">Projects</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {projects.data.map((project) => (
              <button
                key={project.id}
                onClick={() => setProjectId(project.id === projectId ? "" : project.id)}
                className={`rounded-[var(--radius-card)] border p-4 text-left transition-colors ${
                  projectId === project.id
                    ? "border-flame-500/40 bg-flame-500/5"
                    : "border-paper/8 bg-ink-900 hover:border-paper/16"
                }`}
              >
                <p className="text-[13px] font-medium">{project.name}</p>
                <p className="mt-1 line-clamp-2 min-h-[16px] text-[11px] leading-relaxed text-faint">
                  {project.description || "No description"}
                </p>
                <p className="mt-2 text-[10.5px] text-faint">
                  {project.video_count} videos, {relativeTime(project.created_at)}
                </p>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <Dialog
        open={projectDialog}
        onOpenChange={setProjectDialog}
        title="Create a project"
        description="Group related videos, clips and renders together."
        footer={
          <>
            <Button variant="ghost" onClick={() => setProjectDialog(false)}>
              Cancel
            </Button>
            <Button onClick={createProject} loading={saving}>
              Create project
            </Button>
          </>
        }
      >
        <form onSubmit={createProject} className="space-y-4">
          <Field label="Project name">
            <Input
              autoFocus
              value={projectForm.name}
              onChange={(event) => setProjectForm({ ...projectForm, name: event.target.value })}
              placeholder="Podcast season 3"
              maxLength={160}
            />
          </Field>
          <Field label="Description" hint="Optional context for your team.">
            <Textarea
              value={projectForm.description}
              onChange={(event) => setProjectForm({ ...projectForm, description: event.target.value })}
              placeholder="Long-form interviews published every Tuesday"
              rows={3}
            />
          </Field>
        </form>
      </Dialog>
    </div>
  );
}
