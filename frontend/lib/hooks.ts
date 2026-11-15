"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "./api";
import { useSessionStore } from "./stores";

interface UseApiOptions {
  pollMs?: number;
  enabled?: boolean;
}

export function useApi<T>(path: string | null, options: UseApiOptions = {}) {
  const { pollMs, enabled = true } = options;
  const workspaceId = useSessionStore((state) => state.activeWorkspaceId);
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(path) && enabled);
  const mounted = useRef(true);
  const pathRef = useRef(path);
  pathRef.current = path;
  const workspaceRef = useRef(workspaceId);
  workspaceRef.current = workspaceId;

  const load = useCallback(
    async (silent = false) => {
      const requestedWorkspace = workspaceRef.current;
      if (!pathRef.current || !enabled) return;
      if (!silent) setLoading(true);
      try {
        const result = await api.get<T>(pathRef.current);
        if (mounted.current && pathRef.current === path && workspaceRef.current === requestedWorkspace) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (mounted.current && pathRef.current === path) {
          setError(errorMessage(err));
        }
      } finally {
        if (mounted.current && pathRef.current === path) setLoading(false);
      }    }, [path, enabled, workspaceId],
  );

  useEffect(() => {
    mounted.current = true;
    if (!path || !enabled) {
      setLoading(false);
      return () => {
        mounted.current = false;
      };
    }
    setLoading(true);
    setData(null);
    void load(false);
    return () => {
      mounted.current = false;
    };
  }, [path, enabled, load]);

  useEffect(() => {
    if (!pollMs || !path || !enabled) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void load(true);
    }, pollMs);
    return () => window.clearInterval(timer);
  }, [pollMs, path, enabled, load]);

  return { data, error, loading, refresh: () => load(false) };
}

export function useMutation<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(
    async (...args: TArgs) => {
      setLoading(true);
      setError(null);
      try {
        return await fn(...args);
      } catch (err) {
        setError(errorMessage(err));
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [fn],
  );
  return { run, loading, error, setError };
}

export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function useObjectUrl(blobUrl: string | null) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    setUrl(blobUrl);
    return () => {
      if (blobUrl?.startsWith("blob:")) URL.revokeObjectURL(blobUrl);
    };
  }, [blobUrl]);
  return url;
}
