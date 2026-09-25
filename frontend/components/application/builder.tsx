"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, post, API_BASE } from "@/lib/api";
import styles from "./builder.module.css";

type Spec = {
  name: string; description: string; language: string; accent: string; roles: string[];
  entities: { name: string; label: string; fields: { name: string; label: string; kind: string; required: boolean; reference?: string }[]; read_roles: string[]; write_roles: string[]; transitions: { label: string; from_value: string; to_value: string }[]; requirement_ids: string[] }[];
  requirements: { id: string; description: string; evidence: string; implementation: string }[];
  assumptions: string[]; limitations: string[]; change_summary: string;
};
type Version = { id: string; version: number; blueprint_version: number; spec: Spec; approval?: { actor: string; created_at: string }; created_at: string; migration_issues?: string[]; ai_reviews?: { findings: { issue: string; reason: string; mitigation: string; severity: string; requires_revision: boolean }[] }[]; changes?: { added: string[]; removed: string[]; modified: string[] } };
type Build = { id: string; spec_version: number; status: string; created_at: string; logs: string[]; error?: string; validation?: { status: string; error?: string; checks: string[]; logs?: string[] }; manifest?: Record<string, string>; findings?: { issue: string; severity: string; status: string }[] };
type Deployment = { id: string; target?: string; build_id: string; status: string; provider_status?: string; live_url?: string; error?: string; logs: string[]; created_at: string };
type Overview = { specs: Version[]; builds: Build[]; deployments: Deployment[]; role: string; busy: boolean; stale: boolean; deployment_configured: boolean; vercel_configured: boolean; platform_admin: boolean; preview?: { url: string; expires_at: string }; build_cost: number; job?: { status: string; error?: string } };
type Billing = { plan: { name: string; initial_credits: number }; account: { balance: number; entries: { key: string; amount: number; status: string; created_at: string }[] }; policy: string; payments_enabled: boolean };
type Preview = { url: string; email: string; password: string; expires_in_seconds: number };
const readable = (value: string) => value.replaceAll("_", " ");

