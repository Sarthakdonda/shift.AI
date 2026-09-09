"use client";

import { T } from "@/components/locale";
import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ArrowUpRight,
  Send,
  Paperclip,
  FileText,
  Upload,
  Trash2,
  LoaderCircle,
  Check,
  Copy,
  Download,
  Printer,
  ShieldCheck,
  CircleCheck,
  Sparkles,
  RefreshCw,
} from "lucide-react";
import { Shell } from "@/components/layout/shell";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, useToast } from "@/components/ui/feedback";
import { Empty, ErrorBox, Loading } from "@/components/ui/states";
import { useSession } from "@/components/providers";
import { api, post, humanize, date } from "@/lib/api";
import type {
  Project,
  Message,
  Document,
  Analysis,
  Blueprint,
  ModelCatalog,
} from "@/lib/types";
import { ModelPicker } from "@/components/model-picker";
import {
  DiagnosisReport,
  SolutionReport,
  ValueReport,
  FullReport,
  BulletList,
} from "@/components/analysis/report";
import { blueprintMarkdown } from "@/components/blueprint/export";

const stages = ["Discovery", "Diagnosis", "Solution", "Red Team", "Blueprint"];
const stageIndex = (status: string) =>
  status === "BLUEPRINT_READY"
    ? 4
    : status === "BUSINESS_VALUE" || status === "RED_TEAM_REVIEW"
      ? 3
      : status === "SOLUTION_GENERATION"
        ? 2
        : ["SYSTEM_ANALYSIS", "AI_NECESSITY"].includes(status)
          ? 1
          : 0;
