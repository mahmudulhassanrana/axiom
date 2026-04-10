/**
 * When unset, requests use same-origin `/api/...` (Next.js rewrites to FastAPI — no CORS).
 * Set `NEXT_PUBLIC_API_URL` only for direct cross-origin calls (e.g. separate API host).
 */
function resolveApiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (typeof raw === "string" && raw.trim() !== "") {
    return `${raw.replace(/\/$/, "")}${p}`;
  }
  return `/api${p}`;
}

function networkHint(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (typeof raw === "string" && raw.trim() !== "") {
    return `Check that the API is running and reachable at ${raw.replace(/\/$/, "")}, and that CORS allows this app origin.`;
  }
  return "Check that the FastAPI server is running (default http://127.0.0.1:8000). The dev server proxies /api to it.";
}

export const STORAGE_TOKEN_KEY = "axiom_api_token";

export function getApiToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(STORAGE_TOKEN_KEY);
}

export function setApiToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(STORAGE_TOKEN_KEY, token);
  else window.localStorage.removeItem(STORAGE_TOKEN_KEY);
}

export type ApiErrorBody = { detail?: string | unknown };

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function isPublicAuthPath(path: string): boolean {
  return path.startsWith("/auth/login") || path.startsWith("/auth/register");
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getApiToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const url = resolveApiUrl(path);
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch (e) {
    const base = e instanceof Error ? e.message : "Network error";
    throw new ApiError(`${base} — ${networkHint()}`, 0, null);
  }
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      data = text;
    }
  }
  if (res.status === 401 && typeof window !== "undefined" && !isPublicAuthPath(path)) {
    setApiToken(null);
    if (!window.location.pathname.startsWith("/login")) {
      const next = `${window.location.pathname}${window.location.search}`;
      window.location.assign(`/login?next=${encodeURIComponent(next)}`);
    }
  }
  if (!res.ok) {
    let msg = res.statusText;
    if (typeof data === "object" && data !== null) {
      const o = data as Record<string, unknown>;
      if (
        "error" in o &&
        typeof o.error === "object" &&
        o.error !== null &&
        "message" in (o.error as object)
      ) {
        const m = (o.error as { message?: unknown }).message;
        if (typeof m === "string") msg = m;
      } else if ("detail" in data) {
        const d = (data as ApiErrorBody).detail;
        if (typeof d === "string") msg = d;
        else if (typeof d === "object" && d !== null && "message" in d) {
          const inner = (d as { message?: unknown }).message;
          if (typeof inner === "string") msg = inner;
          else msg = JSON.stringify(d);
        } else msg = JSON.stringify(d);
      }
    }
    throw new ApiError(msg || "Request failed", res.status, data);
  }
  return data as T;
}