export function ApplicationBuilder({ projectId }: { projectId: string }) {
  const base = `/projects/${projectId}/application`;
  const [data, setData] = useState<Overview | null>(null);
  const [billing, setBilling] = useState<Billing | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState("");
  const [instructions, setInstructions] = useState("");
  const [selected, setSelected] = useState(0);
  const [draft, setDraft] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const buildRequest = useRef<{ version: number; id: string } | null>(null);
  const load = useCallback(async () => {
    const [overview, balance] = await Promise.all([api<Overview>(base), api<Billing>("/billing")]);
    setData(overview); setBilling(balance);
  }, [base]);
  useEffect(() => { load().catch(e => setError(e.message)); }, [load]);
  useEffect(() => {
    if (!data?.busy && !data?.preview && !data?.deployments.some(d => ["deploying", "health_pending"].includes(d.status))) return;
    const timer = setInterval(async () => { try { for (const item of data.deployments.filter(d => ["deploying", "health_pending"].includes(d.status))) await post(`${base}/deployments/${item.id}/refresh`); await load(); } catch (error) { setError((error as Error).message); } }, 6000);
    return () => clearInterval(timer);
  }, [data, base, load]);
  const latest = data?.specs[0];
  const version = data?.specs.find(v => v.version === selected) || latest;
  const canWrite = !!data && ["owner", "admin", "editor"].includes(data.role);
  const canApprove = !!data && ["owner", "admin", "reviewer"].includes(data.role);
  const canDeploy = !!data && ["owner", "admin"].includes(data.role);
  const busy = !!working || !!data?.busy;
  async function act(name: string, fn: () => Promise<unknown>) {
    setWorking(name); setError("");
    try { await fn(); await load(); } catch (e) { setError((e as Error).message); } finally { setWorking(""); }
  }
  async function generate(version: number) {
    if (buildRequest.current?.version !== version) buildRequest.current = { version, id: crypto.randomUUID() };
    await post(`${base}/build`, { version, request_id: buildRequest.current.id, quoted_cost: data?.build_cost });
    buildRequest.current = null;
  }
  async function download(build: Build) {
    const response = await fetch(`${API_BASE}/api${base}/builds/${build.id}/download`, { credentials: "include" });
    if (!response.ok) throw new Error("Application download failed. Try again.");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a"); link.href = url; link.download = `application-${build.id}.zip`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <div className={styles.builder}>
    <header className={styles.hero}><p className={styles.eyebrow}>FROM BLUEPRINT TO BUSINESS SOFTWARE</p><h1>Application studio</h1><p>Review what will be built, approve a version, then generate, validate and publish your application.</p>
      <div className={styles.steps}><span>1 · Blueprint</span><span>2 · Approve scope</span><span>3 · Build & test</span><span>4 · Deploy</span></div>
    </header>
    {error && <div className={styles.error} role="alert">{error}</div>}
    {!data && !error && <p role="status">Loading your application workspace…</p>}
    {data && <>
      <div className={styles.grid}>
        <section className={styles.panel}><h2>{latest ? "Request a change" : "Prepare your application"}</h2><p>{latest ? "Describe changes to features, fields, workflows or visual style. Each change creates a draft for review." : "Complete your project blueprint first. The AI will map its requirements into an editable application specification."}</p>
          <label htmlFor="application-instructions">Application requirements or changes</label><textarea id="application-instructions" rows={4} maxLength={6000} value={instructions} onChange={e => setInstructions(e.target.value)} placeholder="For example: add candidate profiles and interview scheduling, with separate recruiter and manager roles." />
          <button disabled={!canWrite || busy} onClick={() => act("Planning", async () => { await post(`${base}/plan`, { instructions, base_version: latest?.version || 0 }); setSelected(0); setDraft(""); setConfirmed(false); })}>{busy ? working || "Processing…" : latest ? "Draft changes" : "Create application specification"}</button>
          {data.job?.error && <p role="alert" className={styles.error}>{data.job.error}</p>}
        </section>
        <section className={styles.panel}><h2>Credits & deployment</h2><p className={styles.balance}>{billing?.account.balance ?? "—"} <small>credits available</small></p><p>{data.build_cost} credits per validated build. Credits are reserved once and refunded if generation or validation fails.</p>{billing && <p>{billing.plan.name} plan · {billing.plan.initial_credits} starting credits. {!billing.payments_enabled && "Payment checkout is not enabled."}</p>}<p className={styles.status}>{data.deployment_configured ? "Render target configured" : "Render setup required"}</p><p>Preview requires Docker on this computer. Deployment requires a registry, a Render service, and a persistent database disk.</p>
          <details><summary>Credit history</summary>{billing?.account.entries.length ? billing.account.entries.slice().reverse().slice(0,20).map(entry => <p key={entry.key}>{readable(entry.status)} · {entry.status === "refunded" ? "0 net" : entry.amount} credits · {new Date(entry.created_at).toLocaleString()}</p>) : <p>No generation charges yet.</p>}</details>
        </section>
      </div>
      {version && <section className={styles.panel}>
        <div className={styles.row}><div><p className={styles.eyebrow}>BLUEPRINT V{version.blueprint_version}</p><h2>{version.spec.name}</h2></div><label>Application version<select value={version.version} onChange={e => { setSelected(Number(e.target.value)); setDraft(""); setConfirmed(false); }}>{data.specs.map(v => <option value={v.version} key={v.id}>Version {v.version} · {v.approval ? "Approved" : "Draft"}</option>)}</select></label></div>
        <p>{version.spec.description}</p><p><strong>Changes:</strong> {version.spec.change_summary}</p>{version.changes && <p>Added: {version.changes.added.join(", ") || "None"} ? Modified: {version.changes.modified.join(", ") || "None"} ? Removed: {version.changes.removed.join(", ") || "None"}</p>}{!!version.migration_issues?.length && <p role="alert" className={styles.error}>{version.migration_issues.join(" ")}</p>}
        {data.stale && <p className={styles.error}>The project blueprint or evidence changed. Generate a new specification before approval or building.</p>}
        <div className={styles.modules}>{version.spec.entities.map(entity => <article key={entity.name}><h3>{entity.label}</h3><p>{entity.fields.map(f => f.label).join(" · ")}</p><small>Read: {entity.read_roles.join(", ")} · Write: {entity.write_roles.join(", ")}</small>{entity.transitions.map((t, index) => <p key={index}>{t.label}: {t.from_value} → {t.to_value}</p>)}</article>)}</div>
        {!!version.ai_reviews?.length && <details><summary>Application Red Team review</summary>{version.ai_reviews.at(-1)?.findings.map((finding, index) => <p key={index}><strong>{finding.severity}: {finding.issue}</strong><br/>{finding.reason}<br/>{finding.mitigation}{finding.requires_revision && " ? Revision required"}</p>)}<p>Design review only. Executed runtime checks are recorded with each build.</p></details>}
        <details open><summary>Requirements & evidence</summary><div className={styles.table}><table><thead><tr><th>Requirement</th><th>Implementation</th><th>Evidence</th></tr></thead><tbody>{version.spec.requirements.map(r => <tr key={r.id}><td><strong>{r.id}</strong><br/>{r.description}</td><td>{r.implementation === "manual" ? "Manual implementation required" : "Included in generated scope"}</td><td>{r.evidence}</td></tr>)}</tbody></table></div></details>
        <details><summary>Assumptions & limitations</summary><ul>{[...version.spec.assumptions, ...version.spec.limitations].map((item, i) => <li key={i}>{item}</li>)}</ul><p>The current generator supports relational records, forms, role permissions and state transitions. Custom algorithms and external integrations require additional implementation.</p></details>
        <details><summary>Edit application specification</summary><p>Saving creates a new draft and clears approval. Keep existing entity and field names to preserve data during upgrades.</p><textarea aria-label="Application specification JSON" rows={16} value={draft || JSON.stringify(version.spec, null, 2)} onChange={e => setDraft(e.target.value)} spellCheck={false}/><button disabled={busy || !canWrite} onClick={() => act("Saving draft", async () => { await post(`${base}/spec`, { base_version: latest?.version, spec: JSON.parse(draft || JSON.stringify(version.spec)) }); setDraft(""); setSelected(0); setConfirmed(false); })}>{version.version === latest?.version ? "Save as new draft" : "Restore as new draft"}</button></details>
        {version.version === latest?.version && <div className={styles.approval}>
          {version.approval ? <p><strong>Approved</strong> · {new Date(version.approval.created_at).toLocaleString()}. Generation uses this exact specification and blueprint.</p> : <><label className={styles.check}><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/>I reviewed this blueprint version, application scope, assumptions and any unimplemented requirements.</label><button disabled={busy || !canApprove || !confirmed || data.stale} onClick={() => act("Approving", () => post(`${base}/approve`, { version: version.version }))}>Approve blueprint & application scope</button></>}
          <button disabled={busy || !canWrite || !version.approval || data.stale || (billing?.account.balance ?? 0) < data.build_cost} onClick={() => act("Building", () => generate(version.version))}>Generate & validate · {data.build_cost} credits</button>
        </div>}
      </section>}
      <section className={styles.panel}><h2>Builds & application versions</h2>{!data.builds.length && <p>Your generated applications and validation results will appear here.</p>}
        {data.builds.map(build => <article key={build.id} className={styles.version}><div className={styles.row}><h3>Specification v{build.spec_version}</h3><span className={styles.status}>{readable(build.status)}</span></div><p>{new Date(build.created_at).toLocaleString()}</p>{(build.error || build.validation?.error) && <p className={styles.error}>{build.error || build.validation?.error}</p>}
          {!!build.findings?.length && <p className={styles.error}>{build.findings.length} requirements need manual implementation. Deployment is blocked until they are resolved.</p>}
          <div className={styles.actions}><button disabled={busy || !build.manifest} onClick={() => act("Downloading", () => download(build))}>Download source ZIP</button><button disabled={busy || !canWrite || build.status !== "ready"} onClick={() => act("Starting preview", async () => setPreview(await post<Preview>(`${base}/builds/${build.id}/preview`)))}>Start 15-minute preview</button><button disabled={busy || !canDeploy || build.status !== "ready" || !data.deployment_configured || !!build.findings?.length} onClick={() => act("Deploying", () => post(`${base}/builds/${build.id}/deploy`))}>Deploy to Render</button><button disabled={busy || !canDeploy || !data.vercel_configured || !data.deployments.some(item => item.build_id === build.id && item.target !== "vercel" && item.status === "live")} onClick={() => act("Deploying frontend", () => post(`${base}/builds/${build.id}/deploy/vercel`))}>Deploy frontend to Vercel</button></div>
          <details><summary>Validation, files & build logs</summary><p>Runtime validation: {build.validation ? readable(build.validation.status) : "Not executed yet"}</p>{build.validation?.checks?.length ? <p>Passed: {build.validation.checks.join(", ")}</p> : <p>No successful runtime checks have been recorded.</p>}<pre>{[...build.logs, ...(build.validation?.logs || [])].join("\n\n")}</pre><ul>{Object.keys(build.manifest || {}).map(path => <li key={path}><code>{path}</code></li>)}</ul></details>
        </article>)}
      </section>
      {data.preview && <section className={styles.panel}><h2>Preview session</h2><p>Expires {new Date(data.preview.expires_at).toLocaleString()}. Preview data is temporary.</p><button disabled={busy || !canWrite} onClick={() => act("Stopping preview", async () => { await post(`${base}/preview/stop`); setPreview(null); })}>Stop preview</button></section>}
      {preview && data.preview && <section className={styles.panel}><h2>Your temporary preview</h2><p>Available for 15 minutes on the computer running Docker. Its test data is discarded when it expires.</p><a href={preview.url} target="_blank" rel="noreferrer">Open application preview ↗</a><p>Sign-in email: <code>{preview.email}</code></p><label>Temporary preview password<input readOnly value={preview.password} type="password" onFocus={e => e.target.select()}/></label><button onClick={() => act("Copying", () => navigator.clipboard.writeText(preview.password))}>Copy preview password</button></section>}
      <section className={styles.panel}><h2>Deployment history</h2>{!data.deployments.length && <p>No deployments yet. A live URL appears only after the hosting provider confirms the release and its health check matches the generated build.</p>}{data.deployments.map(item => <article key={item.id} className={styles.version}><div className={styles.row}><h3>{item.target === "vercel" ? "Vercel" : "Render"} · {readable(item.status)}</h3><button disabled={busy} onClick={() => act("Checking deployment", () => post(`${base}/deployments/${item.id}/refresh`))}>Check provider status</button></div>{item.error && <p className={styles.error}>{item.error}</p>}{item.live_url && <a href={item.live_url} target="_blank" rel="noreferrer">Open live application ↗</a>}<details><summary>Deployment logs</summary><pre>{item.logs.join("\n")}</pre>{item.provider_status && <p>Provider status: {item.provider_status}</p>}</details></article>)}</section>
    </>}
  </div>;
}
