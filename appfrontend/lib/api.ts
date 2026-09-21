import { resolveApiBase } from "./api-base";

export const API_BASE = resolveApiBase(
  process.env.NEXT_PUBLIC_API_BASE_URL,
  typeof window === "undefined" ? undefined : window.location.hostname,
);

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message);
  }
}

const PROVIDER_CODES = [
  "rate_limited",
  "provider_unavailable",
  "provider_error",
  "gemini_configuration",
  "model_unavailable",
  "database_unavailable",
  "database_configuration",
  "invalid_ai_output",
];

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api${path}`, {
      ...options,
      credentials: "include",
      headers:
        options.body instanceof FormData
          ? options.headers
          : { "Content-Type": "application/json", ...options.headers },
      signal: options.signal
        ? AbortSignal.any([options.signal, AbortSignal.timeout(300000)])
        : AbortSignal.timeout(300000),
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError(
      "We couldn’t reach your workspace. Check your connection and try again.",
      0,
    );
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status >= 500 && !PROVIDER_CODES.includes(data.code)) {
      throw new ApiError(
        "Your workspace is temporarily unavailable. Please try again shortly.",
        response.status,
      );
    }
    const message =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((d: { msg: string }) => d.msg).join(". ")
          : "That request failed. Please try again.";
    throw new ApiError(message, response.status, data.code);
  }
  return data as T;
}

export function post<T>(path: string, body?: unknown, signal?: AbortSignal) {
  return api<T>(path, {
    method: "POST",
    signal,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
}

export const humanize = (value: string) =>
  value
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/^./, (character) => character.toUpperCase());

export const date = (value: string) =>
  new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

export const clock = (value: string) =>
  new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** Short "2 min ago" style label used by the chat list. */
export function relativeTime(value: string) {
  const elapsed = Date.now() - new Date(value).getTime();
  const minutes = Math.round(elapsed / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} d ago`;
  return date(value);
}
