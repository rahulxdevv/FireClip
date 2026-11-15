"use client";

import { useSearchParams } from "next/navigation";
import * as React from "react";
import { CheckCircle2, ExternalLink, Link2, ShieldCheck, Unplug } from "lucide-react";
import { PageHeader } from "@/components/shared";
import {
  Alert,
  Badge,
  Button,
  Dialog,
  EmptyState,
  PageSkeleton,
  Panel,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatDateTime } from "@/lib/format";
import type { ConnectStart, SocialAccount } from "@/lib/types";

const PLATFORMS = [
  {
    id: "youtube",
    name: "YouTube",
    scope: "youtube.upload, youtube.readonly",
    env: "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET",
    note: "Uploads Shorts and regular videos, reads view and like counts back.",
  },
  {
    id: "tiktok",
    name: "TikTok",
    scope: "video.publish, user.info.basic",
    env: "TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET",
    note: "Direct post is gated by TikTok's app audit. Errors are shown verbatim.",
  },
  {
    id: "instagram",
    name: "Instagram",
    scope: "instagram_content_publish, instagram_basic",
    env: "INSTAGRAM_CLIENT_ID / INSTAGRAM_CLIENT_SECRET",
    note: "Reels publishing needs a public media URL. Requires a Business account linked to a page.",
  },
  {
    id: "facebook",
    name: "Facebook",
    scope: "pages_manage_posts, pages_read_engagement",
    env: "FACEBOOK_CLIENT_ID / FACEBOOK_CLIENT_SECRET",
    note: "Publishes video to a page you manage.",
  },
];

export default function AccountsPage() {
  const params = useSearchParams();
  const accounts = useApi<SocialAccount[]>("/api/publishing/accounts");
  const [dialog, setDialog] = React.useState<{ platform: string; configured: boolean; message: string; url?: string | null } | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);
  const shown = React.useRef(false);

  React.useEffect(() => {
    if (shown.current) return;
    const status = params.get("status");
    const platform = params.get("platform");
    if (!status) return;
    shown.current = true;
    if (status === "connected") {
      toast(`${platform} connected`, "success");
      accounts.refresh();
    } else {
      toast(params.get("message") || "Connection failed", "error");
    }
  }, [params, accounts]);

  async function connect(platformId: string) {
    setBusy(platformId);
    try {
      const result = await api.get<ConnectStart>(`/api/publishing/connect/${platformId}`);
      if (result.configured && result.authorize_url) {
        window.location.href = result.authorize_url;
      } else {
        setDialog({ platform: platformId, configured: false, message: result.message });
      }
    } catch (err) {
      setDialog({ platform: platformId, configured: false, message: errorMessage(err) });
    } finally {
      setBusy(null);
    }
  }

  async function disconnect(account: SocialAccount) {
    if (!window.confirm(`Disconnect ${account.account_name}? Scheduled posts on this account will be cancelled.`)) return;
    setBusy(account.id);
    try {
      await api.delete(`/api/publishing/accounts/${account.id}`);
      toast("Account disconnected", "success");
      accounts.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Distribute"
        title="Social accounts"
        description="OAuth connections are stored encrypted at rest. Tokens never reach the browser."
      />

      {accounts.error ? <Alert className="mb-4">{accounts.error}</Alert> : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {PLATFORMS.map((platform) => {
          const connected = (accounts.data || []).filter((account) => account.platform === platform.id);
          return (
            <Panel key={platform.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-[14px] font-medium">{platform.name}</p>
                    {connected.length > 0 ? <Badge tone="mint">{connected.length} connected</Badge> : <Badge tone="neutral">not connected</Badge>}
                  </div>
                  <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">{platform.note}</p>
                  <p className="mt-2 font-mono text-[9.5px] text-faint">{platform.scope}</p>
                </div>
                <ShieldCheck className="h-4 w-4 shrink-0 text-faint" />
              </div>

              {connected.length > 0 ? (
                <div className="mt-3 space-y-2">
                  {connected.map((account) => (
                    <div key={account.id} className="flex items-center justify-between gap-2 rounded-lg border border-white/8 bg-ink-850 px-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-[12px] text-paper">{account.account_name}</p>
                        <p className="font-mono text-[9.5px] text-faint">
                          token expires {account.token_expires_at ? formatDateTime(account.token_expires_at) : "when revoked"}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        loading={busy === account.id}
                        onClick={() => disconnect(account)}
                      >
                        <Unplug className="h-3 w-3" /> Disconnect
                      </Button>
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="mt-3 flex items-center justify-between gap-2">
                <p className="font-mono text-[9px] text-faint">{platform.env}</p>
                <Button size="sm" variant="outline" loading={busy === platform.id} onClick={() => connect(platform.id)}>
                  <Link2 className="h-3 w-3" /> Connect
                </Button>
              </div>
            </Panel>
          );
        })}
      </div>

      {accounts.loading && !accounts.data ? <div className="mt-4"><PageSkeleton /></div> : null}

      {(accounts.data || []).length === 0 ? (
        <Panel className="mt-5">
          <EmptyState
            icon={<Link2 className="h-5 w-5" />}
            title="No connections yet"
            description="Connecting requires platform OAuth credentials on the server. Without them FireClip tells you exactly which variables to set - it does not simulate a connection."
          />
        </Panel>
      ) : null}

      <Dialog
        open={Boolean(dialog)}
        onOpenChange={(open) => !open && setDialog(null)}
        title={`${dialog ? PLATFORMS.find((item) => item.id === dialog.platform)?.name : ""} is not configured`}
        description="Add the OAuth application credentials to the server environment, then restart the API."
      >
        <div className="space-y-3">
          <Alert tone="info">{dialog?.message}</Alert>
          {dialog ? (
            <div className="rounded-lg border border-white/8 bg-ink-850 p-3 font-mono text-[10.5px] text-faint">
              {PLATFORMS.find((item) => item.id === dialog.platform)?.env}
            </div>
          ) : null}
          <p className="text-[11.5px] leading-relaxed text-faint">
            Callback URL: <code className="font-mono text-muted">/api/publishing/callback/&lt;platform&gt;</code> on
            your backend public URL. Add it to the platform&apos;s developer console.
          </p>
        </div>
      </Dialog>
    </div>
  );
}
