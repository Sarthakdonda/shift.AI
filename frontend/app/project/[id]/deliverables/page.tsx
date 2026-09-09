"use client";

import { T } from "@/components/locale";
import { ImportPlanner } from "@/components/integrations";
import { useRouter } from "next/navigation";
import { use, useState, useEffect, useCallback } from "react";
import { Shell } from "@/components/layout/shell";
import { Section, Findings } from "@/components/analysis/report";
import { DeliverableReport } from "@/components/deliverables/report";
import { DeliverableEditor } from "@/components/deliverables/editor";
import { api, post, API_BASE, humanize } from "@/lib/api";
import { languages, blankDeliverable } from "@/lib/deliverables";
import type {
  Artifact,
  Collaboration,
  Deliverable,
  DeliverableState,
} from "@/lib/deliverables";
import type { Project } from "@/lib/types";
import { ConfirmDialog } from "@/components/ui/feedback";

export default function Deliverables({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [leaving, setLeaving] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null),
    [state, setState] = useState<DeliverableState | null>(null),
    [collab, setCollab] = useState<Collaboration | null>(null);
  const [kind, setKind] = useState("business"),
    [language, setLanguage] = useState("en"),
    [instructions, setInstructions] = useState("");
  const [error, setError] = useState(""),
    [action, setAction] = useState(false),
    [history, setHistory] = useState<Artifact[]>([]),
    [selected, setSelected] = useState<Artifact | null>(null);
  const [draft, setDraft] = useState<Deliverable | null>(null),
    [baseVersion, setBaseVersion] = useState(0),
    [note, setNote] = useState(""),
    [reviewNote, setReviewNote] = useState(""),
    [comment, setComment] = useState(""),
    [confirm, setConfirm] = useState(false),
    [discard, setDiscard] = useState(false);
  const load = useCallback(async () => {
    const [p, s, c] = await Promise.all([
      api<Project>(`/projects/${id}`),
      api<DeliverableState>(`/projects/${id}/deliverables`),
      api<Collaboration>(`/projects/${id}/collaboration`),
    ]);
    setProject(p);
    setState(s);
    setCollab(c);
  }, [id]);
  useEffect(() => {
    void load().catch((e) => setError(e.message));
  }, [load]);
  useEffect(() => {
    if (!state?.busy) return;
    const timer = setInterval(
      () => void load().catch((e) => setError(e.message)),
      2500,
    );
    return () => clearInterval(timer);
  }, [state?.busy, load]);
  useEffect(() => {
    if (!draft) return;
    const prevent = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", prevent);
    return () => window.removeEventListener("beforeunload", prevent);
  }, [draft]);
  useEffect(() => {
    if (!draft) return;
    const intercept = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      const link = target.closest("a");
      if (
        !link ||
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey ||
        link.target === "_blank" ||
        link.origin !== location.origin ||
        link.pathname === location.pathname
      )
        return;
      event.preventDefault();
      event.stopPropagation();
      setLeaving(link.pathname + link.search + link.hash);
    };
    document.addEventListener("click", intercept, true);
    return () => document.removeEventListener("click", intercept, true);
  }, [draft]);
  const item = state?.items.find((i) => i.kind === kind),
    artifact = selected || item?.artifact;
  const canEdit = ["owner", "admin", "editor"].includes(state?.role || ""),
    canReview = ["owner", "admin", "reviewer"].includes(state?.role || "");
  const perform = async (fn: () => Promise<unknown>) => {
    setAction(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAction(false);
    }
  };
  const generate = (which: string) =>
    perform(() =>
      post(`/projects/${id}/deliverables/${which}/generate`, {
        language,
        instructions,
      }),
    );
  return (
    <Shell projectId={id} projectName={project?.name}>
      <div className="page-heading">
        <span className="eyebrow">
          <T text={"Implementation studio"} />
        </span>
        <h1>
          <T text={"Deliverables"} />
        </h1>
        <p>
          <T
            text={
              "Build a complete design pack, challenge assumptions, and track every revision."
            }
          />
        </p>
      </div>
      {error && (
        <p role="alert" className="error-box">
          {error}
        </p>
      )}
      {!state ? (
        <p role="status">
          <T text={"Loading deliverables…"} />
        </p>
      ) : (
        <>
          {project?.workspace_id && ["owner", "admin"].includes(state.role) && (
            <ImportPlanner projectId={id} onImported={load} />
          )}
          <div className="studio-controls no-print">
            <label>
              <T text={"Output language"} />
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                {Object.entries(languages).map(([code, label]) => (
                  <option key={code} value={code}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <T text={"Feedback for the next generation"} />
              <textarea
                placeholder="Changes, new constraints, or reviewer feedback…"
                value={instructions}
                maxLength={4000}
                onChange={(e) => setInstructions(e.target.value)}
              />
            </label>
            <button
              className="button button-primary"
              disabled={
                !canEdit ||
                state.busy ||
                action ||
                !!draft ||
                !project?.analysis_ready ||
                project.status !== "BLUEPRINT_READY"
              }
              onClick={() => setConfirm(true)}
            >
              <T text={"Generate complete pack"} />
            </button>
            {(!project?.analysis_ready ||
              project.status !== "BLUEPRINT_READY") && (
              <p>
                <T
                  text={
                    "Complete discovery and core analysis to enable AI generation. You can create and edit drafts now."
                  }
                />
              </p>
            )}
          </div>
          {state.busy && (
            <div className="processing-banner" role="status">
              <T
                text={
                  "Generation in progress. You can leave this page and return to the saved results."
                }
              />
            </div>
          )}
          <nav
            className="deliverable-tabs no-print"
            aria-label="Deliverable types"
          >
            {state.items.map((i) => (
              <button
                key={i.kind}
                className={`button ${kind === i.kind ? "button-primary" : "button-secondary"}`}
                disabled={!!draft}
                onClick={() => {
                  setKind(i.kind);
                  setSelected(null);
                  setHistory([]);
                }}
              >
                {i.label}
                {i.artifact && <small>v{i.artifact.version}</small>}
              </button>
            ))}
          </nav>
          <Section title={item?.label || "Deliverable"}>
            <div className="studio-actions no-print">
              <button
                className="button button-primary"
                disabled={
                  !canEdit ||
                  state.busy ||
                  action ||
                  !!draft ||
                  !project?.analysis_ready ||
                  project.status !== "BLUEPRINT_READY"
                }
                onClick={() => void generate(kind)}
              >
                <T text={"Generate / revise"} />
              </button>
              <button
                className="button button-secondary"
                disabled={!canEdit || state.busy || action || !!draft}
                onClick={() => {
                  setBaseVersion(item?.artifact?.version || 0);
                  setDraft(
                    structuredClone(
                      artifact?.content ||
                        blankDeliverable(item?.label || "Design"),
                    ),
                  );
                  setNote(selected ? "Restore and edit earlier version" : "");
                }}
              >
                <T text={"Edit draft"} />
              </button>
              <button
                className="button button-ghost"
                disabled={action}
                onClick={() =>
                  void perform(async () =>
                    setHistory(
                      await api<Artifact[]>(
                        `/projects/${id}/deliverables/${kind}/versions`,
                      ),
                    ),
                  )
                }
              >
                <T text={"Version history"} />
              </button>
              {artifact && (
                <>
                  <button
                    className="button button-ghost"
                    onClick={() => window.print()}
                  >
                    <T text={"Print / PDF"} />
                  </button>
                  {[
                    "docx",
                    "xlsx",
                    "pptx",
                    "md",
                    "zip",
                    ...(kind === "process" ? ["bpmn"] : []),
                  ].map((fmt) => (
                    <a
                      className="button button-ghost"
                      key={fmt}
                      href={`${API_BASE}/api/projects/${id}/export/${kind}/${fmt}?version=${artifact.version}`}
                    >
                      {fmt.toUpperCase()}
                    </a>
                  ))}
                </>
              )}
            </div>
            {state.jobs[kind]?.status === "error" && (
              <p role="alert" className="error-box">
                {state.jobs[kind].error}
              </p>
            )}
            {item?.stale && (
              <p className="status-warning">
                <T
                  text={
                    "Project context changed after this draft. Regenerate or revise it before approval."
                  }
                />
              </p>
            )}
            {selected && (
              <p className="status-warning">
                <T text={"Viewing historical version "} />
                {selected.version}.{" "}
                <button onClick={() => setSelected(null)}>
                  <T text={"Return to latest"} />
                </button>
              </p>
            )}
            {history.length > 0 && (
              <div className="version-list no-print">
                {history.map((v) => (
                  <button
                    key={v.id}
                    disabled={!!draft}
                    onClick={() => setSelected(v)}
                  >
                    <T text={"Version "} />
                    {v.version} · {new Date(v.created_at).toLocaleString()} ·{" "}
                    {v.note}
                  </button>
                ))}
              </div>
            )}
            {draft ? (
              <>
                <DeliverableEditor value={draft} onChange={setDraft} />
                <label>
                  <T text={"Revision note"} />
                  <input
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    maxLength={1000}
                  />
                </label>
                <div className="studio-actions">
                  <button
                    className="button button-primary"
                    disabled={action}
                    onClick={() =>
                      void perform(async () => {
                        await post(`/projects/${id}/deliverables/${kind}`, {
                          base_version: baseVersion,
                          content: draft,
                          note: note || "Manual revision",
                        });
                        setDraft(null);
                        setSelected(null);
                        setHistory([]);
                      })
                    }
                  >
                    <T text={"Save new version"} />
                  </button>
                  <button
                    className="button button-secondary"
                    onClick={() => setDiscard(true)}
                  >
                    <T text={"Cancel editing"} />
                  </button>
                </div>
              </>
            ) : artifact ? (
              <>
                <p className="muted">
                  <T text={"Version "} />
                  {artifact.version} ·{" "}
                  {new Date(artifact.created_at).toLocaleString()} ·{" "}
                  {artifact.note}
                </p>
                <DeliverableReport content={artifact.content} />
              </>
            ) : (
              <p>
                <T
                  text={
                    "No saved version yet. Generate from discovery or create an editable draft."
                  }
                />
              </p>
            )}
          </Section>
          {artifact && !draft && (
            <>
              <Section title="Independent design review">
                {artifact.ai_reviews.length ? (
                  artifact.ai_reviews.map((r, i) => (
                    <div key={i}>
                      <h3>
                        <T text={"Review cycle "} />
                        {i + 1}
                      </h3>
                      <p>{r.summary}</p>
                      <Findings findings={r.findings} />
                    </div>
                  ))
                ) : (
                  <p>
                    <T
                      text={
                        "This manual revision has not been reviewed by AI. Request generation with your changes or obtain a human review."
                      }
                    />
                  </p>
                )}
              </Section>
              <Section title="Human approval">
                <p>
                  <T
                    text={
                      "Approval applies only to this exact version. New edits need another review."
                    }
                  />
                </p>
                {collab?.reviews
                  .filter(
                    (r) => r.kind === kind && r.version === artifact.version,
                  )
                  .map((r) => (
                    <article key={r.id}>
                      <strong>
                        {humanize(r.decision)} · {r.reviewer_name}
                      </strong>
                      <p>{r.note}</p>
                    </article>
                  ))}
                {canReview && !selected && !item?.stale && (
                  <div className="no-print">
                    <label>
                      <T text={"Review note"} />
                      <textarea
                        value={reviewNote}
                        maxLength={2000}
                        onChange={(e) => setReviewNote(e.target.value)}
                      />
                    </label>
                    <div className="studio-actions">
                      {["approved", "changes_requested"].map((decision) => (
                        <button
                          key={decision}
                          className="button button-secondary"
                          disabled={
                            !reviewNote.trim() ||
                            action ||
                            state.busy ||
                            !!draft
                          }
                          onClick={() =>
                            void perform(async () => {
                              await post(
                                `/projects/${id}/deliverables/${kind}/review`,
                                {
                                  version: artifact.version,
                                  decision,
                                  note: reviewNote,
                                },
                              );
                              setReviewNote("");
                            })
                          }
                        >
                          {humanize(decision)}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </Section>
            </>
          )}
          <Section title="Team conversation">
            <form
              className="no-print"
              onSubmit={(e) => {
                e.preventDefault();
                void perform(async () => {
                  await post(`/projects/${id}/comments`, {
                    content: comment,
                    artifact_kind: kind,
                  });
                  setComment("");
                });
              }}
            >
              <label>
                <T text={"Comment or feedback"} />
                <textarea
                  value={comment}
                  maxLength={4000}
                  onChange={(e) => setComment(e.target.value)}
                />
              </label>
              <button
                className="button button-primary"
                disabled={!comment.trim() || action}
              >
                <T text={"Post comment"} />
              </button>
            </form>
            {collab?.comments.map((c) => (
              <article className="team-comment" key={c.id}>
                <strong>{c.author_name}</strong>
                <small>
                  {new Date(c.created_at).toLocaleString()} · {c.artifact_kind}
                </small>
                <p>{c.content}</p>
              </article>
            ))}
          </Section>
          <details className="panel no-print">
            <summary>
              <T text={"Activity log"} />
            </summary>
            {collab?.activity.map((a) => (
              <p key={a.id}>
                {new Date(a.created_at).toLocaleString()} · {a.action} ·{" "}
                {a.detail}
              </p>
            ))}
          </details>
        </>
      )}
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Generate all seven deliverables?"
        description="This runs multiple AI generation and review calls using your configured provider. Existing versions are kept; new drafts require review."
        confirmLabel="Generate pack"
        onConfirm={async () => {
          await generate("all");
          setConfirm(false);
        }}
      />
      <ConfirmDialog
        open={!!leaving}
        onOpenChange={(v) => {
          if (!v) setLeaving(null);
        }}
        title="Leave unsaved deliverable?"
        description="Your saved versions are safe. Unsaved edits will be discarded."
        confirmLabel="Discard and leave"
        onConfirm={() => {
          setDraft(null);
          router.push(leaving!);
        }}
      />
      <ConfirmDialog
        open={discard}
        onOpenChange={setDiscard}
        title="Discard unsaved edits?"
        description="The saved version will remain available."
        confirmLabel="Discard edits"
        onConfirm={() => {
          setDraft(null);
          setDiscard(false);
        }}
      />
    </Shell>
  );
}
