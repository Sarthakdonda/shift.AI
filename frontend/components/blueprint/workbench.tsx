"use client";
import { useId, useState } from "react";
import Link from "next/link";
import { api, post } from "@/lib/api";
import type { Blueprint, Project } from "@/lib/types";
import type { ReportChapter } from "./implementation-report";

type Part = { chapters: ReportChapter[]; [key: string]: unknown };
const parts = { architecture_report: "Architecture & requirements", experience_report: "Workflows & wireframes", data_report: "Database & APIs", planning_report: "Delivery & transformation plan" };

export function BlueprintWorkbench({ blueprint, project, reload }: { blueprint: Blueprint; project: Project; reload: () => Promise<void> }) {
  const fieldId = useId();
  const [partKey, setPartKey] = useState("architecture_report");
  const [chapterKey, setChapterKey] = useState("");
  const [draft, setDraft] = useState<Part | null>(null);
  const [advanced, setAdvanced] = useState("");
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [versions, setVersions] = useState<{version:number;created_at:string}[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [comments, setComments] = useState<{id:string;content:string;author_name:string;artifact_kind:string}[]>([]);
  const [comment, setComment] = useState("");
  const canWrite = !["viewer", "reviewer"].includes(project.access_role || "");
  const canApprove = ["owner", "admin", "reviewer"].includes(project.access_role || "owner");
  const locked = busy || project.busy || blueprint.stale;
  const content = blueprint.content as unknown as Record<string, Part>;
  const part = draft || content[partKey];
  const chapter = part?.chapters.find(c => c.key === chapterKey) || part?.chapters[0];
  async function act(run: () => Promise<unknown>, success: string) {
    setBusy(true); setMessage("");
    try { await run(); setDraft(null); setAdvanced(""); setConfirmed(false); await reload(); setMessage(success); }
    catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }
  function edit(field: string, value: string | string[]) {
    if (!part || !chapter) return;
    setDraft({...part,chapters:part.chapters.map(c=>c.key===chapter.key?{...c,[field]:value}:c)});
    setAdvanced("");
  }
  return <section className="blueprint-workbench no-print" aria-label="Blueprint review and editing">
    <div className="blueprint-workbench-heading"><div><p className="eyebrow">BLUEPRINT V{blueprint.version}</p><h2>{blueprint.approval && !blueprint.stale ? "Approved blueprint" : blueprint.quality?.complete && !blueprint.stale ? "Ready for your review" : "Blueprint draft"}</h2></div><Link href={`/project/${project.id}/application`}>Application studio →</Link></div>
    {blueprint.stale && <p role="status">Your saved blueprint is preserved. Requirements have changed; run analysis again before editing or approving this version.</p>}
    <details><summary>Quality checks · {blueprint.quality?.checks.filter(c=>c.status==="passed").length ?? 0}/{blueprint.quality?.checks.length ?? 0} passed</summary>
      <ul className="blueprint-quality">{blueprint.quality?.checks.map(check=><li key={check.key}><span>{check.status==="passed"?"✓":"○"}</span><div><strong>{check.label}</strong>{check.detail && <p>{check.detail}</p>}</div></li>)}</ul>
    </details>
    {message && <p role="status">{message}</p>}
    <details onToggle={async e=>{if(e.currentTarget.open){try{const result=await api<{comments:typeof comments}>(`/projects/${project.id}/collaboration`);setComments(result.comments.filter(c=>c.artifact_kind==="blueprint"));}catch(error){setMessage((error as Error).message);}}}}><summary>Blueprint comments</summary>
      {comments.map(c=><p key={c.id}><strong>{c.author_name}</strong> · {c.content}</p>)}
      <div className="blueprint-editor"><label>Comment on this version<textarea rows={3} value={comment} onChange={e=>setComment(e.target.value)}/></label><button className="button button-secondary" disabled={busy || !comment.trim()} onClick={()=>act(async()=>{const saved=await post<(typeof comments)[number]>(`/projects/${project.id}/comments`,{artifact_kind:"blueprint",content:`Blueprint v${blueprint.version}: ${comment}`});setComments([saved,...comments]);setComment("");},"Comment saved.")}>Add comment</button></div>
    </details>
    <div className="blueprint-workbench-actions">
      <Link className="button button-secondary" href={`/project/${project.id}/red-team`}>Red Team findings & review</Link>
      <button className="button button-secondary" disabled={busy} onClick={async()=>{try{setVersions(await api(`/projects/${project.id}/blueprint/versions`));}catch(error){setMessage((error as Error).message);}}}>Version history</button>
      {canWrite && <button className="button button-secondary" disabled={busy || project.busy} onClick={()=>act(()=>post(`/projects/${project.id}/analysis/run`),"Full blueprint regeneration started. Your previous versions remain saved.")}>Regenerate full blueprint</button>}
    </div>
    {!!versions.length && <ul>{versions.map(v=><li key={v.version}>Version {v.version} · {new Date(v.created_at).toLocaleString()} · <a href={`/project/${project.id}/red-team`}>Compare / restore in review</a></li>)}</ul>}
    {canApprove && !blueprint.approval && <div className="blueprint-approval"><label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> I reviewed this version, its assumptions and remaining Red Team risks.</label><button className="button" disabled={locked || !confirmed || !blueprint.quality?.complete} onClick={()=>act(()=>post(`/projects/${project.id}/blueprint/approve`,{version:blueprint.version}),"This exact blueprint version is approved. Review the application scope in Application studio before building.")}>Approve blueprint v{blueprint.version}</button></div>}
    {canWrite && part && <details><summary>Edit or regenerate a blueprint section</summary>
      <div className="blueprint-editor">
        <label><span id={`${fieldId}-area`}>Design area</span><select aria-labelledby={`${fieldId}-area`} value={partKey} disabled={busy} onChange={e=>{setPartKey(e.target.value);setDraft(null);setAdvanced("");setChapterKey("");}}>{Object.entries(parts).filter(([key])=>content[key]).map(([key,title])=><option key={key} value={key}>{title}</option>)}</select></label>
        <label><span id={`${fieldId}-section`}>Section</span><select aria-labelledby={`${fieldId}-section`} value={chapter?.key || ""} onChange={e=>setChapterKey(e.target.value)}>{part.chapters.map(c=><option key={c.key} value={c.key}>{c.title}</option>)}</select></label>
        {chapter && <><label>Title<input value={chapter.title} onChange={e=>edit("title",e.target.value)}/></label><label><span id={`${fieldId}-content`}>Section content</span><textarea aria-labelledby={`${fieldId}-content`} rows={6} value={chapter.narrative} onChange={e=>edit("narrative",e.target.value)}/></label><label><span id={`${fieldId}-basis`}>Evidence and assumptions</span><textarea aria-labelledby={`${fieldId}-basis`} rows={3} value={chapter.basis} onChange={e=>edit("basis",e.target.value)}/></label><label><span id={`${fieldId}-details`}>Details (one per line)</span><textarea aria-labelledby={`${fieldId}-details`} rows={3} value={chapter.items.join("\n")} onChange={e=>edit("items",e.target.value.split("\n").filter(Boolean))}/></label></>}
        <details><summary>Advanced: tables, diagram nodes, requirements and database contract</summary><p>The database contract generates the ER diagram, SQL and column tables together. Save creates a new draft requiring Red Team review.</p><textarea aria-label="Structured blueprint design" rows={18} spellCheck={false} value={advanced || JSON.stringify(part,null,2)} onChange={e=>setAdvanced(e.target.value)}/></details>
        <button className="button" disabled={locked || (!draft && !advanced)} onClick={()=>act(()=>api(`/projects/${project.id}/blueprint/parts/${partKey}`,{method:"PUT",body:JSON.stringify({base_version:blueprint.version,content:advanced?JSON.parse(advanced):part,note:`Edited ${chapter?.title || partKey}`})}),"Saved a new draft. Run Red Team review before approval.")}>Save as new blueprint version</button>
        <label>Regeneration request<textarea rows={3} value={instructions} onChange={e=>setInstructions(e.target.value)} placeholder="Describe what this section needs to include or correct."/></label>
        <button className="button button-secondary" disabled={locked || !instructions.trim()} onClick={()=>act(()=>post(`/projects/${project.id}/blueprint/regenerate`,{base_version:blueprint.version,part:partKey,chapter:chapter?.key || "",instructions}),"Section regeneration started. It will be saved as a new draft for review.")}>Regenerate selected section</button>
      </div>
    </details>}
  </section>;
}
