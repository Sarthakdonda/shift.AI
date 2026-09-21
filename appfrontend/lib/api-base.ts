// A phone's localhost is the phone, so the app follows the host that served it.
// Relative production proxies and explicitly configured remote APIs stay intact.
export function resolveApiBase(configured?: string, browserHostname?: string) {
  const base = (configured || "http://localhost:8000").replace(/\/$/, "");
  if (!browserHostname || base.startsWith("/")) return base;
  const url = new URL(base);
  if (["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) {
    url.hostname = browserHostname;
  }
  return url.toString().replace(/\/$/, "");
}
