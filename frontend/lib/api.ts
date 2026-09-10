export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message);
  }
}
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
      signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(300000)]) : AbortSignal.timeout(300000),
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError(
      "We couldn’t connect to your workspace. Please try again in a moment.",
      0,
    );
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status >= 500 && ![
      'rate_limited', 'provider_unavailable', 'provider_error', 'gemini_configuration',
      'model_unavailable', 'database_unavailable', 'database_configuration', 'invalid_ai_output',
    ].includes(data.code)) {
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
          : "The request failed. Please try again.";
    throw new ApiError(message, response.status, data.code);
  }
  return data;
}
export function post<T>(path: string, body?: unknown, signal?: AbortSignal) {
  return api<T>(path, {
    method: "POST",
    signal,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
}
export const humanize = (s: string) =>
  s
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase());
export const date = (s: string) =>
  new Date(s).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
