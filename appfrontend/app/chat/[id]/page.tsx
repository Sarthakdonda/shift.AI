"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  CircleCheck,
  FileText,
  FolderOpen,
  MoreHorizontal,
  ScrollText,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { Screen } from "@/components/shell/screen";
import { useRequireAuth } from "@/components/shell/guard";
import { useSession, useToast } from "@/components/providers";
import { ConfirmSheet, Sheet } from "@/components/ui/sheet";
import { ErrorNote, SkeletonBlocks, Splash } from "@/components/ui/states";
import { Opener, Stream } from "@/components/chat/conversation";
import { Composer } from "@/components/chat/composer";
import { messageQuestions, type ActiveQuestion } from "@/components/chat/question";
import { STAGES, activityLabel, stageIndex } from "@/components/chat/activity";
import { ApiError, api, post } from "@/lib/api";
import type {
  Document,
  Message,
  ModelCatalog,
  Project,
} from "@/lib/types";

export default function Conversation({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { ready } = useRequireAuth();
  const { health } = useSession();
  const router = useRouter();
  const toast = useToast();

  const [project, setProject] = useState<Project | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [choice, setChoice] = useState<{ model: string; effort: string } | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [action, setAction] = useState("");
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Message | null>(null);
  const [stopped, setStopped] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const [confirm, setConfirm] = useState<"delete" | "rerun" | null>(null);

  const generation = useRef<{
    requestId: string;
    controller: AbortController;
  } | null>(null);
  const retryDraft = useRef<{ content: string; request_id: string } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [p, m, d] = await Promise.all([
        api<Project>(`/projects/${id}`),
        api<Message[]>(`/projects/${id}/messages`),
        api<Document[]>(`/projects/${id}/documents`),
      ]);
      setProject(p);
      setMessages(m);
      setPending((current) =>
        m.some((saved) => saved.request_id === current?.request_id)
          ? null
          : current,
      );
      setDocuments(d);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (ready) void load();
  }, [ready, load]);

  useEffect(() => {
    if (!ready) return;
    api<ModelCatalog>("/models")
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, [ready]);

  // Saved stage and status updates arrive by polling while work is in flight.
  useEffect(() => {
    if (!project?.busy && !generationId) return;
    const timer = setInterval(() => void load(), 2500);
    return () => clearInterval(timer);
  }, [project?.busy, generationId, load]);

  const busy = !!action || !!project?.busy;
  const selection = choice ?? {
    model: project?.model || catalog?.default_model || "",
    effort: project?.effort || catalog?.default_effort || "low",
  };
  const effortSupported =
    catalog?.models.find((option) => option.id === selection.model)
      ?.supports_effort ?? true;

  async function chooseModel(next: { model: string; effort: string }) {
    const previous = selection;
    setChoice(next);
    try {
      await post(`/projects/${id}/model`, next);
      toast(
        next.model === previous.model
          ? `Effort set to ${next.effort}.`
          : `Model set to ${next.model}.`,
      );
    } catch (failure) {
      setChoice(previous);
      setError((failure as Error).message);
    }
  }

  async function perform(name: string, work: () => Promise<unknown>) {
    setAction(name);
    setError("");
    try {
      await work();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      await load();
      setAction("");
    }
  }

  async function upload(file?: File) {
    if (!file || busy) return;
    const limit = health?.max_upload_mb || 15;
    if (file.size > limit * 1024 * 1024) {
      setError(`Files must be ${limit} MB or smaller.`);
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
    const saved = retry ? retryDraft.current : null;
    const requestId = saved?.request_id || crypto.randomUUID();
    const text = saved?.content ?? content;
    const controller = new AbortController();
    generation.current = { requestId, controller };
    setGenerationId(requestId);
    setStopped(false);
    setAction("Thinking through your answer");
    setError("");
    if (text) {
      retryDraft.current = { content: text, request_id: requestId };
      setDraft("");
      if (!messages.some((message) => message.request_id === requestId)) {
        setPending({
          id: requestId,
          request_id: requestId,
          role: "user",
          content: text,
          created_at: new Date().toISOString(),
        });
      }
    }
    try {
      await post(
        `/projects/${id}/${text ? "chat" : "discovery/next"}`,
        { ...(text ? { content: text } : {}), request_id: requestId },
        controller.signal,
      );
      retryDraft.current = null;
    } catch (failure) {
      if (
        !controller.signal.aborted &&
        !(failure instanceof ApiError && failure.code === "generation_cancelled")
      ) {
        setError((failure as Error).message);
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
      if (pending) {
        const saved = await api<Message[]>(`/projects/${id}/messages`);
        if (!saved.some((message) => message.request_id === pending.request_id)) {
          setPending(null);
          setDraft((current) => current || pending.content);
        }
      }
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setStopping(false);
    }
  }, [id, project?.active_generation_id, stopping, load, pending]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" &&
        !event.defaultPrevented &&
        (generation.current || project?.active_generation_id)
      ) {
        event.preventDefault();
        void stop();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [stop, project?.active_generation_id]);

  if (!ready) return <Splash />;

  if (loading) {
    return (
      <Screen title="Loading…" back="/chats">
        <SkeletonBlocks />
      </Screen>
    );
  }

  if (!project) {
    return (
      <Screen title="Project" back="/chats">
        <div className="stack">
          <ErrorNote
            message={error || "That project could not be opened."}
            onRetry={() => {
              setError("");
              setLoading(true);
              void load();
            }}
          />
          <Link className="btn btn-secondary btn-block" href="/chats">
            Back to projects
          </Link>
        </div>
      </Screen>
    );
  }

  const shown =
    pending && !messages.some((message) => message.request_id === pending.request_id)
      ? [...messages, pending]
      : messages;

  const questionNumbers: Record<string, number> = {};
  for (const message of shown) {
    for (const question of messageQuestions(message)) {
      if (!questionNumbers[question.topic])
        questionNumbers[question.topic] = Object.keys(questionNumbers).length + 1;
    }
  }

  const latest = shown.at(-1);
  const openQuestions =
    latest && !project.analysis_ready ? messageQuestions(latest) : [];
  const activeQuestion: ActiveQuestion | undefined = openQuestions.length
    ? {
        questions: openQuestions,
        numbers: openQuestions.map(
          (question) => questionNumbers[question.topic],
        ),
        notice: latest?.question_notice,
      }
    : undefined;

  const started = shown.some((message) => message.role === "assistant");
  const awaitingReply =
    shown.at(-1)?.role === "user" && shown.length > 1 && !busy;
  const stage = stageIndex(project.status);

  return (
    <Screen
      variant="fill"
      title={project.name}
      subtitle={`${STAGES[stage]} · Stage ${stage + 1} of 5`}
      back="/chats"
      below={
        <div className="project-rail">
          <div className="project-stage-line" aria-label={`Project stage ${stage + 1} of 5`}>
            {STAGES.map((label, index) => (
              <span
                key={label}
                title={label}
                data-state={index < stage ? "done" : index === stage ? "active" : "next"}
              />
            ))}
          </div>
          <div className="project-rail-actions">
            <span><b>{STAGES[stage]}</b> in progress</span>
            <Link href={`/chat/${id}/documents`}>
              <FolderOpen size={14} /> {documents.length || "Add"} docs
            </Link>
            <Link href={`/chat/${id}/report`}>
              <ScrollText size={14} /> Report
            </Link>
          </div>
        </div>
      }
      actions={
        <button
          type="button"
          className="icon-btn"
          aria-label="Project options"
          onClick={() => setMenu(true)}
        >
          <MoreHorizontal size={22} />
        </button>
      }
    >
      <input
        ref={fileInput}
        type="file"
        hidden
        accept=".pdf,.docx,.pptx,.txt,.csv,.xlsx"
        onChange={(event) => void upload(event.target.files?.[0])}
      />

      <div className="chat">
        <Stream
          messages={shown}
          activeQuestionId={activeQuestion ? latest?.id : undefined}
          questionNumbers={questionNumbers}
          thinking={!stopped && (!!action || !!project.busy)}
          thinkingLabel={activityLabel({
            status: project.status,
            busy: !!project.busy,
            action,
            effort: selection.effort,
            stopping,
          })}
          onRetry={awaitingReply ? () => void generate(undefined, true) : undefined}
          empty={
            !started && shown.length <= 1 && !busy && !stopped ? (
              <Opener
                problem={project.initial_problem}
                busy={busy}
                compact={shown.length > 0}
                onBegin={() => void generate()}
                onExample={setDraft}
              />
            ) : undefined
          }
        />

        {(stopped ||
          (project.analysis_ready && !project.busy) ||
          !!error ||
          !!project.error ||
          !!project.retrieval_warnings?.length) && (
          <div className="chat-notes">
            {stopped && (
              <p className="note" role="status">
                Response stopped. Continue whenever you’re ready.
              </p>
            )}
            {project.analysis_ready && !project.busy && (
              <div className="ready">
                <CircleCheck size={18} aria-hidden="true" />
                <div>
                  <strong>Discovery complete. Your context is saved.</strong>
                  <p>
                    Next: diagnose the root problem, weigh the options, and review
                    the recommendation.
                  </p>
                </div>
                <div className="ready-actions">
                  {project.status === "BLUEPRINT_READY" && (
                    <Link
                      className="btn btn-secondary btn-sm"
                      href={`/chat/${id}/report`}
                    >
                      View report
                    </Link>
                  )}
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={busy}
                    onClick={() =>
                      project.status === "BLUEPRINT_READY"
                        ? setConfirm("rerun")
                        : void perform("Starting analysis", () =>
                            post(`/projects/${id}/analysis/run`),
                          )
                    }
                  >
                    Run analysis
                    <ArrowRight size={14} aria-hidden="true" />
                  </button>
                </div>
              </div>
            )}
            {error && (
              <div className="note note-danger" role="alert">
                <TriangleAlert size={15} aria-hidden="true" />
                <div className="stack" style={{ gap: 8 }}>
                  <span>{error}</span>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      setError("");
                      void generate(undefined, true);
                    }}
                  >
                    Try again
                  </button>
                </div>
              </div>
            )}
            {project.error && (
              <p className="note note-danger" role="alert">
                <TriangleAlert size={15} aria-hidden="true" />
                <span>{project.error}</span>
              </p>
            )}
            {project.retrieval_warnings?.map((warning) => (
              <p className="note" role="status" key={warning}>
                <FileText size={15} aria-hidden="true" />
                <span>{warning}</span>
              </p>
            ))}
          </div>
        )}

        <Composer
          value={draft}
          onChange={setDraft}
          onSubmit={() => {
            if (draft.trim()) void generate(draft.trim());
          }}
          busy={busy}
          sending={!!action}
          onStop={
            generationId || project.active_generation_id
              ? () => void stop()
              : undefined
          }
          stopping={stopping}
          projectId={id}
          documents={documents}
          documentsHref={`/chat/${id}/documents`}
          onUpload={() => fileInput.current?.click()}
          catalog={catalog}
          model={selection.model}
          effort={selection.effort}
          effortSupported={effortSupported}
          onModel={(model) => void chooseModel({ ...selection, model })}
          onEffort={(effort) => void chooseModel({ ...selection, effort })}
          question={activeQuestion}
        />
      </div>

      <Sheet open={menu} onClose={() => setMenu(false)} title={project.name}>
        <div className="sheet-body" style={{ display: "grid", gap: 4 }}>
          <Link className="sheet-option" href={`/chat/${id}/documents`}>
            <span>
              <FolderOpen size={16} aria-hidden="true" />
            </span>
            <span className="sheet-option-body">
              <strong>Documents</strong>
              <small>{documents.length} in this project</small>
            </span>
            <span />
          </Link>
          <Link className="sheet-option" href={`/chat/${id}/report`}>
            <span>
              <ScrollText size={16} aria-hidden="true" />
            </span>
            <span className="sheet-option-body">
              <strong>Analysis & blueprint</strong>
              <small>
                {project.status === "BLUEPRINT_READY"
                  ? "Ready to read"
                  : "Available after analysis"}
              </small>
            </span>
            <span />
          </Link>
          <button
            type="button"
            className="sheet-option"
            onClick={() => {
              setMenu(false);
              setConfirm("delete");
            }}
          >
            <span>
              <Trash2 size={16} aria-hidden="true" color="var(--danger)" />
            </span>
            <span className="sheet-option-body">
              <strong style={{ color: "var(--danger)" }}>Delete project</strong>
              <small>Removes messages, documents and blueprints</small>
            </span>
            <span />
          </button>
        </div>
      </Sheet>

      <ConfirmSheet
        open={confirm === "delete"}
        onClose={() => setConfirm(null)}
        title="Delete this project?"
        description={`“${project.name}” and all its messages, documents and blueprints will be permanently deleted. This cannot be undone.`}
        confirmLabel="Delete"
        danger
        onConfirm={async () => {
          await api(`/projects/${id}`, { method: "DELETE" });
          toast("Project deleted.");
          router.replace("/chats");
        }}
      />

      <ConfirmSheet
        open={confirm === "rerun"}
        onClose={() => setConfirm(null)}
        title="Run a fresh analysis?"
        description="New results replace the current analysis and blueprint. Export the current blueprint first if you want to keep a copy."
        confirmLabel="Run analysis"
        onConfirm={async () => {
          await post(`/projects/${id}/analysis/run`);
          toast("A fresh analysis is underway.");
          await load();
        }}
      />
    </Screen>
  );
}
