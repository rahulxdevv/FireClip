"use client";

import { useParams } from "next/navigation";
import * as React from "react";
import { Download, Film, Lock, Play } from "lucide-react";
import { Alert, Button, Field, Input, PageSkeleton } from "@/components/ui";
import { Logo } from "@/components/logo";
import { api, errorMessage } from "@/lib/api";
import { formatBytes, formatDuration } from "@/lib/format";
import type { PublicShare } from "@/lib/types";

export default function PublicSharePage() {
  const params = useParams<{ token: string }>();
  const token = params?.token || "";
  const [share, setShare] = React.useState<PublicShare | null>(null);
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [unlocking, setUnlocking] = React.useState(false);

  React.useEffect(() => {
    if (!token) return;
    let active = true;
    api
      .get<PublicShare>(`/api/public/shares/${token}`)
      .then((data) => {
        if (active) setShare(data);
      })
      .catch((err) => {
        if (active) setError(errorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  async function unlock(event: React.FormEvent) {
    event.preventDefault();
    setUnlocking(true);
    setError(null);
    try {
      const data = await api.post<PublicShare>(`/api/public/shares/${token}/unlock`, { password });
      setShare(data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setUnlocking(false);
    }
  }

  return (
    <div className="min-h-screen bg-ink-950">
      <header className="border-b border-paper/8">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4">
          <Logo size={30} />
          <span className="text-[11.5px] font-semibold text-flame-400">Shared clip</span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-5 py-10">
        {loading ? (
          <PageSkeleton />
        ) : error && !share ? (
          <div className="mx-auto max-w-md pt-16">
            <Alert title="This link is unavailable">{error}</Alert>
            <p className="mt-4 text-center text-[12px] text-faint">
              Ask the sender for a fresh link. Links can expire or be revoked.
            </p>
          </div>
        ) : share?.locked ? (
          <div className="mx-auto max-w-md pt-10">
            <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl border border-paper/10 bg-ink-900 text-flame-500">
              <Lock className="h-5 w-5" />
            </div>
            <h1 className="text-[24px] font-semibold tracking-tight">This clip is protected</h1>
            <p className="mt-1.5 text-[13px] text-muted">Enter the password the sender shared with you.</p>
            <form onSubmit={unlock} className="mt-6 space-y-4">
              <Field label="Password">
                <Input
                  type="password"
                  required
                  autoFocus
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                />
              </Field>
              {error ? <Alert>{error}</Alert> : null}
              <Button type="submit" className="w-full" size="lg" loading={unlocking}>
                <Play className="h-4 w-4" /> Watch clip
              </Button>
            </form>
          </div>
        ) : share ? (
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px]">
            <div>
              <div className="overflow-hidden rounded-2xl border border-white/10 bg-black">
                {share.media_url ? (
                  <video
                    controls
                    playsInline
                    preload="metadata"
                    poster={share.thumbnail_url || undefined}
                    className="max-h-[72vh] w-full"
                    src={share.media_url}
                  />
                ) : (
                  <div className="flex aspect-[9/16] max-h-[72vh] items-center justify-center text-ink-600">
                    <Film className="h-8 w-8" />
                  </div>
                )}
              </div>
              {share.expires_at ? (
                <p className="mt-3 text-center text-[10.5px] text-faint">
                  Link expires {new Date(share.expires_at).toLocaleDateString()}
                </p>
              ) : null}
            </div>

            <aside className="space-y-4">
              <div>
                <h1 className="display text-[26px] text-paper">{share.title || share.filename}</h1>
              </div>
              <dl className="space-y-2 border-y border-paper/8 py-4 text-[12px]">
                {share.duration_ms ? (
                  <div className="flex justify-between"><dt className="text-faint">Duration</dt><dd className="font-mono text-muted">{formatDuration(share.duration_ms, true)}</dd></div>
                ) : null}
                {share.width && share.height ? (
                  <div className="flex justify-between"><dt className="text-faint">Dimensions</dt><dd className="font-mono text-muted">{share.width}×{share.height}</dd></div>
                ) : null}
                {share.size_bytes ? (
                  <div className="flex justify-between"><dt className="text-faint">File size</dt><dd className="font-mono text-muted">{formatBytes(share.size_bytes)}</dd></div>
                ) : null}
                {share.format ? (
                  <div className="flex justify-between"><dt className="text-faint">Format</dt><dd className="font-mono text-muted">{share.format}</dd></div>
                ) : null}
              </dl>
              {share.download_url ? (
                <a href={share.download_url} download>
                  <Button variant="outline" className="w-full">
                    <Download className="h-4 w-4" /> Download
                  </Button>
                </a>
              ) : null}
              <p className="text-[10.5px] leading-relaxed text-faint">
                This page is served by the workspace that created the clip. No tracking scripts,
                no third-party embeds.
              </p>
            </aside>
          </div>
        ) : null}
      </main>
    </div>
  );
}
