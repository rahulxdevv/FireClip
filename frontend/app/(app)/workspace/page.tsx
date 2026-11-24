"use client";

import * as React from "react";
import { KeyRound, Mail, Plus, ShieldCheck, Trash2, UserPlus } from "lucide-react";
import { PageHeader } from "@/components/shared";
import {
  Alert,
  Badge,
  Button,
  Dialog,
  Field,
  Input,
  PageSkeleton,
  Panel,
  PanelHeader,
  Select,
} from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { api, errorMessage } from "@/lib/api";
import { toast, useSessionStore } from "@/lib/stores";
import { formatDateTime, relativeTime } from "@/lib/format";
import type { Activity, ApiKeyItem, Member, WorkspaceInvite } from "@/lib/types";

export default function WorkspacePage() {
  const workspace = useSessionStore((state) =>
    state.workspaces.find((item) => item.id === state.activeWorkspaceId),
  );
  const setSession = useSessionStore((state) => state.setSession);
  const [name, setName] = React.useState(workspace?.name || "");
  const [savingName, setSavingName] = React.useState(false);
  const [addOpen, setAddOpen] = React.useState(false);
  const [addForm, setAddForm] = React.useState({ email: "", role: "editor" });
  const [adding, setAdding] = React.useState(false);
  const [keyOpen, setKeyOpen] = React.useState(false);
  const [keyName, setKeyName] = React.useState("Automation");
  const [createdKey, setCreatedKey] = React.useState<string | null>(null);
  const [creatingKey, setCreatingKey] = React.useState(false);
  const [busy, setBusy] = React.useState<string | null>(null);

  const members = useApi<Member[]>(workspace ? `/api/workspaces/${workspace.id}/members` : null);
  const keys = useApi<ApiKeyItem[]>("/api/api-keys");
  const audit = useApi<Activity[]>("/api/audit-logs?limit=50");
  const isAdmin = workspace?.role === "owner" || workspace?.role === "admin";
  const invites = useApi<WorkspaceInvite[]>(workspace && isAdmin ? `/api/workspaces/${workspace.id}/invites` : null);

  React.useEffect(() => setName(workspace?.name || ""), [workspace?.name]);

  async function saveName(event: React.FormEvent) {
    event.preventDefault();
    if (!workspace || !name.trim() || name === workspace.name) return;
    setSavingName(true);
    try {
      await api.patch(`/api/workspaces/${workspace.id}`, { name: name.trim() });
      const session = await api.get<Parameters<typeof setSession>[0]>("/api/auth/me");
      setSession(session);
      toast("Workspace renamed", "success");
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setSavingName(false);
    }
  }

  async function addMember(event: React.FormEvent) {
    event.preventDefault();
    if (!workspace) return;
    setAdding(true);
    try {
      const result = await api.post<{ status: string }>(
        `/api/workspaces/${workspace.id}/members`,
        addForm,
      );
      toast(result.status === "invited" ? "Invitation sent" : "Member added", "success");
      setAddOpen(false);
      setAddForm({ email: "", role: "editor" });
      members.refresh();
      invites.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setAdding(false);
    }
  }

  async function changeRole(member: Member, role: string) {
    if (!workspace) return;
    setBusy(member.id);
    try {
      await api.patch(`/api/workspaces/${workspace.id}/members/${member.id}`, {
        email: member.email,
        role,
      });
      members.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function removeMember(member: Member) {
    if (!workspace || !window.confirm(`Remove ${member.email} from this workspace?`)) return;
    setBusy(member.id);
    try {
      await api.delete(`/api/workspaces/${workspace.id}/members/${member.id}`);
      members.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function revokeInvite(invite: WorkspaceInvite) {
    if (!workspace || !window.confirm(`Revoke the invitation for ${invite.email}?`)) return;
    setBusy(invite.id);
    try {
      await api.delete(`/api/workspaces/${workspace.id}/invites/${invite.id}`);
      toast("Invitation revoked", "success");
      invites.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function createKey(event: React.FormEvent) {
    event.preventDefault();
    setCreatingKey(true);
    try {
      const result = await api.post<ApiKeyItem & { key: string }>("/api/api-keys", { name: keyName });
      setCreatedKey(result.key);
      keys.refresh();
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setCreatingKey(false);
    }
  }

  async function revokeKey(key: ApiKeyItem) {
    if (!window.confirm(`Revoke API key “${key.name}”? Clients using it will fail immediately.`)) return;
    setBusy(key.id);
    try {
      await api.delete(`/api/api-keys/${key.id}`);
      keys.refresh();
      toast("Key revoked", "success");
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  if (!workspace) return <PageSkeleton />;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Settings"
        title="Workspace"
        description={`${workspace.name} · ${workspace.plan} plan · ${workspace.member_count} members`}
        actions={
          <Badge tone="flame">{workspace.role}</Badge>
        }
      />

      <div className="grid gap-5">
        <Panel>
          <PanelHeader title="Workspace details" description="The name appears in the switcher and audit logs." />
          <form onSubmit={saveName} className="flex flex-wrap items-end gap-3 p-5">
            <Field label="Name" className="min-w-[260px] flex-1">
              <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} disabled={!isAdmin} />
            </Field>
            <Button type="submit" loading={savingName} disabled={!isAdmin || name === workspace.name}>
              Save
            </Button>
          </form>
          <div className="grid gap-3 border-t border-white/7 px-5 py-4 text-[11.5px] sm:grid-cols-3">
            <div><p className="text-faint">Slug</p><p className="mt-0.5 font-mono text-muted">{workspace.slug}</p></div>
            <div><p className="text-faint">Created</p><p className="mt-0.5 text-muted">{formatDateTime(workspace.created_at)}</p></div>
            <div><p className="text-faint">Clip allowance</p><p className="mt-0.5 text-muted">{workspace.monthly_clip_limit} / month</p></div>
          </div>
        </Panel>

        <Panel>
          <PanelHeader
            title="Members"
            description="Roles: owner, admin, editor (can change content), viewer (read-only)."
            action={
              <Button size="sm" variant="outline" disabled={!isAdmin} onClick={() => setAddOpen(true)}>
                <UserPlus className="h-3.5 w-3.5" /> Add member
              </Button>
            }
          />
          {members.error ? <Alert className="m-4">{members.error}</Alert> : null}
          {members.loading && !members.data ? (
            <div className="p-4"><PageSkeleton /></div>
          ) : (
            <div className="divide-y divide-white/6">
              {(members.data || []).map((member) => (
                <div key={member.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-flame-500/12 font-mono text-[11px] text-flame-400">
                    {(member.name || member.email).slice(0, 2).toUpperCase()}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12.5px] text-paper">{member.name || member.email}</p>
                    <p className="truncate font-mono text-[10px] text-faint">{member.email} · joined {relativeTime(member.created_at)}</p>
                  </div>
                  {member.role === "owner" ? (
                    <Badge tone="flame">owner</Badge>
                  ) : (
                    <Select
                      value={member.role}
                      onChange={(event) => changeRole(member, event.target.value)}
                      className="w-[120px]"
                      disabled={!isAdmin || busy === member.id}
                    >
                      <option value="admin">admin</option>
                      <option value="editor">editor</option>
                      <option value="viewer">viewer</option>
                    </Select>
                  )}
                  {member.role !== "owner" && isAdmin ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={busy === member.id}
                      onClick={() => removeMember(member)}
                      aria-label="Remove member"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </Panel>

        {isAdmin ? (
          <Panel>
            <PanelHeader
              title="Pending invitations"
              description="Single-use links for people who do not have an account yet."
              action={<Mail className="h-4 w-4 text-faint" />}
            />
            {(invites.data || []).length === 0 ? (
              <p className="px-5 py-5 text-[12px] text-faint">No pending invitations.</p>
            ) : (
              <div className="divide-y divide-white/6">
                {(invites.data || []).map((invite) => (
                  <div key={invite.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                    <Mail className="h-4 w-4 text-faint" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12.5px] text-paper">{invite.email}</p>
                      <p className="font-mono text-[10px] text-faint">
                        {invite.role} · expires {relativeTime(invite.expires_at)}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={busy === invite.id}
                      onClick={() => revokeInvite(invite)}
                    >
                      Revoke
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        ) : null}

        <Panel>
          <PanelHeader
            title="API keys"
            description="Scoped to your user and this workspace. The full key is shown once."
            action={
              <Button size="sm" variant="outline" onClick={() => { setCreatedKey(null); setKeyOpen(true); }}>
                <Plus className="h-3.5 w-3.5" /> Create key
              </Button>
            }
          />
          {(keys.data || []).length === 0 ? (
            <p className="px-5 py-6 text-[12px] text-faint">No API keys yet.</p>
          ) : (
            <div className="divide-y divide-white/6">
              {(keys.data || []).map((key) => (
                <div key={key.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                  <KeyRound className="h-4 w-4 text-faint" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] text-paper">{key.name}</p>
                    <p className="font-mono text-[10px] text-faint">
                      fk_{key.prefix}_… · created {relativeTime(key.created_at)} · last used {key.last_used_at ? relativeTime(key.last_used_at) : "never"}
                    </p>
                  </div>
                  {key.revoked_at ? (
                    <Badge tone="rose">revoked</Badge>
                  ) : (
                    <Button size="sm" variant="ghost" loading={busy === key.id} onClick={() => revokeKey(key)}>
                      Revoke
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
          <div className="border-t border-white/7 px-5 py-3">
            <p className="text-[10.5px] leading-relaxed text-faint">
              Authenticate with <code className="font-mono text-muted">X-API-Key: fk_…</code>. Keys are stored as
              SHA-256 hashes and are scoped to this workspace.
            </p>
          </div>
        </Panel>

        <Panel>
          <PanelHeader
            title="Audit log"
            description="Security-relevant actions. Admin access only."
            action={<ShieldCheck className="h-4 w-4 text-faint" />}
          />
          {audit.error ? (
            <p className="px-5 py-6 text-[12px] text-faint">{audit.error}</p>
          ) : (audit.data || []).length === 0 ? (
            <p className="px-5 py-6 text-[12px] text-faint">No audit entries visible.</p>
          ) : (
            <div className="max-h-80 divide-y divide-white/6 overflow-y-auto">
              {(audit.data || []).map((entry) => (
                <div key={entry.id} className="flex flex-wrap items-center gap-2 px-5 py-2.5">
                  <span className="min-w-0 flex-1 text-[11.5px] text-muted">
                    <span className="text-paper">{entry.user_email?.split("@")[0] || "system"}</span>{" "}
                    {entry.action.replace(/\./g, " ")}
                  </span>
                  <span className="font-mono text-[9.5px] text-faint">{relativeTime(entry.created_at)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Dialog
        open={addOpen}
        onOpenChange={setAddOpen}
        title="Add a member"
        description="Existing accounts join immediately. New addresses receive a single-use invitation email."
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button onClick={addMember} loading={adding}>Add member</Button>
          </>
        }
      >
        <form onSubmit={addMember} className="space-y-4">
          <Field label="Email">
            <Input type="email" required value={addForm.email} onChange={(event) => setAddForm({ ...addForm, email: event.target.value })} />
          </Field>
          <Field label="Role">
            <Select value={addForm.role} onChange={(event) => setAddForm({ ...addForm, role: event.target.value })}>
              <option value="editor">Editor - full content access</option>
              <option value="admin">Admin - manage members and settings</option>
              <option value="viewer">Viewer - read only</option>
            </Select>
          </Field>
        </form>
      </Dialog>

      <Dialog
        open={keyOpen}
        onOpenChange={setKeyOpen}
        title={createdKey ? "Copy your API key" : "Create an API key"}
        description={createdKey ? "This is the only time the full key is shown." : "The key inherits your permissions in this workspace."}
        footer={
          createdKey ? (
            <Button onClick={() => setKeyOpen(false)}>Done</Button>
          ) : (
            <>
              <Button variant="ghost" onClick={() => setKeyOpen(false)}>Cancel</Button>
              <Button onClick={createKey} loading={creatingKey}>Create key</Button>
            </>
          )
        }
      >
        {createdKey ? (
          <div className="space-y-3">
            <div className="break-all rounded-lg border border-flame-500/30 bg-ink-850 p-3 font-mono text-[12px] text-flame-400">
              {createdKey}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                await navigator.clipboard.writeText(createdKey);
                toast("Copied", "success");
              }}
            >
              Copy key
            </Button>
          </div>
        ) : (
          <Field label="Key name">
            <Input value={keyName} onChange={(event) => setKeyName(event.target.value)} maxLength={80} />
          </Field>
        )}
      </Dialog>
    </div>
  );
}
