"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import {
  ArrowDown,
  ArrowRight,
  Check,
  Copy,
  RefreshCw,
} from "lucide-react";
import { T } from "@/components/locale";
import { MessageText } from "@/components/discovery/message-text";
import type { Message } from "@/lib/types";
import mark from "@/public/brand/logo-mark.png";

function AssistantMark({ large = false }: { large?: boolean }) {
  return (
    <span className={large ? "dx-empty-mark" : "dx-mark"} aria-hidden="true">
      <Image src={mark} alt="" sizes={large ? "24px" : "14px"} />
    </span>
  );
}

const time = (value: string) =>
  new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

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
      className="dx-msg-action"
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
      {copied ? <Check size={14} /> : <Copy size={14} />}
      <span>{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

function MessageActions({
  content,
  onRetry,
}: {
  content: string;
  onRetry?: () => void;
}) {
  return (
    <div className="dx-msg-actions">
      <CopyButton content={content} />
      {onRetry && (
        <button
          type="button"
          className="dx-msg-action"
          aria-label="Retry response to your saved answer"
          onClick={onRetry}
        >
          <RefreshCw size={14} />
          <span>
            <T text={"Retry"} />
          </span>
        </button>
      )}
    </div>
  );
}

export function AssistantMessage({
  message,
}: {
  message: Message;
}) {
  return (
    <article className="dx-msg dx-msg-assistant" aria-label="Assistant response">
      <div className="dx-msg-head">
        <AssistantMark />
        <span className="dx-msg-time">{time(message.created_at)}</span>
      </div>
      <div className="dx-prose">
        <MessageText content={message.content} />
      </div>
      <MessageActions content={message.content} />
    </article>
  );
}

export function UserMessage({
  message,
  onRetry,
}: {
  message: Message;
  onRetry?: () => void;
}) {
  return (
    <article className="dx-msg dx-msg-user">
      <div className="dx-msg-head">
        <span className="dx-msg-time">{time(message.created_at)}</span>
        <strong>
          <T text={"You"} />
        </strong>
      </div>
      <div className="dx-bubble">
        <div className="dx-prose">
          <MessageText content={message.content} />
        </div>
      </div>
      <MessageActions content={message.content} onRetry={onRetry} />
    </article>
  );
}

export function TypingIndicator({ label }: { label?: string }) {
  return (
    <div className="dx-typing" role="status" aria-live="polite" aria-atomic="true">
      <AssistantMark />
      <span className="dx-typing-label"><T text={label || "Thinking"} />…</span>
    </div>
  );
}

const examples = [
  "Reduce our patient waiting time",
  "Automate employee leave approvals",
  "Improve EV charging availability",
];

export function EmptyConversation({
  problem,
  busy,
  compact,
  onBegin,
  onExample,
}: {
  problem?: string;
  busy: boolean;
  /** True when the project already carries a message, so examples are noise. */
  compact?: boolean;
  onBegin: () => void;
  onExample: (text: string) => void;
}) {
  const suggestions = problem
    ? [
        problem.length > 64 ? `${problem.slice(0, 64).trimEnd()}…` : problem,
        ...examples,
      ].slice(0, 3)
    : examples;
  return (
    <div className="dx-empty">
      <AssistantMark large />
      <h2>
        <T text={"What are you trying to improve?"} />
      </h2>
      <p>
        <T
          text={
            "Tell me what happens today. I’ll understand the system before recommending a solution."
          }
        />
      </p>
      <button
        type="button"
        className="button button-primary"
        disabled={busy}
        onClick={onBegin}
      >
        {busy ? "Preparing…" : "Begin the conversation"}
        <ArrowRight size={16} />
      </button>
      {!compact && (
        <>
          <div className="dx-examples">
            {suggestions.map((example) => (
              <button
                key={example}
                type="button"
                className="dx-example"
                onClick={() => onExample(example)}
              >
                <span>{example}</span>
                <ArrowRight size={14} />
              </button>
            ))}
          </div>
          <small>
            <T
              text={
                "Examples fill the composer — nothing is sent until you do."
              }
            />
          </small>
        </>
      )}
      {compact && (
        <small>
          <T
            text={
              "Your problem statement is saved below. Begin whenever you’re ready."
            }
          />
        </small>
      )}
    </div>
  );
}

/**
 * The conversation is the page: it owns its own scroll region so the composer
 * stays reachable, and it only follows new messages when the reader is already
 * at the latest one.
 */
export function ConversationStream({
  messages,
  thinking,
  thinkingLabel,
  onRetry,
  children,
  empty,
}: {
  messages: Message[];
  thinking: boolean;
  thinkingLabel?: string;
  onRetry?: () => void;
  children?: React.ReactNode;
  empty?: React.ReactNode;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const anchor = useRef<HTMLDivElement>(null);
  const seen = useRef(0);
  const settled = useRef(false);
  const [pinned, setPinned] = useState(true);
  const [unseen, setUnseen] = useState(false);

  const toBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const reduce = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    anchor.current?.scrollIntoView({
      behavior: reduce ? "instant" : behavior,
      block: "end",
    });
    setUnseen(false);
  }, []);

  useEffect(() => {
    const node = scroller.current;
    if (!node) return;
    const onScroll = () => {
      const distance = node.scrollHeight - node.scrollTop - node.clientHeight;
      const bottom = distance < 90;
      setPinned(bottom);
      if (bottom) setUnseen(false);
    };
    onScroll();
    node.addEventListener("scroll", onScroll, { passive: true });
    return () => node.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!settled.current) {
      // First paint of a saved transcript starts at the newest message.
      settled.current = true;
      seen.current = messages.length;
      toBottom("instant");
      return;
    }
    if (messages.length === seen.current) return;
    const grew = messages.length > seen.current;
    seen.current = messages.length;
    if (!grew) return;
    if (pinned || (thinking && messages.at(-1)?.role === "user")) toBottom();
    else setUnseen(true);
  }, [messages, pinned, thinking, toBottom]);

  return (
    <div className="dx-stream-wrap">
      <div className="dx-stream" ref={scroller} tabIndex={-1}>
        <div className="dx-stream-inner">
          {empty}
          {messages.map((message) =>
            message.role === "assistant" ? (
              <AssistantMessage
                key={message.id}
                message={message}
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
          {thinking && <TypingIndicator label={thinkingLabel} />}
          {children}
          <div ref={anchor} className="dx-anchor" />
        </div>
      </div>
      {unseen && (
        <button
          type="button"
          className="dx-jump"
          onClick={() => toBottom()}
          aria-label="Jump to latest message"
        >
          <ArrowDown size={14} />
          <T text={"Jump to latest"} />
        </button>
      )}
    </div>
  );
}
