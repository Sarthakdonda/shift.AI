"use client";

import { T } from "@/components/locale";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api";
import { Section } from "@/components/analysis/report";
import { ConfirmDialog } from "@/components/ui/feedback";

export function MicrosoftConnection({ workspaceId }: { workspaceId: string }) {
  const [connection, setConnection] = useState<{
    connected: boolean;
    label: string;
  } | null>(null);
  const [token, setToken] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [disconnect, setDisconnect] = useState(false);
  const load = useCallback(async () => {
    const result = await api<{
      microsoft_graph: { connected: boolean; label: string };
    }>(`/workspaces/${workspaceId}/integrations`);
    setConnection(result.microsoft_graph);
  }, [workspaceId]);
  useEffect(() => {
    setConnection(null);
    setToken("");
    void load().catch((e) => setError(e.message));
  }, [load]);
  return (
    <Section title="Microsoft Planner connection">
      <p>
        <T
          text={
            "Import your assigned Planner tasks into a team project as discovery evidence."
          }
        />
      </p>
      {error && (
        <p role="alert" className="error-box">
          {error}
        </p>
      )}
      {connection?.connected ? (
        <>
          <p>
            <T text={"Connected: "} />
            {connection.label}
          </p>
          <button
            className="button button-secondary"
            onClick={() => setDisconnect(true)}
          >
            <T text={"Disconnect Microsoft"} />
          </button>
        </>
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await post(
                `/workspaces/${workspaceId}/integrations/microsoft_graph`,
                { access_token: token },
              );
              setToken("");
              await load();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            <T text={"Microsoft Graph delegated access token"} />
            <input
              type="password"
              value={token}
              autoComplete="off"
              required
              minLength={20}
              maxLength={12000}
              onChange={(e) => setToken(e.target.value)}
            />
          </label>
          <p className="muted">
            <T
              text={
                "Use a token from your organization with User.Read and Tasks.Read. The connection is encrypted on the server. Reconnect when the token expires."
              }
            />
          </p>
          <button
            className="button button-primary"
            disabled={busy || !connection}
          >
            {busy ? "Connecting…" : "Connect Microsoft"}
          </button>
        </form>
      )}
      <ConfirmDialog
        open={disconnect}
        onOpenChange={setDisconnect}
        title="Disconnect Microsoft?"
        description="Future imports will stop until you reconnect. Previously imported evidence stays in its project."
        confirmLabel="Disconnect"
        onConfirm={async () => {
          await api(`/workspaces/${workspaceId}/integrations/microsoft_graph`, {
            method: "DELETE",
          });
          await load();
          setDisconnect(false);
        }}
      />
    </Section>
  );
}

export function ImportPlanner({
  projectId,
  onImported,
}: {
  projectId: string;
  onImported: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="button button-secondary" onClick={() => setOpen(true)}>
        <T text={"Import Planner evidence"} />
      </button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Import assigned Planner tasks?"
        description="This reads the first page of your assigned tasks, up to 100, through the team's Microsoft connection. The snapshot is sent to your configured AI provider for discovery, so existing analysis becomes out of date."
        confirmLabel="Import snapshot"
        onConfirm={async () => {
          await post(
            `/projects/${projectId}/integrations/microsoft_graph/import`,
          );
          await onImported();
          setOpen(false);
        }}
      />
    </>
  );
}
