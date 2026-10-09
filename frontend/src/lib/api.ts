import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useApp } from "@/store/app";

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; form?: FormData; params?: Record<string, string | number | boolean | undefined>; facility?: boolean } = {}): Promise<T> {
  const { token, facility, logout } = useApp.getState();
  const q = new URLSearchParams();
  if (opts.facility !== false) q.set("facility", facility);
  Object.entries(opts.params ?? {}).forEach(([k, v]) => v !== undefined && q.set(k, String(v)));
  const res = await fetch(`/api/v1${path}?${q}`, {
    method: opts.method ?? "GET",
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(opts.body ? { "Content-Type": "application/json" } : {}) },
    body: opts.form ?? (opts.body ? JSON.stringify(opts.body) : undefined),
  });
  if (res.status === 401 && path !== "/auth/login") { logout(); throw new ApiError(401, "Session expired, please sign in again"); }
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail ?? j.error?.message ?? msg; if (typeof msg !== "string") msg = JSON.stringify(msg); } catch { /* keep status text */ }
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

/** GET query keyed by facility, so switching facility refetches everything. */
export function useQ<T = any>(path: string, params?: Record<string, string | number | boolean | undefined>, enabled = true) {
  const facility = useApp((s) => s.facility);
  return useQuery<T, ApiError>({ queryKey: [path, facility, params], queryFn: () => api<T>(path, { params }), enabled, staleTime: 15_000, retry: 1 });
}

export function useAct<TIn = any, TOut = any>(fn: (v: TIn) => Promise<TOut>, invalidate: string[] = []) {
  const qc = useQueryClient();
  return useMutation<TOut, ApiError, TIn>({ mutationFn: fn, onSuccess: () => invalidate.forEach((k) => qc.invalidateQueries({ queryKey: [k] })) });
}
