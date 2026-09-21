"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { LoaderCircle } from "lucide-react";

/**
 * Android's hardware back button should close whatever is on top, not leave the
 * screen. A history entry is pushed while an overlay is open, and closing the
 * overlay from the UI goes back through that entry. Next's own history state is
 * preserved so the router treats the entry as its own.
 *
 * Cleanup deliberately does not touch history: an action that closes the overlay
 * and then navigates (sign out, delete) must not race a `history.back()`.
 */
function useBackDismiss(open: boolean, close: () => void) {
  const closeRef = useRef(close);
  useEffect(() => {
    closeRef.current = close;
  }, [close]);
  useEffect(() => {
    if (!open) return;
    try {
      window.history.pushState(
        { ...(window.history.state || {}), shiftOverlay: true },
        "",
      );
    } catch {
      // A blocked history API only costs the back-to-close shortcut.
    }
    const onPop = () => closeRef.current();
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [open]);
}

/** Closes through history when this overlay owns the current entry. */
function dismissThroughHistory(close: () => void) {
  if (typeof window !== "undefined" && window.history.state?.shiftOverlay)
    window.history.back();
  else close();
}

/** Keeps the exit animation on screen for one frame budget before unmounting. */
export function useOverlay(open: boolean) {
  const [mounted, setMounted] = useState(open);
  const [closing, setClosing] = useState(false);
  useEffect(() => {
    if (open) {
      setMounted(true);
      setClosing(false);
      return;
    }
    if (!mounted) return;
    setClosing(true);
    const timer = setTimeout(() => {
      setMounted(false);
      setClosing(false);
    }, 220);
    return () => clearTimeout(timer);
  }, [open, mounted]);
  return { mounted, closing };
}

export function Sheet({
  open,
  onClose,
  title,
  description,
  labelledBy,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  labelledBy?: string;
  children?: React.ReactNode;
}) {
  const { mounted, closing } = useOverlay(open);
  const panel = useRef<HTMLDivElement>(null);
  const dismiss = useCallback(() => dismissThroughHistory(onClose), [onClose]);
  useBackDismiss(open, onClose);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        dismiss();
      }
      if (event.key !== "Tab" || !panel.current) return;
      const focusable = panel.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const timer = setTimeout(
      () => panel.current?.querySelector<HTMLElement>("button, a, input")?.focus(),
      60,
    );
    return () => {
      document.removeEventListener("keydown", onKey);
      clearTimeout(timer);
    };
  }, [open, dismiss]);

  if (!mounted) return null;
  return (
    <>
      <div
        className="scrim"
        data-closing={closing || undefined}
        onClick={dismiss}
        aria-hidden="true"
      />
      <div
        className="sheet"
        data-closing={closing || undefined}
        role="dialog"
        aria-modal="true"
        aria-label={labelledBy ? undefined : title}
        aria-labelledby={labelledBy}
        ref={panel}
      >
        <span className="sheet-grab" aria-hidden="true" />
        {title && <h2>{title}</h2>}
        {description && <p>{description}</p>}
        {children}
      </div>
    </>
  );
}

export function ConfirmSheet({
  open,
  onClose,
  title,
  description,
  confirmLabel = "Confirm",
  danger,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setError("");
      setBusy(false);
    }
  }, [open]);
  return (
    <Sheet open={open} onClose={onClose} title={title} description={description}>
      {error && (
        <p className="note note-danger" role="alert">
          {error}
        </p>
      )}
      <div className="sheet-actions">
        <button
          type="button"
          className={`btn btn-block ${danger ? "btn-danger" : "btn-primary"}`}
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await onConfirm();
              onClose();
            } catch (failure) {
              setError((failure as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy && <LoaderCircle size={16} className="spin" aria-hidden="true" />}
          {busy ? "Working…" : confirmLabel}
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-block"
          disabled={busy}
          onClick={() => dismissThroughHistory(onClose)}
        >
          Cancel
        </button>
      </div>
    </Sheet>
  );
}
