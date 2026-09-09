"use client";

import { T } from "@/components/locale";
import Link from "next/link";
import { MicrosoftConnection } from "@/components/integrations";
import { useState, useEffect, useCallback } from "react";
import { Shell } from "@/components/layout/shell";
import { Section } from "@/components/analysis/report";
import { api, post, API_BASE } from "@/lib/api";
import type { Workspace } from "@/lib/deliverables";
import { ConfirmDialog } from "@/components/ui/feedback";
type Member = { user_id: string; name: string; role: string };
type Admin = {
  project_count: number;
  member_count: number;
  busy_projects: number;
  failed_projects: number;
  artifact_versions: number;
  default_model: string;
  usage: {
    kind: string;
    status: string;
    duration_seconds: number;
    model: string;
  }[];
  activity: { action: string; created_at: string }[];
};
type Notification = {
  id: string;
  project_id: string;
  message: string;
  read: boolean;
  created_at: string;
};
export default function Workspaces() {
  const [spaces, setSpaces] = useState<Workspace[]>([]),
    [wid, setWid] = useState(""),
    [members, setMembers] = useState<Member[]>([]),
    [admin, setAdmin] = useState<Admin | null>(null),
    [notifications, setNotifications] = useState<Notification[]>([]);
  const [name, setName] = useState(""),
    [organization, setOrganization] = useState(""),
    [role, setRole] = useState("editor"),
    [token, setToken] = useState(""),
    [invitation, setInvitation] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [remove, setRemove] = useState<Member | null>(null);
  const [model, setModel] = useState(""),
    [policy, setPolicy] = useState(""),
    [days, setDays] = useState(90);
  const selected = spaces.find((w) => w.id === wid),
    canAdmin = ["owner", "admin"].includes(selected?.access_role || "");
  const load = useCallback(async () => {
    const [w, n] = await Promise.all([
      api<Workspace[]>("/workspaces"),
      api<Notification[]>("/notifications"),
    ]);
    setSpaces(w);
    setNotifications(n);
  }, []);
  useEffect(() => {
    void load().catch((e) => setError(e.message));
  }, [load]);
  useEffect(() => {
    if (!selected) return;
    setModel(selected.model || "");
    setPolicy(selected.ai_policy || "");
    setDays(selected.retention_days || 90);
  }, [selected]);
  const loadDetails = useCallback(async () => {
    if (!wid) return;
    setMembers(await api<Member[]>(`/workspaces/${wid}/members`));
    setAdmin(canAdmin ? await api<Admin>(`/workspaces/${wid}/admin`) : null);
  }, [wid, canAdmin]);
  useEffect(() => {
    void loadDetails().catch((e) => setError(e.message));
  }, [loadDetails]);
  const perform = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
      await loadDetails();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Shell>
      <div className="page-heading">
        <h1>
          <T text={"Teams & administration"} />
        </h1>
        <p>
          <T
            text={
              "Organize shared projects, assign roles, review activity, and govern AI use."
            }
          />
        </p>
      </div>
      {error && (
        <p className="error-box" role="alert">
          {error}
        </p>
      )}
      <div className="two-columns">
        <Section title="Create a workspace">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void perform(async () => {
                const w = await post<Workspace>("/workspaces", {
                  name,
                  organization,
                });
                setWid(w.id);
                setName("");
              });
            }}
          >
            <label>
              <T text={"Workspace name"} />
              <input
                value={name}
                minLength={2}
                maxLength={100}
                required
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              <T text={"Organization"} />
              <input
                value={organization}
                maxLength={100}
                onChange={(e) => setOrganization(e.target.value)}
              />
            </label>
            <button className="button button-primary" disabled={busy}>
              <T text={"Create workspace"} />
            </button>
          </form>
        </Section>
        <Section title="Join your team">
          <p>
            <T
              text={
                "Ask a workspace administrator for a one-use invitation code. Sign in before accepting it."
              }
            />
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void perform(async () => {
                const result = await post<{ workspace_id: string }>(
                  "/invitations/accept",
                  { token },
                );
                setWid(result.workspace_id);
                setToken("");
              });
            }}
          >
            <label>
              <T text={"Invitation code"} />
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                required
                maxLength={100}
              />
            </label>
            <button className="button button-secondary" disabled={busy}>
              <T text={"Join workspace"} />
            </button>
          </form>
        </Section>
      </div>
      <label>
        <T text={"Workspace"} />
        <select
          value={wid}
          onChange={(e) => {
            setWid(e.target.value);
            setInvitation("");
            setMembers([]);
            setAdmin(null);
          }}
        >
          <option value="">Choose a workspace</option>
          {spaces.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name} · {w.access_role}
            </option>
          ))}
        </select>
      </label>
      {selected && (
        <>
          <Section title={selected.name}>
            <p>
              {selected.organization}
              <T text={" · Your role: "} />
              {selected.access_role}
            </p>
            <Link
              href={`/project/new?workspace=${wid}`}
              className="button button-primary"
            >
              <T text={"Create team project"} />
            </Link>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>
                      <T text={"Member"} />
                    </th>
                    <th>
                      <T text={"Role"} />
                    </th>
                    <th>
                      <T text={"Actions"} />
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((m) => (
                    <tr key={m.user_id}>
                      <td>{m.name}</td>
                      <td>
                        {selected.access_role === "owner" &&
                        m.role !== "owner" ? (
                          <select
                            aria-label={`Role for ${m.name}`}
                            value={m.role}
                            disabled={busy}
                            onChange={(e) =>
                              void perform(() =>
                                post(
                                  `/workspaces/${wid}/members/${encodeURIComponent(m.user_id)}`,
                                  { role: e.target.value },
                                ),
                              )
                            }
                          >
                            {["admin", "editor", "reviewer", "viewer"].map(
                              (r) => (
                                <option key={r}>{r}</option>
                              ),
                            )}
                          </select>
                        ) : (
                          m.role
                        )}
                      </td>
                      <td>
                        {selected.access_role === "owner" &&
                          m.role !== "owner" && (
                            <button
                              className="button button-ghost"
                              onClick={() => setRemove(m)}
                            >
                              <T text={"Remove"} />
                            </button>
                          )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted">
              <T
                text={
                  "Editors change content; reviewers approve it; viewers read and comment. Administrators manage policy and invitations. Only the owner changes existing roles."
                }
              />
            </p>
            {canAdmin && (
              <>
                <label>
                  <T text={"Invite with role"} />
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  >
                    {["editor", "reviewer", "viewer", "admin"].map((r) => (
                      <option key={r}>{r}</option>
                    ))}
                  </select>
                </label>
                <button
                  className="button button-secondary"
                  disabled={busy}
                  onClick={() =>
                    void perform(async () =>
                      setInvitation(
                        (
                          await post<{ token: string }>(
                            `/workspaces/${wid}/invitations`,
                            { role },
                          )
                        ).token,
                      ),
                    )
                  }
                >
                  <T text={"Create invitation code"} />
                </button>
                {invitation && (
                  <label>
                    <T text={"One-use code · expires in seven days"} />
                    <input
                      readOnly
                      value={invitation}
                      onFocus={(e) => e.target.select()}
                    />
                  </label>
                )}
              </>
            )}
          </Section>
          {admin && (
            <>
              <Section title="Workspace health">
                <div className="metric-grid">
                  {Object.entries({
                    Projects: admin.project_count,
                    Members: admin.member_count,
                    Processing: admin.busy_projects,
                    "Project errors": admin.failed_projects,
                    "Saved versions": admin.artifact_versions,
                  }).map(([k, v]) => (
                    <article key={k}>
                      <strong>{v}</strong>
                      <span>{k}</span>
                    </article>
                  ))}
                </div>
              </Section>
              <Section title="Model and security policy">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void perform(() =>
                      post(`/workspaces/${wid}/policy`, {
                        model,
                        ai_policy: policy,
                        retention_days: days,
                      }),
                    );
                  }}
                >
                  <label>
                    <T text={"Model override"} />
                    <input
                      placeholder={admin.default_model}
                      value={model}
                      maxLength={100}
                      onChange={(e) => setModel(e.target.value)}
                    />
                  </label>
                  <p className="muted">
                    <T
                      text={
                        "Leave blank to use the configured default. Availability depends on provider access."
                      }
                    />
                  </p>
                  <label>
                    <T text={"Data-retention target in days"} />
                    <input
                      type="number"
                      min={1}
                      max={3650}
                      value={days}
                      onChange={(e) => setDays(Number(e.target.value))}
                    />
                  </label>
                  <p className="muted">
                    <T
                      text={
                        "Retention is a governance target; saving it does not automatically delete project data."
                      }
                    />
                  </p>
                  <label>
                    <T text={"AI governance instructions"} />
                    <textarea
                      value={policy}
                      maxLength={4000}
                      onChange={(e) => setPolicy(e.target.value)}
                      placeholder="Allowed use, data handling, review requirements…"
                    />
                  </label>
                  <button className="button button-primary" disabled={busy}>
                    <T text={"Save policy"} />
                  </button>
                </form>
              </Section>
              <Section title="Usage and activity">
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>
                          <T text={"Deliverable"} />
                        </th>
                        <th>
                          <T text={"Model"} />
                        </th>
                        <th>
                          <T text={"Result"} />
                        </th>
                        <th>
                          <T text={"Duration"} />
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {admin.usage.map((u, i) => (
                        <tr key={i}>
                          <td>{u.kind}</td>
                          <td>{u.model}</td>
                          <td>{u.status}</td>
                          <td>{u.duration_seconds}s</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="muted">
                  <T
                    text={
                      "Operation telemetry; billing totals are not estimated from durations."
                    }
                  />
                </p>
                {admin.activity.map((a, i) => (
                  <p key={i}>
                    {new Date(a.created_at).toLocaleString()} · {a.action}
                  </p>
                ))}
              </Section>
              <MicrosoftConnection workspaceId={wid} />
              <Section title="Data portability">
                <p>
                  <T
                    text={
                      "Download project content and history. Restore creates new copies, retains historical records for download, and requires fresh discovery and approval. Existing projects are kept."
                    }
                  />
                </p>
                <a
                  className="button button-secondary"
                  href={`${API_BASE}/api/workspaces/${wid}/backup`}
                >
                  <T text={"Download backup"} />
                </a>
                <label>
                  <T text={"Restore workspace backup"} />
                  <input
                    type="file"
                    accept=".json"
                    disabled={busy}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f)
                        void perform(async () => {
                          if (f.size > 15 * 1024 * 1024)
                            throw new Error("Backup must be under 15 MB.");
                          await post(
                            `/workspaces/${wid}/restore`,
                            JSON.parse(await f.text()),
                          );
                        });
                    }}
                  />
                </label>
              </Section>
            </>
          )}
        </>
      )}
      <Section title="Notifications">
        <button
          className="button button-ghost"
          disabled={busy}
          onClick={() => void perform(() => post("/notifications/read"))}
        >
          <T text={"Mark all read"} />
        </button>
        {notifications.length ? (
          notifications.map((n) => (
            <p key={n.id}>
              <Link href={`/project/${n.project_id}/deliverables`}>
                {!n.read ? "● " : ""}
                {n.message}
              </Link>
              <small> · {new Date(n.created_at).toLocaleString()}</small>
            </p>
          ))
        ) : (
          <p>
            <T text={"No notifications yet."} />
          </p>
        )}
      </Section>
      <ConfirmDialog
        open={!!remove}
        onOpenChange={(v) => {
          if (!v) setRemove(null);
        }}
        title="Remove this member?"
        description="They will lose access to this workspace's projects."
        confirmLabel="Remove member"
        danger
        onConfirm={async () => {
          await api(
            `/workspaces/${wid}/members/${encodeURIComponent(remove!.user_id)}`,
            { method: "DELETE" },
          );
          await loadDetails();
          setRemove(null);
        }}
      />
    </Shell>
  );
}
