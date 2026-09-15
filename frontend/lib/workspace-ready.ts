import { api, ApiError } from "./api";
import type { Health } from "./types";

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
      // A successful HTML startup page is not a ready API.
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
    "Your workspace is taking longer than usual to start. Please try signing in again in a moment.",
    503,
    "workspace_starting",
  );
}
