"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowRight, Check, Copy, RotateCcw } from "lucide-react";
import { clock } from "@/lib/api";
import type { Message } from "@/lib/types";
import { BrandMark } from "@/components/ui/states";
import { MessageText } from "./message-text";
import { QuestionCard, messageQuestions } from "./question";

function CopyButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1600);
    return () => clearTimeout(timer);
  }, [copied]);
  return (
    <button
      type="button"
      className="msg-action"
      aria-label={copied ? "Copied to clipboard" : "Copy message"}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(content);
          setCopied(true);
        } catch {
          setCopied(false);
        }
      }}
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      <span>{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

function Actions({
  content,
  onRetry,
}: {
  content: string;
  onRetry?: () => void;
}) {
  return (
    <div className="msg-actions">
      <CopyButton content={content} />
      {onRetry && (
        <button
          type="button"
          className="msg-action"
          aria-label="Retry response to your saved answer"
          onClick={onRetry}
        >
          <RotateCcw size={13} />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}

function AssistantMessage({
  message,
  numbers,
}: {
  message: Message;
  numbers: Record<string, number>;
}) {
  const questions = messageQuestions(message);
  return (
    <article className="msg msg-assistant" aria-label="Assistant response">
      <div className="msg-head">
        <BrandMark />
        <span>shift.AI</span>
        <span aria-hidden="true">·</span>
        <span>{clock(message.created_at)}</span>
      </div>
      {questions.length ? (
        <QuestionCard
          questions={questions}
          numbers={questions.map((question) => numbers[question.topic] || 1)}
          notice={message.question_notice}
        />
      ) : (
        <div className="prose selectable">
          <MessageText content={message.content} />
        </div>
      )}
      <Actions content={message.content} />
    </article>
  );
}

function UserMessage({
  message,
  onRetry,
}: {
  message: Message;
  onRetry?: () => void;
}) {
  return (
    <article className="msg msg-user" aria-label="Your message">
      <div className="msg-head">
        <strong>You</strong>
        <span aria-hidden="true">·</span>
        <span>{clock(message.created_at)}</span>
      </div>
      <div className="bubble">
        <div className="prose selectable">
          <MessageText content={message.content} />
        </div>
      </div>
      <Actions content={message.content} onRetry={onRetry} />
    </article>
  );
}

export function Typing({ label }: { label?: string }) {
  return (
    <div className="typing" role="status" aria-live="polite" aria-atomic="true">
      <BrandMark />
      <span>{label || "Thinking"}</span>
      <span className="typing-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
    </div>
  );
}

const EXAMPLES = [
  "Reduce our patient waiting time",
  "Automate employee leave approvals",
  "Improve EV charging availability",
];

export function Opener({
  problem,
  busy,
  compact,
  onBegin,
  onExample,
}: {
  problem?: string;
  busy: boolean;
  compact?: boolean;
  onBegin: () => void;
  onExample: (text: string) => void;
}) {
  const suggestions = problem
    ? [
        problem.length > 64 ? `${problem.slice(0, 64).trimEnd()}…` : problem,
        ...EXAMPLES,
      ].slice(0, 3)
    : EXAMPLES;
  return (
    <div className="opener">
      <BrandMark large />
      <h2>What are you trying to improve?</h2>
      <p>
        Tell me what happens today. I’ll understand the system before
        recommending a solution.
      </p>
      <button
        type="button"
        className="btn btn-primary"
        disabled={busy}
        onClick={onBegin}
      >
        {busy ? "Preparing…" : "Begin the conversation"}
        <ArrowRight size={16} aria-hidden="true" />
      </button>
      {compact ? (
        <small>Your problem statement is saved. Begin whenever you’re ready.</small>
      ) : (
        <>
          <div className="suggestions">
            {suggestions.map((example) => (
              <button
                className="suggestion"
                key={example}
                type="button"
                onClick={() => onExample(example)}
              >
                <span>{example}</span>
                <ArrowRight size={15} aria-hidden="true" />
              </button>
            ))}
          </div>
          <small>Examples fill the composer — nothing is sent until you do.</small>
        </>
      )}
    </div>
  );
}

/**
 * One scroll region owns the transcript. It follows new messages only while the
 * reader is already at the latest one, so reading history is never interrupted.
 */
export function Stream({
  messages,
  thinking,
  thinkingLabel,
  onRetry,
  empty,
  activeQuestionId,
  questionNumbers,
}: {
  messages: Message[];
  thinking: boolean;
  thinkingLabel?: string;
  onRetry?: () => void;
  empty?: React.ReactNode;
  activeQuestionId?: string;
  questionNumbers: Record<string, number>;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const anchor = useRef<HTMLDivElement>(null);
  const seen = useRef(0);
  const settled = useRef(false);
  const pinned = useRef(true);
  const [unseen, setUnseen] = useState(false);

  const toBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    anchor.current?.scrollIntoView({
      behavior: reduce ? "instant" : behavior,
      block: "end",
    });
    setUnseen(false);
  }, []);

  useEffect(() => {
    const node = scroller.current;
    if (!node) return;
    // Scroll position lives in a ref: tracking it in state would re-render the
    // whole transcript on every frame of a flick.
    const onScroll = () => {
      const distance = node.scrollHeight - node.scrollTop - node.clientHeight;
      const bottom = distance < 90;
      pinned.current = bottom;
      if (bottom) setUnseen((current) => (current ? false : current));
    };
    onScroll();
    node.addEventListener("scroll", onScroll, { passive: true });
    return () => node.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const node = scroller.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    // The keyboard opening, a status note appearing or the composer growing all
    // shrink this region. Staying pinned keeps the newest message in view
    // instead of letting it slide under the composer.
    const observer = new ResizeObserver(() => {
      if (pinned.current) toBottom("instant");
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [toBottom]);

  useEffect(() => {
    if (!settled.current) {
      settled.current = true;
      seen.current = messages.length;
      toBottom("instant");
      return;
    }
    if (messages.length <= seen.current) {
      seen.current = messages.length;
      return;
    }
    seen.current = messages.length;
    if (pinned.current || (thinking && messages.at(-1)?.role === "user"))
      toBottom();
    else setUnseen(true);
  }, [messages, thinking, toBottom]);

  return (
    <div className="stream-wrap">
      <div className="stream" ref={scroller} tabIndex={-1}>
        <div className="stream-inner">
          {empty}
          {messages
            .filter((message) => message.id !== activeQuestionId)
            .map((message) =>
              message.role === "assistant" ? (
                <AssistantMessage
                  key={message.id}
                  message={message}
                  numbers={questionNumbers}
                />
              ) : (
                <UserMessage
                  key={message.id}
                  message={message}
                  onRetry={
                    onRetry && message.id === messages.at(-1)?.id
                      ? onRetry
                      : undefined
                  }
                />
              ),
            )}
          {thinking && <Typing label={thinkingLabel} />}
          <div className="anchor" ref={anchor} />
        </div>
      </div>
      {unseen && (
        <button
          type="button"
          className="jump"
          onClick={() => toBottom()}
          aria-label="Jump to latest message"
        >
          <ArrowDown size={14} aria-hidden="true" />
          Latest
        </button>
      )}
    </div>
  );
}
