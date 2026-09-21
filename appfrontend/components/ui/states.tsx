"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowRight, RefreshCw, TriangleAlert } from "lucide-react";
import mark from "@/public/brand/logo-mark.png";

export function BrandMark({ large }: { large?: boolean }) {
  return (
    <span className={large ? "mark mark-lg" : "mark"} aria-hidden="true">
      <Image src={mark} alt="" sizes={large ? "32px" : "13px"} priority={large} />
    </span>
  );
}

export function Splash({ message }: { message?: string }) {
  return (
    <div className="boot" role="status" aria-live="polite">
      <span className="boot-mark">
        <Image src={mark} alt="" sizes="40px" priority />
      </span>
      <p>{message || "Opening your workspace…"}</p>
    </div>
  );
}

/** Content-shaped placeholders: no spinner, no layout shift when data lands. */
export function SkeletonList({ rows = 4 }: { rows?: number }) {
  return (
    <div className="stack" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-row" key={index}>
          <span className="skeleton" style={{ height: 13, width: "58%" }} />
          <span className="skeleton" style={{ height: 11, width: "92%" }} />
          <span className="skeleton" style={{ height: 11, width: "74%" }} />
          <span className="skeleton" style={{ height: 5, width: "100%" }} />
        </div>
      ))}
    </div>
  );
}

export function SkeletonBlocks({ rows = 3 }: { rows?: number }) {
  return (
    <div className="stack" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-row" key={index}>
          <span className="skeleton" style={{ height: 15, width: "44%" }} />
          <span className="skeleton" style={{ height: 11, width: "100%" }} />
          <span className="skeleton" style={{ height: 11, width: "88%" }} />
          <span className="skeleton" style={{ height: 11, width: "63%" }} />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  href,
  onAction,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: string;
  href?: string;
  onAction?: () => void;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">{icon}</span>
      <h2>{title}</h2>
      <p>{description}</p>
      {action && href && (
        <Link className="btn btn-primary" href={href}>
          {action}
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      )}
      {action && !href && onAction && (
        <button type="button" className="btn btn-primary" onClick={onAction}>
          {action}
          <ArrowRight size={16} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

export function ErrorNote({
  message,
  onRetry,
  retryLabel = "Try again",
}: {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <div className="note note-danger" role="alert">
      <TriangleAlert size={16} aria-hidden="true" />
      <div className="stack" style={{ gap: 8 }}>
        <span>{message}</span>
        {onRetry && (
          <button type="button" onClick={onRetry}>
            <RefreshCw
              size={12}
              aria-hidden="true"
              style={{ display: "inline", verticalAlign: "-2px", marginRight: 4 }}
            />
            {retryLabel}
          </button>
        )}
      </div>
    </div>
  );
}

/** Capped stagger so long lists never animate rows the reader cannot see. */
export const stagger = (index: number) =>
  ({ "--delay": `${Math.min(index, 7) * 45}ms` }) as React.CSSProperties;
