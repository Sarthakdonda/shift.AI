"use client";
import { useState } from "react";
import Link from "next/link";
import { api, post } from "@/lib/api";
import styles from "./builder.module.css";
export type BlueprintSources = { choices: { project_id: string; name: string; version: number }[]; selected: { name: string; version: number } | null; current: { name: string; version: number } | null; ready: boolean; reason: string | null };
export function BlueprintSource({ projectId, sources, disabled, changed, onBusyChange }: { projectId: string; sources: BlueprintSources | null; disabled: boolean; changed: () => Promise<void>; onBusyChange: (busy: boolean) => void }) {
  const [choice, setChoice] = useState(""), [busy, setBusy] = useState(false), [message, setMessage] = useState(""), [error, setError] = useState("");
  const base = "/projects/" + projectId + "/application";
  async function act(fn: () => Promise<unknown>) {
    setBusy(true); onBusyChange(true); setMessage(""); setError("");
    try { await fn(); await changed(); setMessage("Blueprint source updated. Review the active blueprint before creating your application specification."); }
    catch (error) { setError((error as Error).message); } finally { setBusy(false); onBusyChange(false); }
  }
  return <section className={styles.panel} aria-label="Choose your blueprint">
    <p className={styles.eyebrow}>START WITH YOUR REQUIREMENTS</p><h2>Choose your blueprint</h2>
    <p>Already have a blueprint? Upload it or use a saved one to build directly. You do not need to repeat discovery.</p>
    {(sources?.selected || sources?.current) && <p><strong>Active blueprint:</strong> {(sources.selected || sources.current)!.name} · v{(sources.selected || sources.current)!.version}. {sources.ready ? "Ready to create an application specification." : sources.reason}</p>}
    <div className={styles.sourceGrid}>
      <article><h3>Upload a blueprint</h3><p>Bring a PDF, Word document, Markdown or structured JSON. Its requirements stay linked to your application.</p>
        <label htmlFor="blueprint-upload">Blueprint file · up to 10 MB</label>
        <input id="blueprint-upload" type="file" accept=".pdf,.docx,.md,.json" disabled={disabled || busy} onChange={e => {
          const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
          void act(async () => {
            if (file.size > 10 * 1024 * 1024) throw new Error("Choose a blueprint up to 10 MB.");
            const body = new FormData(); body.append("file", file);
            await api(base + "/import", { method: "POST", body });
          });
        }} />
      </article>
      <article><h3>Use my shift.AI blueprint</h3><p>Select a reviewed design from your projects. Its structured requirements and diagrams remain intact.</p>
        <label htmlFor="blueprint-project">Saved blueprint</label><select id="blueprint-project" value={choice} onChange={e => setChoice(e.target.value)} disabled={disabled || busy}><option value="">Choose a project</option>{sources?.choices.map(c => <option key={c.project_id} value={c.project_id}>{c.name} · v{c.version}</option>)}</select>
        <button disabled={disabled || busy || !choice} onClick={() => act(() => post(base + "/source", { project_id: choice, version: sources?.choices.find(c => c.project_id === choice)?.version }))}>Use selected blueprint</button>
        {sources?.selected && <button disabled={disabled || busy} onClick={() => act(() => api(base + "/source", { method: "DELETE" }))}>Use this project’s current blueprint</button>}
      </article>
      <article><h3>Start from a business idea</h3><p>Only need this if you do not have a blueprint yet. Discovery helps clarify your idea and create one.</p><Link href={"/project/" + projectId}>Continue discovery →</Link><p><Link href="/project/new">Start a new project</Link></p></article>
    </div>
    {busy && <p role="status">Reading and preserving your blueprint…</p>}{message && <p role="status">{message}</p>}
    {error && <p role="alert" className={styles.error}>{error}</p>}
  </section>;
}
