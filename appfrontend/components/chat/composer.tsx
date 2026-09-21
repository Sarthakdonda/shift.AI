"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUp,
  Check,
  ExternalLink,
  FileText,
  FolderOpen,
  Gauge,
  Plus,
  Sparkles,
  Square,
  Upload,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  Document,
  ModelCatalog,
  Usage,
} from "@/lib/types";
import { Sheet } from "@/components/ui/sheet";
import { QuestionContent, type ActiveQuestion } from "./question";

function UsageSheet({
  projectId,
  model,
  busy,
}: {
  projectId: string;
  model: string;
  busy: boolean;
}) {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const controller = new AbortController();
    const refresh = () =>
      api<Usage>(`/projects/${projectId}/usage`, { signal: controller.signal })
        .then((data) => {
          if (controller.signal.aborted) return;
          setUsage(data);
          setFailed(false);
        })
        .catch(() => {
          if (controller.signal.aborted) return;
          setUsage(null);
          setFailed(true);
        });
    void refresh();
    const timer = setInterval(
      () => {
        if (!document.hidden) void refresh();
      },
      busy ? 5000 : 30000,
    );
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [projectId, model, busy]);

  useEffect(() => {
    if (!usage?.retry_at) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [usage?.retry_at]);

  const seconds = usage?.retry_at
    ? Math.max(0, Math.ceil((Date.parse(usage.retry_at) - now) / 1000))
    : null;
  const countdown =
    seconds === null
      ? ""
      : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  const label = !usage
    ? failed
      ? "Usage unavailable"
      : "Usage & limits"
    : usage.status === "available"
      ? "Usage & limits"
      : usage.status === "not_configured"
        ? "API not connected"
        : seconds
          ? `Retry in ${countdown}`
          : "Checking availability";

  return (
    <>
      <button
        type="button"
        className="usage-btn"
        data-limited={usage?.status === "rate_limited" ? "true" : undefined}
        onClick={() => setOpen(true)}
      >
        <Activity size={12} aria-hidden="true" />
        <span>{label}</span>
      </button>
      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title="Usage & limits"
        description={model || "Selected model"}
      >
        <div className="sheet-body stack">
          {usage ? (
            <>
              <div className="kv">
                <div>
                  <strong>Available connections</strong>
                  <p>
                    {usage.available_connections} / {usage.configured_connections}
                  </p>
                </div>
                <div>
                  <strong>Messages remaining</strong>
                  <p>{usage.remaining_requests ?? "Not reported by the provider"}</p>
                </div>
                <div>
                  <strong>Quota refill</strong>
                  <p>
                    {usage.reset_at
                      ? new Date(usage.reset_at).toLocaleString()
                      : "See the provider dashboard"}
                  </p>
                </div>
                {seconds !== null && (
                  <div>
                    <strong>Next retry</strong>
                    <p>{seconds ? countdown : "Ready to retry"}</p>
                  </div>
                )}
              </div>
              <p className="field-note">{usage.quota_note}</p>
              <p className="field-note">
                Backup connections keep your selected model. Keys in the same
                Google project share a quota.
              </p>
            </>
          ) : (
            <p className="field-note">
              Usage could not be loaded. Your provider’s dashboard has the latest
              limits.
            </p>
          )}
          <a
            className="btn btn-secondary btn-block"
            href="https://aistudio.google.com/usage?tab=rate-limit"
            target="_blank"
            rel="noreferrer"
          >
            View provider usage
            <ExternalLink size={15} aria-hidden="true" />
          </a>
        </div>
      </Sheet>
    </>
  );
}

