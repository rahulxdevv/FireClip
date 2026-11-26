export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const WORKSPACE_KEY = "fireclip.workspace";

export function getStoredWorkspace(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(WORKSPACE_KEY);
}

export function setStoredWorkspace(id: string | null) {
  if (typeof window === "undefined") return;
  if (id) window.localStorage.setItem(WORKSPACE_KEY, id);
  else window.localStorage.removeItem(WORKSPACE_KEY);
}

function readableError(status: number, payload: unknown): string {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === "object" && item && "msg" in item) {
            const field = Array.isArray((item as { loc?: unknown[] }).loc)
              ? (item as { loc: unknown[] }).loc.slice(1).join(".")
              : "";
            return `${field ? `${field}: ` : ""}${(item as { msg: string }).msg}`;
          }
          return String(item);
        })
        .join(", ");
    }
  }
  if (status === 401) return "Your session expired. Sign in again.";
  if (status === 403) return "You do not have permission for that action.";
  if (status === 404) return "Not found.";
  if (status === 429) return "Too many requests. Wait a moment.";
  if (status >= 500) return "The server hit an error. Try again.";
  return "Something went wrong.";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const workspace = getStoredWorkspace();
  if (workspace) headers.set("X-Workspace-Id", workspace);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers,
      credentials: "include",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Cannot reach the FireClip API. Is the backend running?");
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text().catch(() => "");
  if (!response.ok) {
    throw new ApiError(response.status, readableError(response.status, payload));
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: <T = void>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof Error) return error.message;
  return "Unexpected error";
}
