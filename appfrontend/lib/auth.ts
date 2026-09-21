import { api, ApiError, post } from "./api";
import type { Health, User } from "./types";

// Free hosting can return gateway errors or an HTML loading page while waking.
// Probe with GET before submitting credentials; never replay account mutations.
export async function waitForWorkspace(onWaiting?: (waiting: boolean) => void) {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    try {
      const health = await api<Health>("/health", {
        cache: "no-store",
        signal: AbortSignal.timeout(
          Math.max(1, Math.min(10_000, deadline - Date.now())),
        ),
      });
      if (health.status === "ok" && health.database === "connected") {
        onWaiting?.(false);
        return;
      }
      if (health.database) {
        throw new ApiError(
          "Your workspace database is unavailable. Please try again shortly.",
          503,
          "database_unavailable",
        );
      }
    } catch (error) {
      const retryable =
        (error instanceof ApiError &&
          !error.code &&
          [0, 502, 503, 504].includes(error.status)) ||
        (error instanceof Error && error.name === "TimeoutError");
      if (!retryable) throw error;
    }
    onWaiting?.(true);
    await new Promise((resolve) =>
      setTimeout(resolve, Math.max(0, Math.min(3000, deadline - Date.now()))),
    );
  }
  throw new ApiError(
    "Your workspace is taking longer than usual to start. Please try again in a moment.",
    503,
    "workspace_starting",
  );
}

export async function verifySession() {
  const user = await api<User>("/auth/me", {
    signal: AbortSignal.timeout(15000),
  });
  if (!user?.id || user.local)
    throw new Error("We couldn’t verify your sign-in. Please try again.");
  return user;
}

export async function signInWithEmail(
  email: string,
  password: string,
  onWaiting?: (waiting: boolean) => void,
) {
  await waitForWorkspace(onWaiting);
  await post("/auth/login", { email, password });
  return verifySession();
}

export async function signUpWithEmail(
  name: string,
  email: string,
  password: string,
  onWaiting?: (waiting: boolean) => void,
) {
  await waitForWorkspace(onWaiting);
  await post("/auth/signup", { name, email, password });
  return verifySession();
}

export type ResetRequest = {
  ok: boolean;
  message: string;
  delivery: "email" | "local_link" | "none";
  reset_link?: string;
  expires_in_minutes?: number;
};

export function requestPasswordReset(email: string) {
  return post<ResetRequest>("/auth/password/forgot", { email });
}

export function checkResetToken(token: string) {
  return post<{ ok: boolean }>("/auth/password/verify", { token });
}

export function completePasswordReset(token: string, password: string) {
  return post<{ ok: boolean; email: string }>("/auth/password/reset", {
    token,
    password,
  });
}
