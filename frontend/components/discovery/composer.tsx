"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  FileText,
  FolderOpen,
  Square,
  Plus,
  TriangleAlert,
  Upload,
  X,
} from "lucide-react";
import { T } from "@/components/locale";
import { Popover } from "@/components/ui/popover";
import {
  ModelSelector,
  ResponseModeSelector,
} from "@/components/discovery/model-controls";
import { VoiceInputButton } from "@/components/discovery/voice-input";
import { UsageIndicator } from "@/components/discovery/usage-indicator";
import type { Document, ModelCatalog } from "@/lib/types";

/**
 * The composer is the second-most important surface after the conversation:
 * one calm container, controls that only appear when they are useful, and the
 * same send/upload/model logic the page already used.
 */
export function ChatComposer({
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
}) {
  const field = useRef<HTMLTextAreaElement>(null);
  const [listening, setListening] = useState(false);
  const [voiceError, setVoiceError] = useState("");

  const resize = useCallback(() => {
    const node = field.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 260)}px`;
  }, []);

  useEffect(resize, [value, resize]);

  const onVoiceStatus = useCallback(
    (status: { listening: boolean; error?: string }) => {
      setListening(status.listening);
      if (status.error) setVoiceError(status.error);
      else if (status.listening) setVoiceError("");
    },
    [],
  );

  const onTranscript = useCallback(
    (text: string) => {
      if (text) onChange(text);
      field.current?.focus();
    },
    [onChange],
  );

  const ready = !!value.trim() && !busy;

  return (
    <div className="dx-composer-wrap">
      <form
        className={`dx-composer ${listening ? "is-listening" : ""}`}
        onSubmit={(event) => {
          event.preventDefault();
          if (!ready) return;
          onSubmit();
        }}
      >
        {!!documents.length && (
          <div className="dx-attached" aria-label="Documents in this project">
            {documents.slice(0, 3).map((document) => (
              <Link
                key={document.id}
                href={documentsHref}
                className="dx-doc-chip"
                title={document.filename}
              >
                <FileText size={12} />
                <span>{document.filename}</span>
              </Link>
            ))}
            {documents.length > 3 && (
              <Link href={documentsHref} className="dx-doc-chip">
                +{documents.length - 3}
              </Link>
            )}
          </div>
        )}
        <textarea
          ref={field}
          aria-label="Your message"
          rows={1}
          maxLength={12000}
          value={value}
          placeholder="Ask shift.AI about your current process…"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              event.preventDefault();
              if (ready) onSubmit();
            }
          }}
        />
        <div className="dx-composer-bar">
          <div className="dx-composer-left">
            <Popover
              label="Add context"
              align="start"
              width={268}
              className="dx-pop-menu"
              trigger={(props) => (
                <button
                  {...props}
                  type="button"
                  className="dx-icon-button"
                  disabled={busy}
                  aria-label="Add context"
                  title="Add context"
                >
                  <Plus size={18} />
                </button>
              )}
            >
              {(close) => (
                <>
                  <p className="dx-pop-label">
                    <T text={"Add context"} />
                  </p>
                  <button
                    type="button"
                    className="dx-pop-option"
                    onClick={() => {
                      close();
                      onUpload();
                    }}
                  >
                    <span>
                      <strong>
                        <Upload size={14} />
                        <T text={"Upload a document"} />
                      </strong>
                      <small>
                        <T text={"PDF, DOCX, PPTX, TXT, CSV, XLSX"} />
                      </small>
                    </span>
                  </button>
                  <Link
                    className="dx-pop-option"
                    href={documentsHref}
                    onClick={() => close()}
                  >
                    <span>
                      <strong>
                        <FolderOpen size={14} />
                        <T text={"Project documents"} />
                      </strong>
                      <small>
                        {documents.length}
                        <T text={" already in this project"} />
                      </small>
                    </span>
                  </Link>
                  <p className="dx-pop-hint">
                    <T
                      text={
                        "New evidence refreshes discovery and resets earlier analysis."
                      }
                    />
                  </p>
                </>
              )}
            </Popover>
            {catalog && (
              <>
                <ModelSelector
                  models={catalog.models}
                  model={model}
                  disabled={busy}
                  onSelect={onModel}
                />
                <ResponseModeSelector
                  efforts={catalog.efforts}
                  effort={effort}
                  supported={effortSupported}
                  disabled={busy}
                  onSelect={onEffort}
                />
              </>
            )}
          </div>
          <div className="dx-composer-right">
            {listening && (
              <span className="dx-listening" role="status">
                <span className="dx-listening-dot" aria-hidden />
                <T text={"Listening…"} />
              </span>
            )}
            <VoiceInputButton
              disabled={busy}
              onTranscript={onTranscript}
              onStatus={onVoiceStatus}
            />
            {onStop ? (
              <button type="button" className="dx-send dx-stop" onClick={onStop} disabled={stopping} aria-label="Stop response" title="Stop response (Esc)">
                <Square size={13} fill="currentColor" />
              </button>
            ) : (
              <button type="submit" className="dx-send" disabled={!ready} aria-label="Send message" title="Send message">
                <ArrowUp size={18} />
              </button>
            )}
          </div>
        </div>
      </form>
      {voiceError && (
        <p className="dx-composer-alert" role="alert">
          <TriangleAlert size={13} aria-hidden />
          {voiceError}
          <button
            type="button"
            aria-label="Dismiss voice input message"
            onClick={() => setVoiceError("")}
          >
            <X size={13} />
          </button>
        </p>
      )}
      <div className="dx-composer-hint">
        <span>
          <T text={onStop ? "Esc to stop · Shift + Enter for a new line" : "Enter to send · Shift + Enter for a new line"} />
        </span>
        <UsageIndicator projectId={projectId} model={model} busy={busy || sending} />
      </div>
    </div>
  );
}
