"use client";
import { useState } from "react";
import { post } from "@/lib/api";
import styles from "./builder.module.css";

export function WebsiteInput({ projectId, disabled, onImported }: { projectId: string; disabled?: boolean; onImported: () => Promise<void> }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <form className={styles.panel} onSubmit={async event => {
    event.preventDefault(); setBusy(true); setError("");
    try { await post(`/projects/${projectId}/documents/url`, { url }); setUrl(""); await onImported(); }
    catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }}><h2>Add a website as evidence</h2><p>Import publicly accessible page text into requirement discovery. Sign-in pages, private addresses and sites that disallow automated retrieval are rejected.</p>
    <label htmlFor="evidence-url">Website URL</label><input id="evidence-url" type="url" maxLength={2000} required value={url} onChange={event => setUrl(event.target.value)} placeholder="https://example.com/about"/>
    <button disabled={disabled || busy || !url}>{busy ? "Importing page…" : "Import website"}</button>
    {error && <p role="alert" className={styles.error}>{error}</p>}
  </form>;
}
