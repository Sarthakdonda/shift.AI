"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  BadgeCheck,
  Check,
  Copy,
  KeyRound,
  LoaderCircle,
  LogOut,
  ShieldCheck,
  Smartphone,
  UserCog,
} from "lucide-react";
import { Shell } from "@/components/layout/shell";
import { T } from "@/components/locale";
import { ConfirmDialog, useToast } from "@/components/ui/feedback";
import { ErrorBox, Loading } from "@/components/ui/states";
import { api, humanize, post } from "@/lib/api";

type Security = {
  password_account: boolean;
  mfa_enabled: boolean;
  recovery_codes_remaining: number;
  admin: boolean;
  events: { action: string; created_at: string }[];
};
type Admin = {
  users: {
    id: string;
    name: string;
    email: string;
    disabled: boolean;
    mfa: boolean | null;
  }[];
  workers: { id: string; heartbeat_at: string }[];
  jobs: {
    id: string;
    kind: string;
    status: string;
    attempts: number;
    error?: string;
  }[];
  events: {
    actor: string;
    action: string;
    target?: string;
    created_at: string;
  }[];
};

const when = (value: string) => new Date(value).toLocaleString();

export default function AccountPage() {
  const [data, setData] = useState<Security | null>(null);
  const [admin, setAdmin] = useState<Admin | null>(null);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [secret, setSecret] = useState("");
  const [codes, setCodes] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [disabling, setDisabling] = useState(false);
  const [changing, setChanging] = useState<Admin["users"][number] | null>(null);
  const toast = useToast();

  const load = useCallback(async () => {
    const state = await api<Security>("/security");
    setData(state);
    if (state.admin) setAdmin(await api<Admin>("/security/admin"));
  }, []);

  useEffect(() => {
    load()
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [load]);

  async function action(path: string, done: string) {
    setBusy(true);
    setError("");
    try {
      const result = await post<{ secret?: string; recovery_codes?: string[] }>(
        path,
        { password, code },
      );
      if (result.secret) {
        setSecret(result.secret);
      } else {
        setPassword("");
        setCode("");
        setSecret("");
      }
      if (result.recovery_codes) setCodes(result.recovery_codes);
      await load();
      toast(done);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function changeAccount(id: string, disabled: boolean) {
    setBusy(true);
    setError("");
    try {
      await post("/security/admin/account", { id, disabled });
      await load();
      toast(disabled ? "Account disabled." : "Account enabled.");
    } catch (e) {
      setError((e as Error).message);
      throw e;
    } finally {
      setBusy(false);
    }
  }

  if (loading)
    return (
      <Shell>
        <Loading label="Loading your security settings…" />
      </Shell>
    );

  return (
    <Shell>
      <div className="ac-page">
        <div className="page-heading">
          <div>
            <span className="eyebrow">
              <T text={"ACCOUNT PROTECTION"} />
            </span>
            <h1>
              <T text={"Account security"} />
            </h1>
            <p>
              <T
                text={
                  "Add a second factor, keep recovery codes somewhere private, and sign other devices out of your workspace."
                }
              />
            </p>
          </div>
          <span className="badge">
            <ShieldCheck size={12} aria-hidden />
            {data?.mfa_enabled ? "Two-factor on" : "Password only"}
          </span>
        </div>

        {error && <ErrorBox message={error} />}

        <section className="panel">
          <div className="section-toolbar" style={{ margin: "0 0 20px" }}>
            <div>
              <h2>
                <T text={"Sign-in protection"} />
              </h2>
              <p className="muted">
                <T
                  text={
                    "Confirming your password is required before any factor changes."
                  }
                />
              </p>
            </div>
            <span
              className={`badge ${data?.mfa_enabled ? "badge-green" : "badge-orange"}`}
            >
              {data?.mfa_enabled ? (
                <BadgeCheck size={12} aria-hidden />
              ) : (
                <Smartphone size={12} aria-hidden />
              )}
              {data?.mfa_enabled
                ? "Authenticator enabled"
                : "Authenticator not enabled"}
            </span>
          </div>

          {!data?.password_account ? (
            <p className="muted">
              <T
                text={
                  "This account signs in through Google or your organization provider. Manage authentication factors and session revocation there."
                }
              />
            </p>
          ) : (
            <>
              <div className="ac-status">
                <div className="ac-tile">
                  <small>
                    <Smartphone size={12} aria-hidden />
                    <T text={"Authenticator"} />
                  </small>
                  <strong>{data.mfa_enabled ? "Enabled" : "Not set up"}</strong>
                </div>
                <div className="ac-tile">
                  <small>
                    <KeyRound size={12} aria-hidden />
                    <T text={"Recovery codes"} />
                  </small>
                  <strong>
                    {data.mfa_enabled
                      ? `${data.recovery_codes_remaining} remaining`
                      : "None yet"}
                  </strong>
                </div>
                <div className="ac-tile">
                  <small>
                    <LogOut size={12} aria-hidden />
                    <T text={"Other sessions"} />
                  </small>
                  <strong>
                    <T text={"Revoke any time"} />
                  </strong>
                </div>
              </div>

              <div className="ac-form">
                <label htmlFor="security-password">
                  <T text={"Confirm your password"} />
                  <input
                    id="security-password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    maxLength={128}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <span className="field-hint">
                    <T text={"Required for every change on this page."} />
                  </span>
                </label>
                <label htmlFor="security-code">
                  <T text={"Authenticator or recovery code"} />
                  <input
                    id="security-code"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={code}
                    maxLength={64}
                    onChange={(e) => setCode(e.target.value)}
                  />
                  <span className="field-hint">
                    <T
                      text={
                        data.mfa_enabled
                          ? "Six digits from your app, or one recovery code."
                          : "Needed only after a setup key is generated."
                      }
                    />
                  </span>
                </label>
              </div>

              {secret && (
                <div className="ac-secret" role="status">
                  <p>
                    <T
                      text={
                        "Add this setup key to your authenticator app, then enter the six-digit code above to confirm. The key expires after ten minutes."
                      }
                    />
                  </p>
                  <div className="ac-secret-key">
                    <code>{secret}</code>
                    <button
                      type="button"
                      className="button button-secondary button-sm"
                      onClick={async () => {
                        await navigator.clipboard?.writeText(secret);
                        setCopied(true);
                        toast("Setup key copied.");
                      }}
                    >
                      {copied ? <Check size={14} /> : <Copy size={14} />}
                      <T text={copied ? "Copied" : "Copy key"} />
                    </button>
                  </div>
                </div>
              )}

              <div className="ac-actions">
                {!data.mfa_enabled ? (
                  <button
                    type="button"
                    className="button button-primary"
                    disabled={busy || !password || (!!secret && !code)}
                    onClick={() =>
                      void action(
                        secret ? "/security/mfa/confirm" : "/security/mfa/enroll",
                        secret
                          ? "Authenticator enabled. Save your recovery codes."
                          : "Setup key generated.",
                      )
                    }
                  >
                    {busy ? (
                      <LoaderCircle size={16} className="spin" />
                    ) : (
                      <Smartphone size={16} />
                    )}
                    <T
                      text={
                        secret ? "Confirm authenticator" : "Set up authenticator"
                      }
                    />
                  </button>
                ) : (
                  <button
                    type="button"
                    className="button button-danger"
                    disabled={busy || !password || !code}
                    onClick={() => setDisabling(true)}
                  >
                    <T text={"Disable authenticator"} />
                  </button>
                )}
                <button
                  type="button"
                  className="button button-secondary"
                  disabled={busy || !password || (data.mfa_enabled && !code)}
                  onClick={() =>
                    void action(
                      "/security/sessions/revoke",
                      "Other sessions signed out.",
                    )
                  }
                >
                  <LogOut size={16} />
                  <T text={"Sign out other sessions"} />
                </button>
              </div>

              {!!codes.length && (
                <div className="ac-codes" role="status">
                  <h3>
                    <KeyRound size={18} aria-hidden />
                    <T text={"Save your recovery codes"} />
                  </h3>
                  <p>
                    <T
                      text={
                        "These are shown once. Store them somewhere private — each code works a single time if you lose your authenticator."
                      }
                    />
                  </p>
                  <div className="ac-code-grid">
                    {codes.map((value) => (
                      <span key={value}>{value}</span>
                    ))}
                  </div>
                  <div className="ac-actions" style={{ marginTop: 0 }}>
                    <button
                      type="button"
                      className="button button-secondary button-sm"
                      onClick={async () => {
                        await navigator.clipboard?.writeText(codes.join("\n"));
                        toast("Recovery codes copied.");
                      }}
                    >
                      <Copy size={14} />
                      <T text={"Copy all codes"} />
                    </button>
                    <button
                      type="button"
                      className="button button-dark button-sm"
                      onClick={() => setCodes([])}
                    >
                      <Check size={14} />
                      <T text={"I saved these codes"} />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </section>

        {!!data?.events.length && (
          <section className="panel">
            <h2>
              <T text={"Recent security activity"} />
            </h2>
            <p className="muted" style={{ marginTop: 6, marginBottom: 12 }}>
              <T
                text={
                  "The last thirty security events recorded for this account."
                }
              />
            </p>
            <ul className="ac-activity">
              {data.events.map((event, index) => (
                <li key={`${event.action}-${event.created_at}-${index}`}>
                  <strong>
                    <Activity size={15} aria-hidden />
                    {humanize(event.action.replace(/\./g, " "))}
                  </strong>
                  <time dateTime={event.created_at}>
                    {when(event.created_at)}
                  </time>
                </li>
              ))}
            </ul>
          </section>
        )}

        {admin && (
          <>
            <section className="panel">
              <div className="section-toolbar" style={{ margin: "0 0 16px" }}>
                <div>
                  <h2>
                    <T text={"Account administration"} />
                  </h2>
                  <p className="muted">
                    <T
                      text={
                        "Disabling an account revokes its sessions immediately."
                      }
                    />
                  </p>
                </div>
                <span className="badge badge-orange">
                  <UserCog size={12} aria-hidden />
                  <T text={"Administrator"} />
                </span>
              </div>
              <div className="dx-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">
                        <T text={"Account"} />
                      </th>
                      <th scope="col">
                        <T text={"Two-factor"} />
                      </th>
                      <th scope="col">
                        <T text={"Status"} />
                      </th>
                      <th scope="col" className="ac-table-actions">
                        <T text={"Action"} />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {admin.users.map((account) => (
                      <tr key={account.id}>
                        <td>
                          <span className="ac-admin-account">
                            <strong>{account.name}</strong>
                            <small>{account.email}</small>
                          </span>
                        </td>
                        <td>
                          {account.mfa === null
                            ? "Provider managed"
                            : account.mfa
                              ? "Enabled"
                              : "Not enabled"}
                        </td>
                        <td>
                          <span
                            className={`badge ${account.disabled ? "" : "badge-green"}`}
                          >
                            {account.disabled ? "Disabled" : "Active"}
                          </span>
                        </td>
                        <td className="ac-table-actions">
                          <button
                            type="button"
                            className="button button-secondary button-sm"
                            disabled={busy}
                            onClick={() => setChanging(account)}
                          >
                            {account.disabled ? "Enable" : "Disable"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="panel">
              <h2>
                <T text={"Background workers"} />
              </h2>
              <div className="ac-status" style={{ marginTop: 16 }}>
                <div className="ac-tile">
                  <small>
                    <Activity size={12} aria-hidden />
                    <T text={"Workers reporting"} />
                  </small>
                  <strong>{admin.workers.length}</strong>
                </div>
                <div className="ac-tile">
                  <small>
                    <Activity size={12} aria-hidden />
                    <T text={"Last heartbeat"} />
                  </small>
                  <strong>
                    {admin.workers.length
                      ? when(admin.workers[0].heartbeat_at)
                      : "None recorded"}
                  </strong>
                </div>
                <div className="ac-tile">
                  <small>
                    <Activity size={12} aria-hidden />
                    <T text={"Recent jobs"} />
                  </small>
                  <strong>{admin.jobs.length}</strong>
                </div>
              </div>
              {!!admin.jobs.length && (
                <ul className="ac-activity" style={{ marginTop: 18 }}>
                  {admin.jobs.map((job) => (
                    <li key={job.id}>
                      <strong>
                        <Activity size={15} aria-hidden />
                        {`${humanize(job.kind)} · ${job.status}`}
                      </strong>
                      <time>
                        {`${job.attempts} attempt${job.attempts === 1 ? "" : "s"}${job.error ? ` · ${job.error}` : ""}`}
                      </time>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <details className="panel">
              <summary>
                <T text={"Administration audit log"} />
              </summary>
              <ul className="ac-activity">
                {admin.events.map((event, index) => (
                  <li key={`${event.action}-${event.created_at}-${index}`}>
                    <strong>
                      <Activity size={15} aria-hidden />
                      {`${humanize(event.action.replace(/\./g, " "))} · ${event.actor}${event.target ? ` → ${event.target}` : ""}`}
                    </strong>
                    <time dateTime={event.created_at}>
                      {when(event.created_at)}
                    </time>
                  </li>
                ))}
              </ul>
            </details>
          </>
        )}
      </div>

      <ConfirmDialog
        open={disabling}
        onOpenChange={setDisabling}
        title="Disable authenticator protection?"
        description="Your account will fall back to password-only sign-in and existing recovery codes stop working."
        confirmLabel="Disable authenticator"
        danger
        onConfirm={() =>
          action("/security/mfa/disable", "Authenticator disabled.")
        }
      />

      <ConfirmDialog
        open={!!changing}
        onOpenChange={(open) => !open && setChanging(null)}
        title={
          changing?.disabled ? "Enable this account?" : "Disable this account?"
        }
        description={
          changing?.disabled
            ? "The account can sign in again immediately."
            : "The account is signed out of every device and cannot sign in until it is enabled again."
        }
        confirmLabel={changing?.disabled ? "Enable account" : "Disable account"}
        danger={!changing?.disabled}
        onConfirm={async () => {
          if (changing) await changeAccount(changing.id, !changing.disabled);
          setChanging(null);
        }}
      />
    </Shell>
  );
}