function ModelSheet({
  catalog,
  model,
  effort,
  effortSupported,
  disabled,
  onModel,
  onEffort,
}: {
  catalog: ModelCatalog;
  model: string;
  effort: string;
  effortSupported: boolean;
  disabled: boolean;
  onModel: (id: string) => void;
  onEffort: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const active = catalog.models.find((option) => option.id === model);
  return (
    <>
      <button
        type="button"
        className="pill-btn"
        disabled={disabled}
        onClick={() => setOpen(true)}
        aria-label="Model and response effort"
      >
        <Sparkles size={14} aria-hidden="true" />
        <span>{active?.label || "Model"}</span>
      </button>
      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title="Model & effort"
        description="Your choice is saved on this project and applies to discovery, analysis and deliverables."
      >
        <div className="sheet-body stack">
          <div className="stack" style={{ gap: 4 }}>
            <p className="eyebrow">Model</p>
            {catalog.models.map((option) => (
              <button
                type="button"
                className="sheet-option"
                key={option.id}
                data-selected={option.id === model ? "true" : undefined}
                onClick={() => {
                  onModel(option.id);
                  setOpen(false);
                }}
              >
                <span>
                  <Sparkles size={15} aria-hidden="true" />
                </span>
                <span className="sheet-option-body">
                  <strong>{option.label}</strong>
                  <small>{option.description}</small>
                </span>
                {option.id === model ? (
                  <Check size={16} aria-hidden="true" />
                ) : (
                  <span />
                )}
              </button>
            ))}
          </div>
          <div className="stack" style={{ gap: 4 }}>
            <p className="eyebrow">Response effort</p>
            {!effortSupported && (
              <p className="field-note">
                This model does not accept a thinking option, so effort is ignored.
              </p>
            )}
            {catalog.efforts.map((option) => (
              <button
                type="button"
                className="sheet-option"
                key={option.id}
                data-selected={option.id === effort ? "true" : undefined}
                disabled={!effortSupported}
                onClick={() => {
                  onEffort(option.id);
                  setOpen(false);
                }}
              >
                <span>
                  <Gauge size={15} aria-hidden="true" />
                </span>
                <span className="sheet-option-body">
                  <strong>{option.label}</strong>
                  <small>{option.description}</small>
                </span>
                {option.id === effort ? (
                  <Check size={16} aria-hidden="true" />
                ) : (
                  <span />
                )}
              </button>
            ))}
          </div>
        </div>
      </Sheet>
    </>
  );
}

function ContextSheet({
  documents,
  documentsHref,
  disabled,
  onUpload,
}: {
  documents: Document[];
  documentsHref: string;
  disabled: boolean;
  onUpload: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        className="icon-btn"
        disabled={disabled}
        aria-label="Add context"
        onClick={() => setOpen(true)}
      >
        <Plus size={20} />
      </button>
      <Sheet open={open} onClose={() => setOpen(false)} title="Add context">
        <div className="sheet-body stack" style={{ gap: 4 }}>
          <button
            type="button"
            className="sheet-option"
            onClick={() => {
              setOpen(false);
              onUpload();
            }}
          >
            <span>
              <Upload size={16} aria-hidden="true" />
            </span>
            <span className="sheet-option-body">
              <strong>Upload a document</strong>
              <small>PDF, DOCX, PPTX, TXT, CSV, XLSX</small>
            </span>
            <span />
          </button>
          <Link
            className="sheet-option"
            href={documentsHref}
          >
            <span>
              <FolderOpen size={16} aria-hidden="true" />
            </span>
            <span className="sheet-option-body">
              <strong>Project documents</strong>
              <small>{documents.length} already in this project</small>
            </span>
            <span />
          </Link>
          <p className="field-note" style={{ padding: "6px 6px 0" }}>
            New evidence refreshes discovery and resets earlier analysis.
          </p>
        </div>
      </Sheet>
    </>
  );
}

/**
 * The composer is the answer surface. With an open discovery question it shows
 * the question above the field and swaps send for an explicit submit, so
 * answering never feels like guessing what the field is for.
 */
export function Composer({
  value,
  onChange,
  onSubmit,
  busy,
  sending,
  onStop,
  stopping,
  projectId,
  documents,
  documentsHref,
  onUpload,
  catalog,
  model,
  effort,
  effortSupported,
  onModel,
  onEffort,
  question,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
  sending: boolean;
  onStop?: () => void;
  stopping: boolean;
  projectId: string;
  documents: Document[];
  documentsHref: string;
  onUpload: () => void;
  catalog: ModelCatalog | null;
  model: string;
  effort: string;
  effortSupported: boolean;
  onModel: (id: string) => void;
  onEffort: (id: string) => void;
  question?: ActiveQuestion;
}) {
  const questionId = useId();
  const field = useRef<HTMLTextAreaElement>(null);

  const resize = useCallback(() => {
    const node = field.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${node.scrollHeight}px`;
  }, []);

  useEffect(resize, [value, resize]);

  const ready = !!value.trim() && !busy;

  return (
    <div className="composer-wrap">
      <form
        className="composer"
        data-question={question ? "true" : undefined}
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) onSubmit();
        }}
      >
        {question && <QuestionContent {...question} headingId={questionId} />}
        {!!documents.length && !question && (
          <div className="attached" aria-label="Documents in this project">
            {documents.slice(0, 3).map((document) => (
              <Link
                className="doc-chip"
                href={documentsHref}
                key={document.id}
                title={document.filename}
              >
                <FileText size={12} aria-hidden="true" />
                <span>{document.filename}</span>
              </Link>
            ))}
            {documents.length > 3 && (
              <Link className="doc-chip" href={documentsHref}>
                +{documents.length - 3}
              </Link>
            )}
          </div>
        )}
        <div className="composer-field">
          <textarea
            ref={field}
            rows={1}
            maxLength={12000}
            value={value}
            aria-label={question ? "Your answer" : "Your message"}
            aria-describedby={question ? questionId : undefined}
            placeholder={
              question
                ? "Answer in your own words…"
                : "Ask about your current process…"
            }
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing &&
                // On a phone Enter is a newline; sending stays an explicit tap.
                window.matchMedia("(pointer: fine)").matches
              ) {
                event.preventDefault();
                if (ready) onSubmit();
              }
            }}
          />
        </div>
        <div className="composer-bar">
          <div className="composer-left">
            <ContextSheet
              documents={documents}
              documentsHref={documentsHref}
              disabled={busy}
              onUpload={onUpload}
            />
            {catalog && (
              <ModelSheet
                catalog={catalog}
                model={model}
                effort={effort}
                effortSupported={effortSupported}
                disabled={busy}
                onModel={onModel}
                onEffort={onEffort}
              />
            )}
          </div>
          <div className="composer-right">
            {onStop ? (
              <button
                type="button"
                className="send send-stop"
                disabled={stopping}
                aria-label="Stop response"
                onClick={onStop}
              >
                <Square size={12} fill="currentColor" aria-hidden="true" />
              </button>
            ) : (
              !question && (
                <button
                  type="submit"
                  className="send"
                  data-ready={ready ? "true" : undefined}
                  disabled={!ready}
                  aria-label="Send message"
                >
                  <ArrowUp size={19} aria-hidden="true" />
                </button>
              )
            )}
          </div>
        </div>
        {question && !onStop && (
          <button type="submit" className="submit-answer" disabled={!ready}>
            Submit answer
            <ArrowRight size={16} aria-hidden="true" />
          </button>
        )}
      </form>
      <div className="composer-hint">
        <span>{onStop ? "Tap stop to cancel" : "Your answers are saved"}</span>
        <UsageSheet
          projectId={projectId}
          model={model}
          busy={busy || sending}
        />
      </div>
    </div>
  );
}
