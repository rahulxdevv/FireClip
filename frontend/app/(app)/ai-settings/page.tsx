"use client";

import * as React from "react";
import { CheckCircle2, Cpu, KeyRound, PlugZap, Server, Sparkles, TestTube2, TriangleAlert } from "lucide-react";
import { PageHeader } from "@/components/shared";
import {
  Alert,
  Badge,
  Button,
  Field,
  Input,
  PageSkeleton,
  Panel,
  PanelHeader,
  Select,
  Switch,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast } from "@/lib/stores";
import { formatBytes } from "@/lib/format";
import type { AIProvider, SystemStatus } from "@/lib/types";

interface EngineStatus {
  configured: string;
  diarization: string;
  engines: Record<string, { available: boolean; model: string; local: boolean; note: string | null }>;
}

export default function AiSettingsPage() {
  const providers = useApi<AIProvider[]>("/api/ai/providers");
  const engines = useApi<EngineStatus>("/api/ai/transcription");
  const status = useApi<SystemStatus>("/api/system/status");
  const [testing, setTesting] = React.useState<string | null>(null);
  const [testResults, setTestResults] = React.useState<Record<string, { ok: boolean; message: string; latency_ms: number }>>({});

  async function test(provider: string) {
    setTesting(provider);
    try {
      const result = await api.post<{ provider: string; ok: boolean; message: string; latency_ms: number }>(
        "/api/ai/test",
        { provider },
      );
      setTestResults((current) => ({ ...current, [provider]: result }));
      toast(result.ok ? `${provider} connected` : `${provider} failed`, result.ok ? "success" : "error");
    } catch (err) {
      setTestResults((current) => ({ ...current, [provider]: { ok: false, message: errorMessage(err), latency_ms: 0 } }));
    } finally {
      setTesting(null);
    }
  }

  if (providers.loading && !providers.data) return <PageSkeleton />;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader        title="AI & transcription"
        description="Keys are encrypted at rest with AES-GCM. The browser only ever learns whether a provider is configured."
        actions={
          <Button size="sm" variant="outline" onClick={() => { providers.refresh(); engines.refresh(); status.refresh(); }}>
            Refresh status
          </Button>
        }
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <StatusChip
          icon={<Cpu className="h-4 w-4" />}
          label="FFmpeg"
          value={status.data?.ffmpeg ? "available" : "missing"}
          healthy={Boolean(status.data?.ffmpeg)}
        />
        <StatusChip
          icon={<Server className="h-4 w-4" />}
          label="Job runner"
          value={status.data?.job_runner || "-"}
          healthy={Boolean(status.data)}
        />
        <StatusChip
          icon={<Sparkles className="h-4 w-4" />}
          label="Local ASR"
          value={engines.data?.engines.faster_whisper.available ? "installed" : "not installed"}
          healthy={Boolean(engines.data?.engines.faster_whisper.available)}
        />
      </div>

      <div className="space-y-4">
        {(providers.data || []).map((provider) => (
          <ProviderCard
            key={provider.provider}
            provider={provider}
            testing={testing === provider.provider}
            result={testResults[provider.provider]}
            onTest={() => test(provider.provider)}
            onSaved={() => providers.refresh()}
          />
        ))}
      </div>

      <Panel className="mt-6">
        <PanelHeader
          title="Transcription engines"
          description="Available engines come from the server environment. Nothing is simulated."
        />
        <div className="divide-y divide-paper/6">
          {Object.entries(engines.data?.engines || {}).map(([name, engine]) => (
            <div key={name} className="flex flex-wrap items-start justify-between gap-3 px-5 py-3.5">
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-[13px] font-medium">{name}</p>
                  <Badge tone={engine.available ? "mint" : "neutral"}>{engine.available ? "available" : "unavailable"}</Badge>
                  {engine.local ? <Badge tone="neutral">local</Badge> : <Badge tone="neutral">cloud</Badge>}
                </div>
                <p className="mt-1 text-[11.5px] text-faint">
                  model <code className="font-mono">{engine.model}</code>
                  {engine.note ? `, ${engine.note}` : ""}
                </p>
              </div>
            </div>
          ))}
          <div className="px-5 py-3.5">
            <p className="text-[12px] text-muted">Diarization</p>
            <p className="mt-1 text-[11.5px] leading-relaxed text-faint">
              Current mode: <code className="font-mono text-paper">{engines.data?.diarization}</code>. The
              pause-based estimate labels speaker turns and is marked as an estimate; pyannote requires the optional
              extra and HF token. Manual speaker labels always win.
            </p>
          </div>
        </div>
      </Panel>

      <Panel className="mt-6">
        <PanelHeader title="Platform diagnostics" />
        <div className="grid gap-3 p-5 sm:grid-cols-2">
          {[
            ["FFmpeg version", status.data?.ffmpeg_version || "-"],
            ["FFmpeg binary", status.data?.ffmpeg ? "found" : "not found"],
            ["yt-dlp", status.data?.ytdlp ? "available" : "missing"],
            ["Redis", status.data?.redis ? "connected" : "not configured"],
            ["Database", status.data?.database || "-"],
            ["Storage", status.data?.storage || "-"],
            ["Workspace media", status.data ? formatBytes(status.data.workspace_storage_bytes) : "-"],
            [
              "Disk free",
              status.data?.disk_free_gb != null ? `${status.data.disk_free_gb.toFixed(1)} GB` : "managed by S3",
            ],
          ].map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-3 rounded-[var(--radius-control)] border border-paper/8 bg-ink-850/60 px-3 py-2 text-[11.5px]">
              <span className="text-faint">{label}</span>
              <span className="truncate font-mono text-muted">{value}</span>
            </div>
          ))}
        </div>
      </Panel>

      <div className="mt-6">
        <Alert tone="info" title="Provider notes">
          <ul className="mt-1 space-y-1">
            <li>OpenAI, Anthropic and Gemini use environment keys or a workspace key saved below.</li>
            <li>Ollama is only used when explicitly selected as default, never as an automatic fallback.</li>
            <li>Hosted Whisper accepts up to 25MB per request; use faster-whisper locally for long recordings.</li>
          </ul>
        </Alert>
      </div>
    </div>
  );
}

