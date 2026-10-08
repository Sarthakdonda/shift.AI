"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, post, API_BASE, ApiError } from "@/lib/api";
import styles from "./builder.module.css";
import { BlueprintSource, type BlueprintSources } from "./blueprint-source";
import { PortableWorkspace, type Artifacts } from "./portable-workspace";
import { BlueprintSync, type BlueprintSyncProposal } from "./blueprint-sync";
import { DeployPanel } from "./deploy-panel";

type Spec = {
  name: string; description: string; language: string; accent: string; roles: string[];
  entities: { name: string; label: string; fields: { name: string; label: string; kind: string; required: boolean; reference?: string }[]; read_roles: string[]; write_roles: string[]; transitions: { label: string; from_value: string; to_value: string }[]; requirement_ids: string[]; logic?: {description: string; outputs: string[]; cases: {input_json: string; expected_json: string}[]}; integrations?: {name: string; label: string; description: string; fields: string[]}[] }[];
  public_pages?: {slug: string; title: string; description: string}[];
  requirements: { id: string; description: string; evidence: string; implementation: string }[];
  assumptions: string[]; limitations: string[]; change_summary: string;
  application_type?: string; storage_mode?: string; target_platforms?: string[]; storage_reason?: string; questions?: string[];
};
type Version = { id: string; version: number; blueprint_version: number; spec: Spec; approval?: { actor: string; created_at: string }; created_at: string; migration_issues?: string[]; ai_reviews?: { findings: { issue: string; reason: string; mitigation: string; severity: string; requires_revision: boolean }[] }[]; changes?: { added: string[]; removed: string[]; modified: string[] } };
type Build = { id: string; spec_version: number; spec?: Spec; status: string; created_at: string; logs: string[]; error?: string; validation?: { status: string; error?: string; checks: string[]; logs?: string[] }; manifest?: Record<string, string>; findings?: { issue: string; severity: string; status: string }[] };
type Deployment = { id: string; target?: string; build_id: string; status: string; provider_status?: string; live_url?: string; error?: string; logs: string[]; created_at: string };
type Overview = { specs: Version[]; builds: Build[]; deployments: Deployment[]; role: string; busy: boolean; stale: boolean; deployment_configured: boolean; vercel_configured: boolean; platform_admin: boolean; remote_preview?: boolean; preview?: { url: string; expires_at: string }; build_cost: number; job?: { status: string; error?: string; stage?: string; generation_id?: string; completed_steps?: number; resumable?: boolean }; saved_generations?: { id: string; instructions: string; status: string; completed_steps: number; base_version: number; updated_at: string }[] };
type Billing = { plan: { name: string; initial_credits: number }; account: { balance: number; entries: { key: string; amount: number; status: string; created_at: string }[] }; policy: string; payments_enabled: boolean };
type Preview = { url: string; email: string; password: string; expires_in_seconds: number };
const readable = (value: string) => value.replaceAll("_", " ");

