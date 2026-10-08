"use client";

import { useState } from "react";
import Link from "next/link";
import { post } from "@/lib/api";
import styles from "./builder.module.css";

export type BlueprintSyncProposal = {
  id: string; spec_version: number; status: string; structured?: boolean; error?: string;
  changes?: { title: string; before: unknown; after: unknown }[];
  result?: { version: number; structured: boolean };
};
const display = (value: unknown) => typeof value === "string" ? value : JSON.stringify(value, null, 2);

export function BlueprintSync({ projectId, version, approved, disabled, proposal, changed }: {
  projectId: string; version: number; approved: boolean; disabled: boolean;
  proposal: BlueprintSyncProposal | null; changed: () => Promise<void>;
}) {
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [reviewed, setReviewed] = useState<string | null>(null);
  async function run(apply = false) {
    setWorking(true); setError("");
    try {
      await post(`/projects/${projectId}/application/blueprint-sync${apply ? `/${proposal?.id}/apply` : ""}`, apply ? {} : { version });
      setReviewed(null);
      await changed();
    } catch (e) { setError((e as Error).message); }
    finally { setWorking(false); }
  }
  const matching = proposal?.spec_version === version;
  return <section className={styles.panel}>
    <h2>Keep the blueprint up to date</h2>
    <p>Prepare a proposal from your approved application specification, then compare and review the changes before saving a new blueprint version.</p>
    <button disabled={disabled || working || !approved} onClick={() => run()}>Prepare blueprint update</button>
    {!approved && <p>Approve the current application specification first.</p>}
    {error && <p className={styles.error} role="alert">{error}</p>}
    {matching && proposal && <>
      {["queued", "preparing"].includes(proposal.status) && <p role="status">Preparing blueprint changes…</p>}
      {proposal.status === "failed" && <p className={styles.error} role="alert">{proposal.error}</p>}
      {proposal.status === "ready" && <>
        <p>{proposal.structured ? "Saving creates a draft blueprint in this project. Run its Red Team review before planning and approving the next application version. Any source project remains unchanged." : "Saving creates a revised Markdown source for this application. Review and approve a new application specification afterward. Your original upload remains in version history."}</p>
        {proposal.changes?.map((change, i) => <details key={`${proposal.id}-${i}`}>
          <summary>{change.title}</summary>
          <h3>Current blueprint</h3><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{display(change.before)}</pre>
          <h3>Proposed blueprint</h3><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{display(change.after)}</pre>
        </details>)}
        {!proposal.changes?.length && <p>No chapter changes were proposed. Saving records the application version and requires a fresh review.</p>}
        <label className={styles.check}><input type="checkbox" checked={reviewed === proposal.id} onChange={e => setReviewed(e.target.checked ? proposal.id : null)} />I reviewed the proposed blueprint changes.</label>
        <button disabled={disabled || working || reviewed !== proposal.id} onClick={() => run(true)}>Save new blueprint version</button>
      </>}
      {proposal.status === "applied" && <p>Saved blueprint version {proposal.result?.version}. {proposal.result?.structured && <Link href={`/project/${projectId}/blueprint`}>Open blueprint for review</Link>}</p>}
    </>}
  </section>;
}
