"use client";

import { create } from "zustand";
import type { Session, User, Workspace } from "./types";
import { getStoredWorkspace, setStoredWorkspace } from "./api";

interface SessionState {
  user: User | null;
  workspaces: Workspace[];
  activeWorkspaceId: string | null;
  loaded: boolean;
  setSession: (session: Session) => void;
  setActiveWorkspace: (id: string) => void;
  clear: () => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  user: null,
  workspaces: [],
  activeWorkspaceId: null,
  loaded: false,
  setSession: (session) => {
    const stored = getStoredWorkspace();
    const valid = session.workspaces.some((workspace) => workspace.id === stored);
    const active =
      (valid ? stored : null) ||
      session.active_workspace_id ||
      session.workspaces[0]?.id ||
      null;
    setStoredWorkspace(active);
    set({ user: session.user, workspaces: session.workspaces, activeWorkspaceId: active, loaded: true });
  },
  setActiveWorkspace: (id) => {
    if (!get().workspaces.some((workspace) => workspace.id === id)) return;
    setStoredWorkspace(id);
    set({ activeWorkspaceId: id });
  },
  clear: () => {
    setStoredWorkspace(null);
    set({ user: null, workspaces: [], activeWorkspaceId: null, loaded: true });
  },
}));

export function activeWorkspace(): Workspace | null {
  const state = useSessionStore.getState();
  return state.workspaces.find((workspace) => workspace.id === state.activeWorkspaceId) || null;
}

export type ToastVariant = "success" | "error" | "info";

interface Toast {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastState {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id">) => void;
  dismiss: (id: number) => void;
}

let toastId = 0;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (toast) => {
    const id = ++toastId;
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }].slice(-4) }));
    if (typeof window !== "undefined") {
      window.setTimeout(() => {
        set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) }));
      }, 5200);
    }
  },
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })),
}));

export function toast(title: string, variant: ToastVariant = "info", description?: string) {
  useToastStore.getState().push({ title, variant, description });
}