export function ApplicationBuilder({ projectId }: { projectId: string }) {
  const base = `/projects/${projectId}/application`;
  const [data, setData] = useState<Overview | null>(null);
  const [billing, setBilling] = useState<Billing | null>(null);
  const [sources, setSources] = useState<BlueprintSources | null>(null);
  const [sourceBusy, setSourceBusy] = useState(false);
  const [syncProposal, setSyncProposal] = useState<BlueprintSyncProposal | null>(null);
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState<{ message: string; retryable: boolean } | null>(null);
  const [working, setWorking] = useState("");
  const [instructions, setInstructions] = useState("");
  const [selected, setSelected] = useState(0);
  const [draft, setDraft] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const buildRequest = useRef<{ version: number; id: string } | null>(null);
  const refreshRequest = useRef<{ base: string; promise: Promise<void> } | null>(null);
  const load = useCallback(async () => {
    if (refreshRequest.current?.base === base) return refreshRequest.current.promise;
    const promise = (async () => {
      // Bound reads and wait for all of them before another refresh. A failed
      // optional panel must not discard a successfully loaded application.
      const options = { signal: AbortSignal.timeout(45000) };
      const [overview, balance, blueprintSources, downloads, proposal] = await Promise.allSettled([
        api<Overview>(base, options), api<Billing>("/billing", options),
        api<BlueprintSources>(base + "/sources", options), api<Artifacts>(base + "/artifacts", options),
        api<BlueprintSyncProposal | null>(base + "/blueprint-sync", options),
      ]);
      if (overview.status === "fulfilled") setData(overview.value);
      if (balance.status === "fulfilled") setBilling(balance.value);
      if (blueprintSources.status === "fulfilled") setSources(blueprintSources.value);
      if (downloads.status === "fulfilled") setArtifacts(downloads.value);
      if (proposal.status === "fulfilled") setSyncProposal(proposal.value);
      const failed = [overview, balance, blueprintSources, downloads, proposal].find(result => result.status === "rejected");
      if (failed?.status === "rejected") throw failed.reason;
      setLoadError(null);
    })().catch((failure: unknown) => {
      const timeout = failure instanceof Error && failure.name === "TimeoutError";
      setLoadError({
        message: timeout ? "Your workspace took too long to respond. Reconnecting…" : failure instanceof Error ? failure.message : "Could not refresh your workspace.",
        retryable: timeout || (failure instanceof ApiError && [0, 408, 429, 500, 502, 503, 504].includes(failure.status)),
      });
      throw failure;
    }).finally(() => { if (refreshRequest.current?.promise === promise) refreshRequest.current = null; });
    refreshRequest.current = { base, promise };
    return promise;
  }, [base]);
  useEffect(() => {
    const refresh = () => { void load().catch(() => {}); };
    refresh();
    window.addEventListener("online", refresh);
    return () => window.removeEventListener("online", refresh);
  }, [load]);
  useEffect(() => {
    if (!loadError?.retryable && !data?.busy && !data?.preview && !artifacts?.items.some(a => ["queued", "building"].includes(a.status)) && !data?.deployments.some(d => ["deploying", "health_pending"].includes(d.status))) return;
    let polling = false;
    const timer = setInterval(async () => {
      if (polling || refreshRequest.current) return;
      polling = true;
      try {
        for (const item of (data?.deployments || []).filter(d => ["deploying", "health_pending"].includes(d.status))) {
          try { await post(`${base}/deployments/${item.id}/refresh`); }
          catch (failure) { setError((failure as Error).message); }
        }
        await load();
      } catch { /* load records recoverable connection errors separately. */ }
      finally { polling = false; }
    }, 6000);
    return () => clearInterval(timer);
  }, [data, artifacts, base, load, loadError]);
  const latest = data?.specs[0];
  const version = data?.specs.find(v => v.version === selected) || latest;
  const canWrite = !!data && ["owner", "admin", "editor"].includes(data.role);
  const canApprove = !!data && ["owner", "admin", "reviewer"].includes(data.role);
  const canDeploy = !!data && ["owner", "admin"].includes(data.role);
  // The newest build that one-click deployment can actually accept.
  const deployableBuild = data?.builds.find(build => build.status === "ready"
    && (!build.spec?.storage_mode || build.spec.storage_mode === "shared_server")
    && (!build.spec?.target_platforms || build.spec.target_platforms.includes("web")));
  const busy = !!working || !!data?.busy || sourceBusy;
  async function sourceChanged() {
    setError(""); setSelected(0); setDraft(""); setConfirmed(false);
    await load();
  }
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
    <header className={styles.hero}><p className={styles.eyebrow}>FROM BLUEPRINT TO WORKING SOFTWARE</p><h1>Application studio</h1><p>Bring your blueprint, review the application, then build, try and download it.</p>
      <div className={styles.steps}><span>1 · Blueprint</span><span>2 · Review specification</span><span>3 · Build & test</span><span>4 · Preview & download</span></div>
    </header>
    {(error || loadError) && <div className={styles.error} role="alert"><p>{error || loadError?.message}</p>
      <button onClick={() => { setError(""); void load().catch(() => {}); }}>{loadError ? "Retry connection" : "Refresh workspace"}</button>
    </div>}
    {!data && !error && !loadError && <p role="status">Loading your application workspace…</p>}
    {data && <>
      <BlueprintSource projectId={projectId} sources={sources} disabled={busy || !canWrite} changed={sourceChanged} onBusyChange={setSourceBusy} />
      {!!data.saved_generations?.length && <section className={styles.panel} aria-label="Saved specification work">
        <h2>Saved specification work</h2><p>Your saved stages stay here when you select another blueprint. Restore a run to return to its blueprint and original request, then resume it.</p>
        {data.saved_generations.map(run => <article className={styles.version} key={run.id}>
          <div className={styles.row}><h3>{run.completed_steps} specification steps saved</h3><span className={styles.status}>{run.status === "complete" ? "Specification saved" : "Saved progress"}</span></div>
          <p>{new Date(run.updated_at).toLocaleString()}</p><p>{run.instructions || "Build from the selected blueprint."}</p>
          {run.status !== "complete" && <button disabled={!canWrite || busy || run.base_version !== (latest?.version || 0)} onClick={() => act("Restoring saved work", async () => {
            const saved = await post<{ instructions: string }>(`${base}/generations/${run.id}/restore`);
            setInstructions(saved.instructions); setSelected(0); setDraft(""); setConfirmed(false);
          })}>Restore saved work</button>}
        </article>)}
      </section>}
      <PortableWorkspace projectId={projectId} builds={data.builds} artifacts={artifacts} canWrite={canWrite} changed={load} />
      {latest && <BlueprintSync projectId={projectId} version={latest.version} approved={!!latest.approval && !data.stale} disabled={busy || !canWrite} proposal={syncProposal} changed={sourceChanged} />}
      <div className={styles.grid}>
        <section className={styles.panel}><h2>{latest ? "Request a change" : "Prepare your application"}</h2><p>{sourceBusy ? "Reading your blueprint. Application planning will be available when it is ready." : !sources?.ready ? sources?.reason || "Upload a blueprint or use a saved blueprint above to get started." : latest ? "Describe changes to features, fields, workflows or visual style. Each change creates a draft for review." : "Your blueprint is ready. Create an application specification directly from it, review the scope, then generate your prototype. No discovery session is required."}</p>
          <label htmlFor="application-instructions">Application requirements or changes</label><textarea id="application-instructions" rows={4} maxLength={6000} value={instructions} onChange={e => setInstructions(e.target.value)} placeholder="For example: add candidate profiles and interview scheduling, with separate recruiter and manager roles." />
          <button disabled={!canWrite || busy || !sources?.ready} onClick={() => act("Planning", async () => { await post(`${base}/plan`, { instructions, base_version: latest?.version || 0 }); setSelected(0); setDraft(""); setConfirmed(false); })}>{busy ? working || (sourceBusy ? "Reading blueprint…" : "Processing…") : latest ? "Draft changes" : "Create application specification"}</button>
          {data.job?.error && <p role="alert" className={styles.error}>{data.job.error}</p>}
          {data.job?.resumable && data.job.status === "failed" && <><p>{data.job.completed_steps || 0} steps saved. Resume uses the original request; create a new specification to use edited requirements.</p><button disabled={!canWrite || busy || !sources?.ready} onClick={() => act("Resuming specification", async () => { await post(`${base}/plan`, { resume_id: data.job?.generation_id }); setSelected(0); setDraft(""); setConfirmed(false); })}>Resume specification</button></>}
          {data.busy && data.job?.stage && <p role="status">Preparing {readable(data.job.stage)} · {data.job.completed_steps || 0} steps saved. Progress is saved as each step finishes.</p>}
        </section>
        <section className={styles.panel}><h2>Build credits</h2><p className={styles.balance}>{billing?.account.balance ?? "—"} <small>credits available</small></p><p>{data.build_cost} credits per validated build. Credits are reserved once and refunded if generation or validation fails.</p>{billing && <p>{billing.plan.name} plan · {billing.plan.initial_credits} starting credits. {!billing.payments_enabled && "Payment checkout is not enabled."}</p>}<p>Website and local application builds run browser validation. Shared-server applications use isolated Docker validation. Native installers require a configured platform worker.</p>
          <details><summary>Credit history</summary>{billing?.account.entries.length ? billing.account.entries.slice().reverse().slice(0,20).map(entry => <p key={entry.key}>{readable(entry.status)} · {entry.status === "refunded" ? "0 net" : entry.amount} credits · {new Date(entry.created_at).toLocaleString()}</p>) : <p>No generation charges yet.</p>}</details>
        </section>
      </div>
      {version && <section className={styles.panel}>
        <div className={styles.row}><h2>Application specification</h2><span className={styles.status}>{readable(version.spec.application_type || "web_application")} · {readable(version.spec.storage_mode || "shared_server")}</span></div>
        <p>{version.spec.storage_reason || "Review the storage and infrastructure requirements before building."}</p>
        <p><strong>Target platforms:</strong> {(version.spec.target_platforms || ["web"]).join(", ")}. Change the application type, storage mode or platforms in the specification editor, or describe the change above.</p>
        {!!version.spec.questions?.length && <div className={styles.error}><h3>Questions to resolve before building</h3><ul>{version.spec.questions.map(q => <li key={q}>{q}</li>)}</ul><p>Enter your answers in the change request above and create a revised specification.</p></div>}
        <div className={styles.row}><div><p className={styles.eyebrow}>BLUEPRINT V{version.blueprint_version}</p><h2>{version.spec.name}</h2></div><label>Application version<select value={version.version} onChange={e => { setSelected(Number(e.target.value)); setDraft(""); setConfirmed(false); }}>{data.specs.map(v => <option value={v.version} key={v.id}>Version {v.version} · {v.approval ? "Approved" : "Draft"}</option>)}</select></label></div>
        <p>{version.spec.description}</p><p><strong>Changes:</strong> {version.spec.change_summary}</p>{version.changes && <p>Added: {version.changes.added.join(", ") || "None"} ? Modified: {version.changes.modified.join(", ") || "None"} ? Removed: {version.changes.removed.join(", ") || "None"}</p>}{!!version.migration_issues?.length && <p role="alert" className={styles.error}>{version.migration_issues.join(" ")}</p>}
        {data.stale && <p className={styles.error}>The project blueprint or evidence changed. Generate a new specification before approval or building.</p>}
        <div className={styles.modules}>{version.spec.entities.map(entity => <article key={entity.name}><h3>{entity.label}</h3><p>{entity.fields.map(f => f.label).join(" · ")}</p><small>Read: {entity.read_roles.join(", ")} · Write: {entity.write_roles.join(", ")}</small>{entity.transitions.map((t, index) => <p key={index}>{t.label}: {t.from_value} → {t.to_value}</p>)}</article>)}</div>
        {version.spec.entities.filter(e => e.logic || e.integrations?.length).map(entity => <details key={entity.name}><summary>{entity.label}: calculations and integrations</summary>{entity.logic && <><p>{entity.logic.description}</p><p>Calculated fields: {entity.logic.outputs.join(", ")}</p>{entity.logic.cases.map((example, i) => <pre style={{whiteSpace:"pre-wrap", overflowWrap:"anywhere"}} key={i}>Input: {example.input_json}{"\n"}Expected: {example.expected_json}</pre>)}</>}{entity.integrations?.map(action => <p key={action.name}><strong>{action.label}</strong>: {action.description}. Fields sent: {action.fields.join(", ")}.</p>)}</details>)}
        {!!version.spec.public_pages?.length && <details><summary>Public website pages</summary>{version.spec.public_pages.map(page => <p key={page.slug}><strong>{page.title}</strong> (/site/{page.slug}): {page.description}</p>)}</details>}
        {!!version.ai_reviews?.length && <details><summary>Application Red Team review</summary>{version.ai_reviews.at(-1)?.findings.map((finding, index) => <p key={index}><strong>{finding.severity}: {finding.issue}</strong><br/>{finding.reason}<br/>{finding.mitigation}{finding.requires_revision && " ? Revision required"}</p>)}<p>Design review only. Executed runtime checks are recorded with each build.</p></details>}
        <details open><summary>Requirements & evidence</summary><div className={styles.table}><table><thead><tr><th>Requirement</th><th>Implementation</th><th>Evidence</th></tr></thead><tbody>{version.spec.requirements.map(r => <tr key={r.id}><td><strong>{r.id}</strong><br/>{r.description}</td><td>{r.implementation === "manual" ? "Manual implementation required" : "Included in generated scope"}</td><td>{r.evidence}</td></tr>)}</tbody></table></div></details>
        <details><summary>Assumptions & limitations</summary><ul>{[...version.spec.assumptions, ...version.spec.limitations].map((item, i) => <li key={i}>{item}</li>)}</ul><p>The generator supports relational records, role permissions, workflows, bounded business calculations, public pages and explicit HTTPS integration actions. Review calculation examples and configure integration credentials before production use.</p></details>
        <details><summary>Edit application specification</summary><p>Saving creates a new draft and clears approval. Keep existing entity and field names to preserve data during upgrades.</p><textarea aria-label="Application specification JSON" rows={16} value={draft || JSON.stringify(version.spec, null, 2)} onChange={e => setDraft(e.target.value)} spellCheck={false}/><button disabled={busy || !canWrite} onClick={() => act("Saving draft", async () => { await post(`${base}/spec`, { base_version: latest?.version, spec: JSON.parse(draft || JSON.stringify(version.spec)) }); setDraft(""); setSelected(0); setConfirmed(false); })}>{version.version === latest?.version ? "Save as new draft" : "Restore as new draft"}</button></details>
        {version.version === latest?.version && <div className={styles.approval}>
          {version.approval ? <p><strong>Approved</strong> · {new Date(version.approval.created_at).toLocaleString()}. Generation uses this exact specification and blueprint.</p> : <><label className={styles.check}><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/>I reviewed this blueprint version, application scope, assumptions and any unimplemented requirements.</label><button disabled={busy || !canApprove || !confirmed || data.stale || !!version.spec.questions?.length} onClick={() => act("Approving", () => post(`${base}/approve`, { version: version.version }))}>Approve blueprint & application scope</button></>}
          <button disabled={busy || !canWrite || !version.approval || data.stale || (billing?.account.balance ?? 0) < data.build_cost} onClick={() => act("Building", () => generate(version.version))}>Generate & validate · {data.build_cost} credits</button>
        </div>}
      </section>}
      <section className={styles.panel}><h2>Build progress & version history</h2>{data.busy && <p role="status">{data.job?.status === "planning" ? "Analyzing blueprint and reviewing the application specification…" : "Your application build is processing. The stages and logs below reflect completed worker actions."}</p>}{!data.builds.length && <p>Your generated applications and validation results will appear here.</p>}
        {data.builds.map(build => <article key={build.id} className={styles.version}><div className={styles.row}><h3>Specification v{build.spec_version}</h3><span className={styles.status}>{readable(build.status)}</span></div><p>{new Date(build.created_at).toLocaleString()}</p>{(build.error || build.validation?.error) && <p className={styles.error}>{build.error || build.validation?.error}</p>}
          {!!build.findings?.length && <p className={styles.caption}>{build.findings.length} requirements need manual implementation. A validated prototype can be deployed below; these features remain unavailable.</p>}
          <div className={styles.actions}><button disabled={busy || !build.manifest} onClick={() => act("Downloading", () => download(build))}>Download source ZIP</button><button disabled={busy || !canWrite || build.status !== "ready" || (!!build.spec?.storage_mode && build.spec.storage_mode !== "shared_server")} onClick={() => act("Starting preview", async () => setPreview(await post<Preview>(`${base}/builds/${build.id}/preview`)))}>Start 15-minute preview</button><button disabled={busy || !canDeploy || build.status !== "ready" || (!!build.spec?.storage_mode && build.spec.storage_mode !== "shared_server") || !data.deployment_configured || !!build.findings?.length} onClick={() => act("Deploying", () => post(`${base}/builds/${build.id}/deploy`))}>Deploy to Render</button><button disabled={busy || !canDeploy || !data.vercel_configured || !data.deployments.some(item => item.build_id === build.id && item.target !== "vercel" && item.status === "live")} onClick={() => act("Deploying frontend", () => post(`${base}/builds/${build.id}/deploy/vercel`))}>Deploy frontend to Vercel</button></div>
          <details><summary>Validation, files & build logs</summary><p>Runtime validation: {build.validation ? readable(build.validation.status) : "Not executed yet"}</p>{build.validation?.checks?.length ? <p>Passed: {build.validation.checks.join(", ")}</p> : <p>No successful runtime checks have been recorded.</p>}<pre>{[...build.logs, ...(build.validation?.logs || [])].join("\n\n")}</pre><ul>{Object.keys(build.manifest || {}).map(path => <li key={path}><code>{path}</code></li>)}</ul></details>
        </article>)}
      </section>
      {data.preview && <section className={styles.panel}><h2>Preview session</h2><p>Expires {new Date(data.preview.expires_at).toLocaleString()}. Preview data is temporary.</p><button disabled={busy || !canWrite} onClick={() => act("Stopping preview", async () => { await post(`${base}/preview/stop`); setPreview(null); })}>Stop preview</button></section>}
      {preview && data.preview && <section className={styles.panel}><h2>Your temporary preview</h2><p>Available for 15 minutes. Remote access requires the configured preview host; local links work on the Docker host. Test data is discarded when it expires.</p><a href={preview.url} target="_blank" rel="noreferrer">Open application preview ↗</a>{data.remote_preview && <button disabled={busy} onClick={() => act("Refreshing preview link", async () => { const link = await post<{url: string}>(`${base}/preview/link`); setPreview({...preview, url: link.url}); })}>Get a new access link</button>}<p>Sign-in email: <code>{preview.email}</code></p><label>Temporary preview password<input readOnly value={preview.password} type="password" onFocus={e => e.target.select()}/></label><button onClick={() => act("Copying", () => navigator.clipboard.writeText(preview.password))}>Copy preview password</button></section>}
      <DeployPanel projectId={projectId} buildId={deployableBuild?.id}
        deployable={!!deployableBuild}
        manualRequirements={deployableBuild?.spec?.requirements.filter(item => item.implementation === "manual") || []}
        reason={data.builds.length ? "Generate and validate a shared-server build targeting the web before deploying." : "Approve a specification and generate a build first."} />
      <section className={styles.panel}><h2>Deployment history</h2>{!data.deployments.length && <p>No deployments yet. A live URL appears only after the hosting provider confirms the release and its health check matches the generated build.</p>}{data.deployments.map(item => <article key={item.id} className={styles.version}><div className={styles.row}><h3>{item.target === "vercel" ? "Vercel" : "Render"} · {readable(item.status)}</h3><button disabled={busy} onClick={() => act("Checking deployment", () => post(`${base}/deployments/${item.id}/refresh`))}>Check provider status</button></div>{item.error && <p className={styles.error}>{item.error}</p>}{item.live_url && <a href={item.live_url} target="_blank" rel="noreferrer">Open live application ↗</a>}<details><summary>Deployment logs</summary><pre>{item.logs.join("\n")}</pre>{item.provider_status && <p>Provider status: {item.provider_status}</p>}</details></article>)}</section>
    </>}
  </div>;
}
