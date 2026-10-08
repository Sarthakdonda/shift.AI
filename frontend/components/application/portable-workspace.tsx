"use client";
import { useState } from "react";
import { API_BASE, post } from "@/lib/api";
import styles from "./builder.module.css";
export type PortableBuild = { id: string; status: string; spec_version: number; spec?: { storage_mode?: string }; error?: string };
type Artifact = { id: string; build_id: string; target: string; status: string; error?: string; signing: string; device_validation: string; logs: string[]; sha256?: string; size?: number };
export type Artifacts = { items: Artifact[]; workers: { targets: string[]; platform: string }[]; targets: string[] };
export function PortableWorkspace({ projectId, builds, artifacts, canWrite, changed }: { projectId: string; builds: PortableBuild[]; artifacts: Artifacts | null; canWrite: boolean; changed: () => Promise<void> }) {
  const [preview, setPreview] = useState(""), [viewport, setViewport] = useState("desktop"), [refresh, setRefresh] = useState(0), [selected, setSelected] = useState(""), [working, setWorking] = useState(""), [error, setError] = useState("");
  const available = builds.filter(b => b.status === "ready" && b.spec?.storage_mode && b.spec.storage_mode !== "shared_server");
  const build = available.find(b => b.id === selected) || available[0];
  const base = "/projects/" + projectId + "/application";
  async function act(label: string, fn: () => Promise<unknown>) {
    setWorking(label); setError("");
    try { await fn(); await changed(); } catch (e) { setError((e as Error).message); } finally { setWorking(""); }
  }
  async function download(url: string, name: string) {
    const response = await fetch(API_BASE + "/api" + url, { credentials: "include" });
    if (!response.ok) throw new Error((await response.json()).detail || "The artifact is unavailable.");
    const link = document.createElement("a"), href = URL.createObjectURL(await response.blob());
    link.href = href; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(href), 1000);
  }
  return <>
    <section className={styles.panel} aria-label="Live application preview">
      <div className={styles.row}><div><p className={styles.eyebrow}>TRY YOUR APPLICATION</p><h2>Live preview</h2></div>
        {!!available.length && <label>Build<select aria-label="Preview build" value={build?.id || ""} onChange={e => { setSelected(e.target.value); setPreview(""); }}>{available.map(b => <option key={b.id} value={b.id}>Specification v{b.spec_version} · {b.id.slice(-6)}</option>)}</select></label>}
      </div>
      {error && <p className={styles.error} role="alert">{error}</p>}
      {build ? <div className={styles.actions}>
        <button disabled={!!working || !canWrite} onClick={() => act("Opening preview", async () => setPreview((await post<{ url: string }>(base + "/builds/" + build.id + "/portable-preview")).url))}>{preview ? "Renew preview access" : "Open interactive preview"}</button>
        <label>Viewport<select aria-label="Preview viewport" value={viewport} onChange={e => setViewport(e.target.value)}><option value="desktop">Desktop</option><option value="tablet">Tablet</option><option value="mobile">Mobile</option></select></label>
        {preview && <><button onClick={() => setRefresh(refresh + 1)}>Refresh preview</button><a href={preview} target="_blank" rel="noreferrer">Open in new tab ↗</a></>}
      </div> : <div className={styles.previewEmpty}><h3>Your working application will appear here</h3><p>Choose a blueprint, review the specification and generate a validated website or local application. Shared-server applications use the existing container preview below.</p></div>}
      {preview && <><div className={styles.previewCanvas}><iframe key={refresh} src={preview} title="Generated application preview" sandbox="allow-scripts allow-same-origin allow-forms allow-downloads" referrerPolicy="no-referrer" onLoad={event => event.currentTarget.scrollIntoView({ block: "start" })} style={{ width: viewport === "mobile" ? 390 : viewport === "tablet" ? 768 : "100%", height: "min(720px, 80dvh)" }} /></div>
        <p className={styles.caption}>Preview records stay in this browser on this project’s preview origin. Use Backup & storage inside the application to transfer them to another browser or downloaded app. Clearing browser storage can remove them.</p></>}
      {working && <p role="status">{working}…</p>}
    </section>
    <section className={styles.panel} aria-label="Application downloads"><p className={styles.eyebrow}>TAKE YOUR APPLICATION WITH YOU</p><h2>Downloads</h2>
      {!build ? <p>Download formats become available after a portable application passes its browser validation.</p> : <>
        <div className={styles.actions}><button disabled={!!working} onClick={() => act("Downloading files", () => download(base + "/builds/" + build.id + "/download", "application-v" + build.spec_version + ".zip"))}>Download website / PWA & source ZIP</button></div>
        <p>The ZIP contains working web files and native project sources. Installers and mobile binaries are separate artifacts below.</p>
        <div className={styles.downloadGrid}>{(artifacts?.targets || ["windows", "macos", "android", "android_bundle", "ios"]).map(target => {
          const artifact = artifacts?.items.find(a => a.build_id === build.id && a.target === target);
          const label = ({ windows: "Windows installer", macos: "macOS application", android: "Android APK", android_bundle: "Android AAB", ios: "iOS application" } as Record<string,string>)[target] || target;
          const extension = ({windows:"exe",macos:"dmg",android:"apk",android_bundle:"aab",ios:"ipa"} as Record<string,string>)[target];
          return <article key={target}><h3>{label}</h3><p className={styles.status}>{(artifact?.status || "not_generated").replaceAll("_", " ")}</p>
            {artifact?.error && <p>{artifact.error}</p>}
            {artifact?.status === "ready" ? <><button disabled={!!working} onClick={() => act("Downloading installer", () => download(base + "/artifacts/" + artifact.id + "/download", "application-" + target + "." + extension))}>Download {label}</button><p>Signing: {artifact.signing.replaceAll("_", " ")}. Device validation: {artifact.device_validation.replaceAll("_", " ")}.</p></> :
              <button disabled={!!working || !canWrite || ["queued", "building"].includes(artifact?.status || "")} onClick={() => act("Requesting build", () => post(base + "/builds/" + build.id + "/package", { target }))}>{artifact ? "Retry packaging" : "Generate " + label}</button>}
            {target === "ios" && <p>Native iOS requires a Mac worker, Apple signing and provisioning. PWA files are included in the web download.</p>}
          </article>;
        })}</div>
      </>}
      {!!artifacts?.items.length && <details><summary>Artifact build history & logs</summary>{artifacts.items.map(a => <article key={a.id}><h3>{a.target} · {a.status.replaceAll("_", " ")}</h3>{a.error && <p>{a.error}</p>}<pre>{a.logs.join("\n")}</pre>{a.sha256 && <p className={styles.caption}>SHA-256: {a.sha256}</p>}</article>)}</details>}
    </section>
  </>;
}
