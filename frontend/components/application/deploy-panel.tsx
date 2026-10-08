"use client";
import { useCallback, useEffect, useState } from "react";
import { api, post, ApiError, API_BASE, humanize } from "@/lib/api";
import styles from "./builder.module.css";

type Stage = { key: string; label: string; status: "pending" | "running" | "done" | "failed"; detail?: string };
export type Launch = {
  id: string; build_id: string; status: string; stage: string; attempt: number; created_at: string; finished_at?: string;
  error?: { stage: string; code: string; message: string }; stages: Stage[]; logs: string[];
  frontend_url?: string; backend_url?: string; repository?: string; repository_url?: string; commit?: string;
  verification?: { checks: string[]; module: string };
  prototype?: boolean; manual_requirements?: { id: string; description: string }[];
};
export type DeployState = {
  missing: string[]; can_deploy: boolean; stages: { key: string; label: string }[]; launches: Launch[];
  github: { connected: boolean; login: string; oauth: boolean; owner: string };
  site?: { name: string; repository?: { html_url: string }; live?: { frontend_url: string; build_id: string; at: string } } | null;
};
type Credentials = { email: string; password: string };

const ACTIVE = ["queued", "running"];
const ICON = { done: "✓", running: "…", failed: "✕", pending: "·" } as const;