function StatusChip({
  icon,
  label,
  value,
  healthy,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  healthy: boolean;
}) {
  return (
    <Panel className="flex items-center gap-3 px-4 py-3">
      <span className={`flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] ${healthy ? "bg-mint/10 text-mint" : "bg-rose/10 text-rose"}`}>
        {icon}
      </span>
      <div>
        <p className="text-[10.5px] text-faint">{label}</p>
        <p className="text-[12.5px] font-medium">{value}</p>
      </div>
    </Panel>
  );
}

function ProviderCard({
  provider,
  testing,
  result,
  onTest,
  onSaved,
}: {
  provider: AIProvider;
  testing: boolean;
  result?: { ok: boolean; message: string; latency_ms: number };
  onTest: () => void;
  onSaved: () => void;
}) {
  const heuristic = provider.provider === "heuristic";
  const [model, setModel] = React.useState(provider.model);
  const [baseUrl, setBaseUrl] = React.useState(provider.base_url);
  const [apiKey, setApiKey] = React.useState("");
  const [enabled, setEnabled] = React.useState(provider.enabled);
  const [makeDefault, setMakeDefault] = React.useState(provider.is_default);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    setModel(provider.model);
    setBaseUrl(provider.base_url);
    setEnabled(provider.enabled);
    setMakeDefault(provider.is_default);
  }, [provider]);

  async function save() {
    if (heuristic) return;
    setSaving(true);
    try {
      await api.put("/api/ai/providers", {
        provider: provider.provider,
        model,
        base_url: baseUrl,
        api_key: apiKey || null,
        enabled,
        is_default: makeDefault,
      });
      setApiKey("");
      toast(`${provider.label} saved`, "success");
      onSaved();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[14px] font-medium">{provider.label}</p>
            {provider.provider === "heuristic" ? (
              <Badge tone="flame">always available</Badge>
            ) : (
              <Badge tone={provider.configured ? "mint" : "neutral"}>
                {provider.configured ? "configured" : "not configured"}
              </Badge>
            )}
            {provider.is_default ? <Badge tone="ember">default</Badge> : null}
            {provider.local ? <Badge tone="neutral">local</Badge> : <Badge tone="neutral">cloud</Badge>}
          </div>
          <p className="mt-1 text-[11.5px] text-faint">
            {heuristic
              ? "Deterministic transcript analysis and copy templates. No network, no key, explainable signals."
              : provider.has_workspace_key
                ? "A workspace API key is stored (encrypted). Environment keys are used as a fallback."
                : "Uses the server environment key if present, or add a workspace key below."}
          </p>
        </div>
        {!heuristic ? (
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={onTest} loading={testing}>
              <TestTube2 className="h-3 w-3" /> Test
            </Button>
            <Button size="sm" onClick={save} loading={saving}>Save</Button>
          </div>
        ) : null}
      </div>

      {result ? (
        <div className={`mt-3 flex items-start gap-2 rounded-[var(--radius-control)] border px-3 py-2 text-[11.5px] ${
          result.ok ? "border-mint/25 bg-mint/8 text-mint" : "border-rose/25 bg-rose/8 text-rose"
        }`}>
          {result.ok ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5" /> : <TriangleAlert className="mt-0.5 h-3.5 w-3.5" />}
          <span className="leading-relaxed">{result.message}{result.latency_ms ? ` (${result.latency_ms}ms)` : ""}</span>
        </div>
      ) : null}

      {!heuristic ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Field label="Model">
            <Input value={model} onChange={(event) => setModel(event.target.value)} placeholder="model id" />
          </Field>
          <Field label="Base URL">
            <Input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://…" />
          </Field>
          <Field label="API key" hint={provider.has_workspace_key ? "Leave blank to keep the stored key." : "Stored encrypted, never returned."}>
            <div className="relative">
              <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
              <Input
                type="password"
                className="pl-9"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={provider.has_workspace_key ? "•••••••• stored" : "sk-…"}
                autoComplete="off"
              />
            </div>
          </Field>
          <div className="flex flex-col justify-end gap-2 pb-1">
            <Switch checked={enabled} onCheckedChange={setEnabled} label="Enabled" />
            <Switch checked={makeDefault} onCheckedChange={setMakeDefault} label="Use as workspace default" />
          </div>
        </div>
      ) : null}
    </Panel>
  );
}