export default function Workspace({
  params,
}: {
  params: Promise<{ id: string; section?: string[] }>;
}) {
  const { id, section } = use(params);
  const tab = section?.[0] || "discovery";
  const router = useRouter();
  const { health } = useSession();
  const [project, setProject] = useState<Project | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [action, setAction] = useState("");
  const [message, setMessage] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const setNotice = useToast();
  const [rerunning, setRerunning] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [choice, setChoice] = useState<{ model: string; effort: string } | null>(
    null,
  );
  const bottom = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const load = useCallback(async () => {
    try {
      const p = await api<Project>(`/projects/${id}`);
      const [m, d, a, b] = await Promise.all([
        api<Message[]>(`/projects/${id}/messages`),
        api<Document[]>(`/projects/${id}/documents`),
        api<Analysis | null>(`/projects/${id}/analysis`),
        api<Blueprint | null>(`/projects/${id}/blueprint`),
      ]);
      setProject(p);
      setMessages(m);
      setDocuments(d);
      setAnalysis(a);
      setBlueprint(b);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    // The catalog reflects the models the configured keys can actually use.
    api<ModelCatalog>("/models")
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, []);
  const selection = choice ?? {
    model: project?.model || catalog?.default_model || "",
    effort: project?.effort || catalog?.default_effort || "low",
  };
  async function chooseModel(next: { model: string; effort: string }) {
    const previous = selection;
    setChoice(next);
    try {
      await post(`/projects/${id}/model`, next);
      setNotice(
        next.model === previous.model
          ? `Effort set to ${next.effort}.`
          : `Model set to ${next.model}.`,
      );
    } catch (e) {
      setChoice(previous);
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    if (!project?.busy) return;
    const timer = setInterval(() => void load(), 2500);
    return () => clearInterval(timer);
  }, [project?.busy, load]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages.length]);
  const busy = !!action || !!project?.busy;
  async function perform(name: string, fn: () => Promise<unknown>) {
    setAction(name);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      await load();
      setAction("");
    }
  }
  async function upload(file?: File) {
    if (!file || busy) return;
    if (file.size > (health?.max_upload_mb || 15) * 1024 * 1024) {
      setError(`Files must be ${health?.max_upload_mb || 15} MB or smaller.`);
      return;
    }
    if (!/\.(pdf|docx|pptx|txt|csv|xlsx)$/i.test(file.name)) {
      setError("Choose a PDF, DOCX, PPTX, TXT, CSV, or XLSX file.");
      return;
    }
    const body = new FormData();
    body.append("file", file);
    await perform("Uploading document", () =>
      api(`/projects/${id}/documents`, { method: "POST", body }),
    );
    if (fileInput.current) fileInput.current.value = "";
  }
  const runAnalysis = () =>
    perform("Starting analysis", () => post(`/projects/${id}/analysis/run`));
  const startAnalysis = () =>
    analysis || blueprint ? setRerunning(true) : runAnalysis();
  const isKnownTab =
    [
      "discovery",
      "documents",
      "analysis",
      "solution",
      "red-team",
      "blueprint",
    ].includes(tab) &&
    (!section || section.length <= 1);
  return (
    <Shell projectId={id} projectName={project?.name}>
      <input
        ref={fileInput}
        type="file"
        hidden
        accept=".pdf,.docx,.pptx,.txt,.csv,.xlsx"
        onChange={(e) => void upload(e.target.files?.[0])}
      />
      {loading ? (
        <Loading />
      ) : !project ? (
        <>
          <ErrorBox message={error || "Project not found."} />
          <Link className="text-button" href="/dashboard">
            <T text={"Back to projects "} />
            <ArrowRight size={15} />
          </Link>
        </>
      ) : !isKnownTab ? (
        <Empty
          title="Page not found"
          description="Choose a project section from the navigation."
          href={`/project/${id}`}
        />
      ) : (
        <>
          <div className="project-heading">
            <div>
              <div className="project-meta">
                <span className="eyebrow">
                  {project.industry || "Business strategy"}
                </span>
                <span
                  className={`badge ${project.status === "BLUEPRINT_READY" ? "badge-green" : "badge-orange"}`}
                >
                  {humanize(project.status)}
                </span>
              </div>
              <h1>{project.name}</h1>
              <p>
                {tab === "discovery"
                  ? "Let’s build a clear picture of what’s happening, and what could be better."
                  : tab === "documents"
                    ? "Add the evidence that helps us understand your business."
                    : tab === "analysis"
                      ? "Understand the system, the root problem, and whether AI belongs."
                      : tab === "solution"
                        ? "A practical approach, built around your actual needs."
                        : tab === "red-team"
                          ? "A second opinion on assumptions, risks, and what could go wrong."
                          : "Your evidence-backed strategy and implementation plan."}
              </p>
            </div>
            <div className="heading-actions">
              {project.status === "BLUEPRINT_READY" && tab !== "blueprint" && (
                <Link
                  className="button button-secondary button-sm"
                  href={`/project/${id}/blueprint`}
                >
                  <T text={"View blueprint "} />
                  <ArrowUpRight size={15} />
                </Link>
              )}
              <button
                className="icon-button"
                aria-label="Delete project"
                disabled={busy}
                onClick={() => setDeleting("project")}
              >
                <Trash2 size={17} />
              </button>
            </div>
          </div>
          <div className="stage-stepper">
            {stages.map((s, i) => (
              <div
                className={i <= stageIndex(project.status) ? "complete" : ""}
                key={s}
              >
                <span>
                  {i < stageIndex(project.status) ? <Check size={14} /> : i + 1}
                </span>
                {s}
                {i < 4 && <i />}
              </div>
            ))}
          </div>
          {error && (
            <ErrorBox
              message={error}
              onRetry={() => {
                setError("");
                void load();
              }}
            />
          )}
          {project.error && <ErrorBox message={project.error} />}
          {project.retrieval_warnings?.map((warning) => (
            <div className="setup-note" key={warning} role="status">
              <FileText size={16} /> {warning}
            </div>
          ))}
          {project.busy && (
            <div className="processing-banner" role="status">
              <LoaderCircle size={21} className="spin" />
              <div>
                <strong>
                  {humanize(project.status)}
                  <T text={" in progress"} />
                </strong>
                <p>
                  <T
                    text={
                      "Your work is saved. You can explore the workspace while we connect the dots."
                    }
                  />
                </p>
              </div>
            </div>
          )}
          {tab === "discovery" && (
            <div className="discovery-layout">
              <section className="panel conversation">
                <header>
                  <div className="row">
                    <span className="assistant-avatar">
                      <Sparkles size={19} />
                    </span>
                    <div>
                      <h2>
                        <T text={"Let’s understand the challenge"} />
                      </h2>
                      <small>
                        <T text={"Discovery · One useful question at a time"} />
                      </small>
                    </div>
                  </div>
                  <span className="badge">
                    <span className="tiny-orange" />
                    <T text={" Your thinking partner"} />
                  </span>
                </header>
                <div className="messages">
                  {messages.map((m) => (
                    <div className={`message ${m.role}`} key={m.id}>
                      <span
                        className={`message-avatar ${m.role === "assistant" ? "assistant-avatar" : ""}`}
                      >
                        {m.role === "assistant" ? <Sparkles size={15} /> : "Y"}
                      </span>
                      <div>
                        <div className="message-label">
                          {m.role === "assistant" ? "shift.AI" : "You"}{" "}
                          <span>
                            {new Date(m.created_at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                        <div className="message-content">{m.content}</div>
                      </div>
                    </div>
                  ))}
                  {!messages.some((m) => m.role === "assistant") && (
                    <div className="discovery-start">
                      <span className="assistant-avatar">
                        <Sparkles size={19} />
                      </span>
                      <h3>
                        <T text={"Every good solution starts here."} />
                      </h3>
                      <p>
                        <T
                          text={
                            "I’ll help uncover the problem behind your request, using your answers and any documents you add."
                          }
                        />
                      </p>
                      <Button
                        disabled={busy}
                        onClick={() =>
                          void perform("Preparing your first question", () =>
                            post(`/projects/${id}/discovery/next`),
                          )
                        }
                      >
                        {busy ? "Preparing…" : "Begin the conversation"}
                        <ArrowRight size={16} />
                      </Button>
                    </div>
                  )}
                  {action && (
                    <div className="thinking" role="status">
                      <LoaderCircle size={16} className="spin" />
                      {action}…
                    </div>
                  )}
                  <div ref={bottom} />
                </div>
                {project.analysis_ready && !project.busy && (
                  <div className="ready-banner">
                    <CircleCheck size={21} />
                    <div>
                      <strong>
                        <T
                          text={
                            "We have enough context. You can run analysis now."
                          }
                        />
                      </strong>
                      <span>
                        <T
                          text={
                            "Next: diagnose the root problem, weigh the options, and review the recommendation."
                          }
                        />
                      </span>
                    </div>
                    <Button
                      size="sm"
                      disabled={busy}
                      onClick={() => void startAnalysis()}
                    >
                      <T text={"Run analysis "} />
                      <ArrowRight size={15} />
                    </Button>
                  </div>
                )}
                <form
                  className="composer"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (!message.trim() || busy) return;
                    const content = message;
                    await perform("Thinking through your answer", async () => {
                      try {
                        await post(`/projects/${id}/chat`, { content });
                        setMessage("");
                      } catch (e) {
                        const saved = await api<Message[]>(
                          `/projects/${id}/messages`,
                        );
                        if (
                          saved.at(-1)?.role === "user" &&
                          saved.at(-1)?.content === content
                        )
                          setMessage("");
                        throw e;
                      }
                    });
                  }}
                >
                  <textarea
                    aria-label="Your message"
                    rows={2}
                    maxLength={12000}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Share a little more about your process…"
                    disabled={busy}
                    onKeyDown={(e) => {
                      if (
                        e.key === "Enter" &&
                        !e.shiftKey &&
                        !e.nativeEvent.isComposing
                      ) {
                        e.preventDefault();
                        e.currentTarget.form?.requestSubmit();
                      }
                    }}
                  />
                  <div className="composer-bottom">
                    <button
                      type="button"
                      className="text-button"
                      disabled={busy}
                      onClick={() => fileInput.current?.click()}
                    >
                      <Paperclip size={17} />
                      <T text={" Add context"} />
                    </button>
                    {catalog && (
                      <ModelPicker
                        models={catalog.models}
                        efforts={catalog.efforts}
                        model={selection.model}
                        effort={selection.effort}
                        disabled={busy}
                        onChange={(next) => void chooseModel(next)}
                      />
                    )}
                    <span>
                      <T
                        text={"Enter to send · Shift + Enter for a new line"}
                      />
                    </span>
                    <Button
                      type="submit"
                      size="sm"
                      disabled={busy || !message.trim()}
                      aria-label="Send message"
                    >
                      <Send size={17} />
                    </Button>
                  </div>
                </form>
                <div className="chat-footer">
                  <T
                    text={
                      "Your context stays with this project. Recommendations follow the evidence."
                    }
                  />
                </div>
                {messages.at(-1)?.role === "user" &&
                  messages.length > 1 &&
                  !busy && (
                    <button
                      className="text-button retry-discovery"
                      onClick={() =>
                        void perform("Retrying discovery", () =>
                          post(`/projects/${id}/discovery/next`),
                        )
                      }
                    >
                      <RefreshCw size={14} />
                      <T text={" Retry response to your saved answer"} />
                    </button>
                  )}
              </section>
              <aside className="discovery-sidebar">
                <section className="panel discovery-progress">
                  <div className="row-between">
                    <h3>
                      <T text={"Building the picture"} />
                    </h3>
                    <span className="progress-total">
                      {project.discovery_scores.overall || 0}
                      <small>%</small>
                    </span>
                  </div>
                  <p>
                    <T text={"Context gathered, not certainty."} />
                  </p>
                  {[
                    "business",
                    "problem",
                    "workflow",
                    "people",
                    "technology",
                    "data",
                    "constraints",
                    "impact",
                    "integrations",
                    "outcome",
                  ].map((k) => (
                    <div className="category-progress" key={k}>
                      <div className="row-between">
                        <span>{humanize(k)}</span>
                        <small>{project.discovery_scores[k] || 0}%</small>
                      </div>
                      <div className="progress-track">
                        <span
                          style={{
                            width: `${project.discovery_scores[k] || 0}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </section>
                <section className="warm-panel">
                  <span className="eyebrow">
                    <T text={"Why we ask"} />
                  </span>
                  <h3>
                    <T text={"Understand first."} />
                    <br />
                    <T text={"Recommend second."} />
                  </h3>
                  <p>
                    <T
                      text={
                        "The right solution might be AI, simple automation, or a better way of working. Your context tells us which."
                      }
                    />
                  </p>
                </section>
                {!!project.discovery?.critical_missing.length && (
                  <section className="panel context-gaps">
                    <h3>
                      <T text={"Still to understand"} />
                    </h3>
                    <BulletList items={project.discovery.critical_missing} />
                  </section>
                )}
                <Link
                  href={`/project/${id}/documents`}
                  className="document-shortcut"
                >
                  <FileText size={19} />
                  <div>
                    <strong>
                      {documents.length}
                      <T text={" supporting documents"} />
                    </strong>
                    <span>
                      <T text={"Add evidence to the conversation"} />
                    </span>
                  </div>
                  <ArrowUpRight size={17} />
                </Link>
              </aside>
            </div>
          )}
          {tab === "documents" && (
            <div className="documents-page">
              <div
                className={`upload-zone ${dragging ? "dragging" : ""} ${busy ? "disabled" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  if (!busy) setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  void upload(e.dataTransfer.files[0]);
                }}
              >
                <span className="upload-icon">
                  <Upload size={27} />
                </span>
                <h2>
                  <T text={"Bring your business into focus."} />
                </h2>
                <p>
                  <T
                    text={
                      "Drop a document here, or choose a file to add context."
                    }
                  />
                </p>
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => fileInput.current?.click()}
                >
                  <PlusFile />
                  <T text={" Choose a file"} />
                </Button>
                <small>
                  <T text={"PDF, DOCX, PPTX, TXT, CSV, XLSX · Up to"} />{" "}
                  {health?.max_upload_mb || 15}
                  <T text={" MB · 20 files per project"} />
                </small>
              </div>
              <div className="section-toolbar">
                <div>
                  <h2>
                    <T text={"Project documents"} />{" "}
                    <span className="count">{documents.length}</span>
                  </h2>
                  <p className="muted">
                    <T
                      text={
                        "Processed files inform discovery and analysis. New evidence resets earlier analysis."
                      }
                    />
                  </p>
                </div>
              </div>
              {!documents.length ? (
                <Empty
                  title="The full picture starts with your context."
                  description="Process notes, spreadsheets, and requirements help us ask better questions. Uploading is optional."
                />
              ) : (
                <div className="document-grid">
                  {documents.map((d) => (
                    <article className="panel document-card" key={d.id}>
                      <div className="row-between">
                        <span className="document-type">
                          <FileText size={20} />
                          {d.file_type.toUpperCase()}
                        </span>
                        <span
                          className={`badge ${d.status === "processed" ? "badge-green" : d.status === "failed" ? "severity-high" : "badge-orange"}`}
                        >
                          {d.status === "processing" && (
                            <LoaderCircle size={12} className="spin" />
                          )}
                          {humanize(d.status)}
                        </span>
                      </div>
                      <h3>{d.filename}</h3>
                      <small>
                        {(d.size / 1024).toFixed(1)}
                        <T text={" KB"} />
                        {d.chunk_count ? ` · ${d.chunk_count} text chunks` : ""}
                      </small>
                      <p>
                        {d.summary ||
                          (d.status === "processing"
                            ? "Reading your document and gathering useful facts…"
                            : d.error || "No summary available.")}
                      </p>
                      {d.warnings?.map((w) => (
                        <p className="small muted" key={w}>
                          {w}
                        </p>
                      ))}
                      {!!d.facts?.length && (
                        <details>
                          <summary>
                            {d.facts.length}
                            <T text={" extracted facts"} />
                          </summary>
                          <BulletList
                            items={d.facts.map(
                              (f) => `${f.fact} (${f.source})`,
                            )}
                          />
                        </details>
                      )}
                      <button
                        className="text-button delete-link"
                        disabled={busy}
                        onClick={() => setDeleting(d.id)}
                      >
                        <Trash2 size={14} />
                        <T text={" Remove document"} />
                      </button>
                    </article>
                  ))}
                </div>
              )}
              <div className="setup-note">
                <ShieldCheck size={17} />
                <span>
                  <T
                    text={
                      "Text is extracted for analysis. Scanned PDFs need OCR before upload. Original files are not retained."
                    }
                  />
                </span>
              </div>
            </div>
          )}
          {["analysis", "solution", "red-team"].includes(tab) &&
            (analysis &&
            (tab === "analysis"
              ? analysis.workflow_analysis
              : tab === "solution"
                ? analysis.solution
                : analysis.red_team) ? (
              <>
                {tab === "analysis" ? (
                  <>
                    <DiagnosisReport data={analysis} />
                    <ValueReport data={analysis} />
                  </>
                ) : (
                  <SolutionReport
                    data={analysis}
                    reviewOnly={tab === "red-team"}
                  />
                )}
              </>
            ) : (
              <Empty
                title={
                  project.busy
                    ? "Your analysis is taking shape."
                    : "Good answers start with good context."
                }
                description={
                  project.busy
                    ? "The stages above update as each part is completed. This page refreshes automatically."
                    : "Complete discovery, then run analysis to see your diagnosis, solution, and Red Team review here."
                }
                href={`/project/${id}`}
                action="Back to discovery"
              />
            ))}
          {tab === "blueprint" &&
            (blueprint ? (
              <div className="blueprint-page">
                <div className="blueprint-toolbar">
                  <div>
                    <span className="badge badge-green">
                      <FileText size={13} />
                      <T text={" Version "} />
                      {blueprint.version}
                    </span>
                    <span>
                      <T text={"Prepared "} />
                      {date(blueprint.created_at)}
                    </span>
                  </div>
                  <div>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(
                            blueprintMarkdown(project.name, blueprint.content),
                          );
                          setNotice("Blueprint copied to clipboard.");
                        } catch {
                          setError(
                            "Clipboard access was blocked. Use Download instead.",
                          );
                        }
                      }}
                    >
                      <Copy size={15} />
                      <T text={" Copy"} />
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        const url = URL.createObjectURL(
                          new Blob(
                            [
                              blueprintMarkdown(
                                project.name,
                                blueprint.content,
                              ),
                            ],
                            { type: "text/markdown;charset=utf-8" },
                          ),
                        );
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `${project.name.replace(/[^a-z0-9]+/gi, "-").slice(0, 80)}-blueprint.md`;
                        a.click();
                        setTimeout(() => URL.revokeObjectURL(url), 1000);
                        setNotice("Blueprint downloaded.");
                      }}
                    >
                      <Download size={15} />
                      <T text={" Download"} />
                    </Button>
                    <Button size="sm" onClick={() => window.print()}>
                      <Printer size={15} />
                      <T text={" Print / PDF"} />
                    </Button>
                  </div>
                </div>
                <div className="blueprint-cover">
                  <div>
                    <span className="eyebrow">
                      <T text={"shift.AI · Strategy & implementation"} />
                    </span>
                    <h2>{project.name}</h2>
                    <p>
                      <T
                        text={
                          "From business context to a clear, reviewed direction."
                        }
                      />
                    </p>
                  </div>
                  <FileText size={58} strokeWidth={1} />
                </div>
                <FullReport data={blueprint.content} />
              </div>
            ) : (
              <Empty
                title="Your next chapter, in one blueprint."
                description="After discovery, analysis and Red Team review, your complete implementation plan will appear here."
                href={`/project/${id}`}
                action="Continue discovery"
              />
            ))}
          <ConfirmDialog
            open={!!deleting}
            onOpenChange={(open) => {
              if (!open) setDeleting(null);
            }}
            title={
              deleting === "project"
                ? "Delete this project?"
                : "Remove this document?"
            }
            description={
              deleting === "project"
                ? `?${project.name}? and all its messages, documents, and blueprints will be permanently deleted. This cannot be undone.`
                : "This removes the document and its extracted evidence. Refresh discovery and run analysis again to update your results."
            }
            confirmLabel="Delete"
            danger
            onConfirm={async () => {
              await api(
                `/projects/${id}${deleting === "project" ? "" : `/documents/${deleting}`}`,
                { method: "DELETE" },
              );
              setNotice(
                deleting === "project"
                  ? "Project deleted."
                  : "Document removed.",
              );
              if (deleting === "project") router.push("/dashboard");
              else await load();
            }}
          />
          <ConfirmDialog
            open={rerunning}
            onOpenChange={setRerunning}
            title="Run a fresh analysis?"
            description="This will generate new results and replace the current analysis and blueprint. Export your current blueprint first if you want to keep a copy."
            confirmLabel="Run analysis"
            onConfirm={async () => {
              await post(`/projects/${id}/analysis/run`);
              setNotice("A fresh analysis is underway.");
              await load();
            }}
          />
        </>
      )}
    </Shell>
  );
}
function PlusFile() {
  return <Upload size={16} />;
}
