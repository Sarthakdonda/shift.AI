"use client";

import { T } from "@/components/locale";
import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ArrowUpRight,
  FileText,
  Upload,
  Trash2,
  LoaderCircle,
  Check,
  Copy,
  Download,
  Printer,
  ShieldCheck,
} from "lucide-react";
import { Shell } from "@/components/layout/shell";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, useToast } from "@/components/ui/feedback";
import { Empty, ErrorBox, Loading } from "@/components/ui/states";
import { useSession } from "@/components/providers";
import { api, post, humanize, date, ApiError, API_BASE } from "@/lib/api";
import type {
  Project,
  Message,
  Document,
  Analysis,
  Blueprint,
  ModelCatalog,
} from "@/lib/types";
import { DiscoveryWorkspace } from "@/components/discovery/workspace";
import { stages, stageIndex } from "@/components/discovery/stage-progress";
import {
  DiagnosisReport,
  SolutionReport,
  ValueReport,
  FullReport,
  BulletList,
} from "@/components/analysis/report";
import { blueprintMarkdown } from "@/components/blueprint/export";

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
  const [pendingMessage, setPendingMessage] = useState<Message | null>(null);
  const [stopped, setStopped] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [generationId, setGenerationId] = useState<string | null>(null);
  const generation = useRef<{ requestId: string; controller: AbortController } | null>(null);
  const retryDraft = useRef<{ content: string; request_id: string } | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const setNotice = useToast();
  const [rerunning, setRerunning] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [choice, setChoice] = useState<{
    model: string;
    effort: string;
  } | null>(null);
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
      setPendingMessage((pending) => m.some((saved) => saved.request_id === pending?.request_id) ? null : pending);
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
  const effortSupported =
    catalog?.models.find((m) => m.id === selection.model)?.supports_effort ??
    true;
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
    if (!project?.busy && !generationId) return;
    const timer = setInterval(() => void load(), 2500);
    return () => clearInterval(timer);
  }, [project?.busy, generationId, load]);
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
  async function generate(content?: string, retry = false) {
    if (busy || generation.current) return;
    const draft = retry ? retryDraft.current : null;
    const requestId = draft?.request_id || crypto.randomUUID();
    const text = draft?.content ?? content;
    const controller = new AbortController();
    generation.current = { requestId, controller };
    setGenerationId(requestId);
    setStopped(false);
    setAction("Thinking through your answer");
    setError("");
    if (text) {
      retryDraft.current = { content: text, request_id: requestId };
      setMessage("");
      if (!messages.some((m) => m.request_id === requestId)) {
        setPendingMessage({ id: requestId, request_id: requestId, role: "user", content: text, created_at: new Date().toISOString() });
      }
    }
    try {
      await post(`/projects/${id}/${text ? "chat" : "discovery/next"}`, {
        ...(text ? { content: text } : {}), request_id: requestId,
      }, controller.signal);
      retryDraft.current = null;
    } catch (e) {
      if (!controller.signal.aborted && !(e instanceof ApiError && e.code === "generation_cancelled")) {
        setError((e as Error).message);
      }
    } finally {
      if (generation.current?.requestId === requestId) {
        await load();
        generation.current = null;
        setGenerationId(null);
        setAction("");
      }
    }
  }
  async function send() {
    if (message.trim()) await generate(message.trim());
  }
  const stop = useCallback(async () => {
    const current = generation.current;
    const requestId = current?.requestId || project?.active_generation_id;
    if (!requestId || stopping) return;
    setStopping(true);
    try {
      await post(`/projects/${id}/generation/cancel`, { request_id: requestId });
      setStopped(true);
      retryDraft.current = null;
      current?.controller.abort();
      await load();
      if (pendingMessage) {
        const saved = await api<Message[]>(`/projects/${id}/messages`);
        if (!saved.some((m) => m.request_id === pendingMessage.request_id)) {
          setPendingMessage(null);
          setMessage((draft) => draft || pendingMessage.content);
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStopping(false);
    }
  }, [id, project?.active_generation_id, stopping, load, pendingMessage]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented && (generation.current || project?.active_generation_id)) {
        event.preventDefault();
        void stop();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [stop, project?.active_generation_id]);
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
  const conversational =
    tab === "discovery" && isKnownTab && (loading || !!project);
  return (
    <Shell
      projectId={id}
      projectName={project?.name}
      chrome={conversational ? "chat" : "page"}
    >
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
      ) : tab === "discovery" ? (
        <>
          <DiscoveryWorkspace
            project={project}
            messages={pendingMessage && !messages.some((m) => m.request_id === pendingMessage.request_id) ? [...messages, pendingMessage] : messages}
            documents={documents}
            catalog={catalog}
            model={selection.model}
            effort={selection.effort}
            effortSupported={effortSupported}
            busy={busy}
            action={action}
            stopped={stopped}
            stopping={stopping}
            onStop={generationId || project.active_generation_id ? () => void stop() : undefined}
            error={error}
            message={message}
            onMessage={setMessage}
            onSend={() => void send()}
            onBegin={() => void generate()}
            onRetry={() => void generate(undefined, true)}
            onUpload={() => fileInput.current?.click()}
            onRunAnalysis={() => void startAnalysis()}
            onDelete={() => setDeleting("project")}
            onModel={(model) => void chooseModel({ ...selection, model })}
            onEffort={(effort) => void chooseModel({ ...selection, effort })}
            onDismissError={() => {
              setError("");
              void generate(undefined, true);
            }}
          />
          <ProjectDialogs
            deleting={deleting}
            setDeleting={setDeleting}
            rerunning={rerunning}
            setRerunning={setRerunning}
            project={project}
            id={id}
            load={load}
            setNotice={setNotice}
            router={router}
          />
        </>
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
                {tab === "documents"
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
              <Link
                className="button button-secondary button-sm"
                href={`/project/${id}`}
              >
                <T text={"Back to conversation"} />
              </Link>
            </div>
          </div>
          <div className="stage-stepper">
            {stages.map(([label], i) => (
              <div
                className={i <= stageIndex(project.status) ? "complete" : ""}
                key={label}
              >
                <span>
                  {i < stageIndex(project.status) ? <Check size={14} /> : i + 1}
                </span>
                {label}
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
                  <Upload size={16} />
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
                    {blueprint.content.final_report && <a className="button button-secondary" href={`${API_BASE}/api/projects/${id}/export/blueprint/docx?version=${blueprint.version}`}>Word</a>}
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
                    <p className="blueprint-metadata">
                      Version {blueprint.version} · {date(blueprint.created_at)}
                      {blueprint.content.final_report && <> · {blueprint.content.final_report.industry} · {blueprint.content.final_report.language}<br />Selected option: {blueprint.content.final_report.selected_option}</>}
                    </p>
                    {!blueprint.content.final_report && <p className="no-print">This saved report uses the earlier format. Run analysis again to add solution options and the complete implementation design.</p>}
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
          <ProjectDialogs
            deleting={deleting}
            setDeleting={setDeleting}
            rerunning={rerunning}
            setRerunning={setRerunning}
            project={project}
            id={id}
            load={load}
            setNotice={setNotice}
            router={router}
          />
        </>
      )}
    </Shell>
  );
}

/** Confirmation dialogs shared by the conversation and the report tabs. */
function ProjectDialogs({
  deleting,
  setDeleting,
  rerunning,
  setRerunning,
  project,
  id,
  load,
  setNotice,
  router,
}: {
  deleting: string | null;
  setDeleting: (value: string | null) => void;
  rerunning: boolean;
  setRerunning: (value: boolean) => void;
  project: Project;
  id: string;
  load: () => Promise<void>;
  setNotice: (message: string) => void;
  router: ReturnType<typeof useRouter>;
}) {
  return (
    <>
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
            ? `“${project.name}” and all its messages, documents, and blueprints will be permanently deleted. This cannot be undone.`
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
            deleting === "project" ? "Project deleted." : "Document removed.",
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
  );
}
