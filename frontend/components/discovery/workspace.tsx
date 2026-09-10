"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, CircleCheck, FileText, TriangleAlert } from "lucide-react";
import { T } from "@/components/locale";
import { ChatHeader } from "@/components/discovery/chat-header";
import { ChatComposer } from "@/components/discovery/composer";
import { ContextPanel } from "@/components/discovery/context-panel";
import {
  ConversationStream,
  EmptyConversation,
} from "@/components/discovery/conversation";
import { useMediaQuery } from "@/components/ui/popover";
import { activityLabel } from "@/components/discovery/activity";
import type { Document, Message, ModelCatalog, Project } from "@/lib/types";

/**
 * Discovery workspace.
 *
 * Purely presentational: every request still runs in the project page, which
 * owns the API calls, polling and project state. This component decides only
 * how the conversation, composer and context are arranged.
 */
export function DiscoveryWorkspace({
  project,
  messages,
  documents,
  catalog,
  model,
  effort,
  effortSupported,
  busy,
  action,
  stopped,
  stopping,
  onStop,
  error,
  message,
  onMessage,
  onSend,
  onBegin,
  onRetry,
  onUpload,
  onRunAnalysis,
  onDelete,
  onModel,
  onEffort,
  onDismissError,
}: {
  project: Project;
  messages: Message[];
  documents: Document[];
  catalog: ModelCatalog | null;
  model: string;
  effort: string;
  effortSupported: boolean;
  busy: boolean;
  action: string;
  stopped: boolean;
  stopping: boolean;
  onStop?: () => void;
  error: string;
  message: string;
  onMessage: (value: string) => void;
  onSend: () => void;
  onBegin: () => void;
  onRetry: () => void;
  onUpload: () => void;
  onRunAnalysis: () => void;
  onDelete: () => void;
  onModel: (id: string) => void;
  onEffort: (id: string) => void;
  onDismissError: () => void;
}) {
  const [contextOpen, setContextOpen] = useState(false);
  const wide = useMediaQuery("(min-width: 1280px)");
  const overlay = contextOpen && !wide;
  const documentsHref = `/project/${project.id}/documents`;
  const started = messages.some((m) => m.role === "assistant");
  const awaitingReply =
    messages.at(-1)?.role === "user" && messages.length > 1 && !busy;

  useEffect(() => {
    if (!overlay) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setContextOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [overlay]);

  return (
    <div className={`dx-workspace ${contextOpen ? "context-open" : ""}`}>
      <ChatHeader
        project={project}
        documentCount={documents.length}
        contextOpen={contextOpen}
        onToggleContext={() => setContextOpen(!contextOpen)}
        onDelete={onDelete}
      />
      <div className="dx-body">
        <div className="dx-conversation">
          <ConversationStream
            messages={messages}
            thinking={!stopped && (!!action || !!project.busy)}
            thinkingLabel={activityLabel({ status: project.status, busy: project.busy, action, effort, stopping })}
            onRetry={awaitingReply ? onRetry : undefined}
            empty={
              !started && messages.length <= 1 && !busy && !stopped ? (
                <EmptyConversation
                  problem={project.initial_problem}
                  busy={busy}
                  compact={messages.length > 0}
                  onBegin={onBegin}
                  onExample={onMessage}
                />
              ) : undefined
            }
          />
          <div className="dx-footer">
            {stopped && <p className="dx-stopped" role="status">Response stopped. You can continue whenever you’re ready.</p>}
            {project.analysis_ready && !project.busy && (
              <div className="ready-banner dx-ready">
                <CircleCheck size={17} />
                <div>
                  <strong>
                    <T text={"Discovery complete. Your context is saved."} />
                  </strong>
                  <span>
                    <T
                      text={
                        "Next: diagnose the root problem, weigh the options, and review the recommendation."
                      }
                    />
                  </span>
                </div>
                {project.status === "BLUEPRINT_READY" && (
                  <Link
                    href={`/project/${project.id}/analysis`}
                    className="dx-text-link"
                  >
                    <T text={"View analysis"} />
                    <ArrowRight size={14} />
                  </Link>
                )}
                <button
                  type="button"
                  className="button button-primary button-sm"
                  disabled={busy}
                  onClick={onRunAnalysis}
                >
                  <T text={"Run analysis"} />
                  <ArrowRight size={14} />
                </button>
              </div>
            )}
            {error && (
              <p className="dx-alert" role="alert">
                <TriangleAlert size={14} aria-hidden />
                <span>{error}</span>
                <button type="button" disabled={busy} onClick={onDismissError}>
                  <T text={"Try again"} />
                </button>
              </p>
            )}
            {project.error && (
              <p className="dx-alert" role="alert">
                <TriangleAlert size={14} aria-hidden />
                <span>{project.error}</span>
              </p>
            )}
            {project.retrieval_warnings?.map((warning) => (
              <p className="dx-alert dx-alert-note" role="status" key={warning}>
                <FileText size={14} aria-hidden />
                <span>{warning}</span>
              </p>
            ))}
            <ChatComposer
              value={message}
              onChange={onMessage}
              onSubmit={onSend}
              busy={busy}
              sending={!!action}
              onStop={onStop}
              stopping={stopping}
              projectId={project.id}
              documents={documents}
              documentsHref={documentsHref}
              onUpload={onUpload}
              catalog={catalog}
              model={model}
              effort={effort}
              effortSupported={effortSupported}
              onModel={onModel}
              onEffort={onEffort}
            />
          </div>
        </div>
        {contextOpen && (
          <>
            {overlay && (
              <button
                type="button"
                className="dx-context-scrim"
                aria-label="Close context panel"
                onClick={() => setContextOpen(false)}
              />
            )}
            <ContextPanel
              project={project}
              documents={documents}
              documentsHref={documentsHref}
              overlay={overlay}
              onClose={() => setContextOpen(false)}
              onUpload={onUpload}
            />
          </>
        )}
      </div>
    </div>
  );
}
