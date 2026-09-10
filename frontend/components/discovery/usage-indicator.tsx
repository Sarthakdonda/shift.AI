"use client";

import { useEffect, useState } from "react";
import { Activity, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { Popover } from "@/components/ui/popover";

type Usage = {
  configured_connections: number;
  available_connections: number;
  status: string;
  retry_at: string | null;
  remaining_requests: number | null;
  request_limit: number | null;
  reset_at: string | null;
  quota_note: string;
};

export function UsageIndicator({ projectId, model, busy }: { projectId: string; model: string; busy: boolean }) {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => api<Usage>(`/projects/${projectId}/usage`, { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setUsage(data); })
      .catch(() => { if (!controller.signal.aborted) setUsage(null); });
    void refresh();
    const timer = setInterval(() => { if (!document.hidden) void refresh(); }, busy ? 5000 : 30000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [projectId, model, busy]);
  useEffect(() => {
    if (!usage?.retry_at) return;
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [usage?.retry_at]);
  const seconds = usage?.retry_at ? Math.max(0, Math.ceil((Date.parse(usage.retry_at) - clock) / 1000)) : null;
  const countdown = seconds === null ? "" : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  const label = !usage ? "Usage unavailable" : usage.status === "available" ? "Usage & limits" : usage.status === "not_configured" ? "API not connected" : seconds ? `Retry in ${countdown}` : "Checking availability";
  return (
    <Popover label="Usage and limits" align="end" width={320} trigger={(props) => (
      <button {...props} type="button" className={`dx-usage-trigger ${usage?.status === "rate_limited" ? "is-limited" : ""}`} aria-label="Usage and limits">
        <Activity size={13} /><span>{label}</span>
      </button>
    )}>
      <div className="dx-usage-panel">
        <strong>Usage & limits</strong>
        <p className="dx-usage-model">{model || "Selected model"}</p>
        {usage ? <>
          <dl>
            <div><dt>Available connections</dt><dd>{usage.available_connections} / {usage.configured_connections}</dd></div>
            <div><dt>Messages remaining</dt><dd>{usage.remaining_requests ?? "Not reported"}</dd></div>
            <div><dt>Quota refill</dt><dd>{usage.reset_at ? new Date(usage.reset_at).toLocaleString() : "See AI Studio"}</dd></div>
            {seconds !== null && <div><dt>Next retry</dt><dd>{seconds ? countdown : "Ready to retry"}</dd></div>}
          </dl>
          <p>{usage.quota_note}</p>
          {seconds !== null && <p>The retry cooldown is not a guaranteed quota refill.</p>}
          <p>Backup connections keep your selected model. Keys in the same Google project share a quota.</p>
        </> : <p>Usage could not be loaded. Your provider’s dashboard has the latest limits.</p>}
        <a href="https://aistudio.google.com/usage?tab=rate-limit" target="_blank" rel="noreferrer">View provider usage <ExternalLink size={13} /></a>
      </div>
    </Popover>
  );
}