export function DeployPanel({ projectId, buildId, deployable, reason, manualRequirements = [] }: { projectId: string; buildId?: string; deployable: boolean; reason?: string; manualRequirements?: { id: string; description: string }[] }) {
  const base = `/projects/${projectId}/deploy`;
  const [state, setState] = useState<DeployState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [credentials, setCredentials] = useState<Credentials | null>(null);
  const current = state?.launches[0];
  const running = !!current && ACTIVE.includes(current.status);

  const load = useCallback(async () => {
    try {
      setState(await api<DeployState>(base));
    } catch (failure) {
      setError((failure as Error).message);
    }
  }, [base]);

  useEffect(() => { load().catch(() => {}); }, [load]);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => { load().catch(() => {}); }, 4000);
    return () => clearInterval(timer);
  }, [running, load]);

  useEffect(() => {
    // The GitHub callback returns here; show the outcome, then clean the URL.
    const params = new URLSearchParams(window.location.search);
    const outcome = params.get("github");
    if (!outcome) return;
    if (outcome === "failed") setError("GitHub authorization did not complete. Choose Connect GitHub to try again.");
    window.history.replaceState({}, "", window.location.pathname);
  }, []);

  const act = async (label: string, operation: () => Promise<unknown>) => {
    setBusy(label); setError("");
    try { await operation(); await load(); } catch (failure) {
      const problem = failure as ApiError;
      setError(problem.message + (problem.code === "github_authorization" ? " Choose Connect GitHub below." : ""));
    } finally { setBusy(""); }
  };

  const connect = () => act("Opening GitHub", async () => {
    const { url } = await api<{ url: string }>(`/deploy/github/connect?project_id=${projectId}`);
    window.location.href = url;
  });

  if (!state) return <section className={styles.panel} aria-busy="true"><h2>Deploy your application</h2><p>Loading deployment status…</p></section>;

  const stages: Stage[] = current?.stages ?? state.stages.map(stage => ({ ...stage, status: "pending" as const }));
  const live = state.site?.live;
  const prototype = manualRequirements.length > 0;
  const disabled = !!busy || running || !state.can_deploy || !deployable || state.missing.length > 0;

  return (
    <section className={styles.panel} aria-label="One-click deployment">
      <div className={styles.row}><h2>Deploy your application</h2>
        {live && <a href={live.frontend_url} target="_blank" rel="noreferrer">Open live application ↗</a>}</div>
      <p>One click provisions this application&apos;s own MongoDB database, a private GitHub repository, its Render backend
        and its Vercel frontend, then verifies the live site before reporting success.</p>

      {error && <p className={styles.error} role="alert">{error}</p>}
      {!!state.missing.length && <p className={styles.error}>Deployment setup is incomplete. Add {state.missing.join(", ")} to the backend environment and restart it.</p>}
      {!state.can_deploy && <p className={styles.status}>Only the project owner or an administrator can deploy.</p>}
      {state.can_deploy && !deployable && <p className={styles.status}>{reason || "Generate and validate a build before deploying."}</p>}
      {deployable && prototype && <div>
        <p className={styles.status}>Your prototype passed build validation and is ready to deploy. {manualRequirements.length} blueprint requirements remain unimplemented; deployment will publish the working prototype only.</p>
        <details><summary>Features outside this prototype ({manualRequirements.length})</summary>
          <ul>{manualRequirements.map(item => <li key={item.id}>{item.description}</li>)}</ul>
        </details>
      </div>}

      <p className={styles.status}>GitHub: {state.github.connected
        ? `connected as ${state.github.login}`
        : state.github.oauth ? `not connected${state.github.owner ? ` (repositories are created under ${state.github.owner})` : ""}` : "sign-in is not configured on this server"}</p>

      <div className={styles.actions}>
        <button type="button" disabled={disabled} onClick={() => act("Starting deployment", () => post(base, { build_id: buildId, prototype }))}>
          {busy === "Starting deployment" ? "Starting…" : running ? "Deployment running…" : prototype ? "Deploy prototype" : live ? "Deploy this version" : "Deploy"}
        </button>
        {state.can_deploy && state.github.oauth && !state.github.connected &&
          <button type="button" disabled={!!busy} onClick={connect}>Connect GitHub</button>}
        {current?.status === "failed" && state.can_deploy &&
          <button type="button" disabled={!!busy} onClick={() => act("Retrying", () => post(`${base}/${current.id}/retry`))}>
            {busy === "Retrying" ? "Retrying…" : "Retry from the failed step"}
          </button>}
        {live && state.can_deploy && !credentials &&
          <button type="button" disabled={!!busy} onClick={() => act("Loading sign-in", async () => setCredentials(await post<Credentials>(`${base}/credentials`)))}>
            Show administrator sign-in
          </button>}
      </div>

      {credentials && <p className={styles.caption}>Administrator sign-in for the deployed application: <strong>{credentials.email}</strong> / <code>{credentials.password}</code>. Store it in your password manager; change it inside the application.</p>}

      {current && <>
        <div className={styles.progress} role="status" aria-live="polite">
          {stages.map(stage => <span key={stage.key} className={stage.status === "running" ? styles.current : undefined}>
            {ICON[stage.status]} {stage.label}
          </span>)}
        </div>
        {current.status === "live" && <p>Deployment successful. {current.verification && `Verified: ${current.verification.checks.join(", ")}.`}</p>}
        {current.prototype && !!current.manual_requirements?.length && <p>This deployment contains the prototype scope. {current.manual_requirements.length} requirements remain unimplemented.</p>}
        {current.error && <p className={styles.error} role="alert">
          {stages.find(stage => stage.key === current.error?.stage)?.label || humanize(current.error.stage)}: {current.error.message}
        </p>}
        <ul>
          {current.frontend_url && <li>Frontend: <a href={current.frontend_url} target="_blank" rel="noreferrer">{current.frontend_url}</a></li>}
          {current.backend_url && <li>Backend: <a href={current.backend_url} target="_blank" rel="noreferrer">{current.backend_url}</a></li>}
          {current.repository_url && <li>Repository: <a href={current.repository_url} target="_blank" rel="noreferrer">{current.repository}</a>{current.commit && ` at ${current.commit.slice(0, 7)}`}</li>}
        </ul>
        <details><summary>Deployment steps and log</summary>
          <ul>{stages.filter(stage => stage.detail).map(stage => <li key={stage.key}>{stage.label}: {stage.detail}</li>)}</ul>
          <pre>{current.logs.join("\n")}</pre>
        </details>
      </>}

      {state.launches.length > 1 && <details><summary>Earlier deployments ({state.launches.length - 1})</summary>
        <ul>{state.launches.slice(1).map(item => <li key={item.id}>
          {new Date(item.created_at).toLocaleString()} · {humanize(item.status)}
          {item.attempt > 1 && ` · ${item.attempt} attempts`}
          {item.error && ` · ${item.error.message}`}
        </li>)}</ul>
      </details>}

      <p className={styles.caption}>The database URI and provider keys stay on the shift.AI server. The generated frontend
        reaches its backend through a same-origin gateway, so no credential is exposed to the browser. Free hosting plans
        sleep when idle, so the first request after a pause can take a few seconds. API base: {API_BASE}</p>
    </section>
  );
}
