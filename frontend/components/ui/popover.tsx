"use client";

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

type Align = "start" | "end" | "center";
type Side = "top" | "bottom";

type Placement = {
  left: number;
  top: number;
  maxHeight: number;
  side: Side;
};

/**
 * Anchored popover used by the conversation header and composer controls.
 *
 * One primitive keeps every menu consistent: portalled above the layout,
 * clamped inside the viewport, closed by Escape, outside pointer or Tab, with
 * roving arrow-key focus across the enabled controls it contains.
 */
export function Popover({
  trigger,
  children,
  label,
  align = "start",
  side = "top",
  width = 264,
  open,
  onOpenChange,
  role = "menu",
  className = "",
}: {
  /** Renders the trigger. `props` must be spread onto a focusable element. */
  trigger: (props: {
    ref: React.Ref<HTMLButtonElement>;
    "aria-haspopup": "menu" | "dialog" | "listbox";
    "aria-expanded": boolean;
    "aria-controls"?: string;
    onClick: () => void;
    onKeyDown: (event: React.KeyboardEvent) => void;
  }) => React.ReactNode;
  /** Panel contents. A function receives `close` for selection menus. */
  children: React.ReactNode | ((close: () => void) => React.ReactNode);
  label: string;
  align?: Align;
  side?: Side;
  width?: number;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  role?: "menu" | "dialog" | "listbox";
  className?: string;
}) {
  const [uncontrolled, setUncontrolled] = useState(false);
  const isOpen = open ?? uncontrolled;
  const setOpen = useCallback(
    (next: boolean) => {
      setUncontrolled(next);
      onOpenChange?.(next);
    },
    [onOpenChange],
  );
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const id = useId();
  const [restoreFocus, setRestoreFocus] = useState(false);
  const [placement, setPlacement] = useState<Placement>({
    left: 12,
    top: 12,
    maxHeight: 360,
    side,
  });

  const close = useCallback(() => {
    setOpen(false);
    setRestoreFocus(true);
  }, [setOpen]);

  // Focus returns to the trigger only for keyboard/selection dismissals, never
  // when the user clicked somewhere else on the page.
  useEffect(() => {
    if (!restoreFocus || isOpen) return;
    setRestoreFocus(false);
    triggerRef.current?.focus({ preventScroll: true });
  }, [restoreFocus, isOpen]);

  useLayoutEffect(() => {
    if (!isOpen) return;
    const place = () => {
      const anchor = triggerRef.current?.getBoundingClientRect();
      if (!anchor) return;
      const gutter = 12;
      const box = Math.min(width, window.innerWidth - gutter * 2);
      const above = anchor.top - gutter - 8;
      const below = window.innerHeight - anchor.bottom - gutter - 8;
      const wanted = Math.min(panel.current?.scrollHeight || 320, 420);
      const useAbove =
        side === "top" ? above >= wanted || above > below : false;
      const room = Math.max(140, useAbove ? above : below);
      const maxHeight = Math.min(420, room);
      const height = Math.min(panel.current?.scrollHeight || 320, maxHeight);
      const left =
        align === "end"
          ? anchor.right - box
          : align === "center"
            ? anchor.left + anchor.width / 2 - box / 2
            : anchor.left;
      setPlacement({
        left: Math.max(
          gutter,
          Math.min(left, window.innerWidth - box - gutter),
        ),
        top: useAbove
          ? Math.max(gutter, anchor.top - height - 8)
          : Math.min(
              anchor.bottom + 8,
              Math.max(gutter, window.innerHeight - height - gutter),
            ),
        maxHeight,
        side: useAbove ? "top" : "bottom",
      });
    };
    place();
    const selected =
      panel.current?.querySelector<HTMLElement>('[aria-checked="true"]') ||
      panel.current?.querySelector<HTMLElement>(
        "button:not(:disabled), a[href], input, select",
      );
    selected?.focus({ preventScroll: true });
    selected?.scrollIntoView({ block: "nearest" });
    const onScroll = (event: Event) => {
      if (panel.current?.contains(event.target as Node)) return;
      place();
    };
    window.addEventListener("resize", place);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [isOpen, align, side, width]);

  useEffect(() => {
    if (!isOpen) return;
    const onPointer = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        panel.current?.contains(target) ||
        triggerRef.current?.contains(target)
      )
        return;
      setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      close();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [isOpen, close, setOpen]);

  return (
    <>
      {trigger({
        ref: triggerRef,
        "aria-haspopup": role,
        "aria-expanded": isOpen,
        "aria-controls": isOpen ? id : undefined,
        onClick: () => setOpen(!isOpen),
        onKeyDown: (event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setOpen(true);
          }
        },
      })}
      {isOpen &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            ref={panel}
            id={id}
            role={role}
            aria-label={label}
            data-side={placement.side}
            className={`dx-pop ${className}`}
            style={{
              left: placement.left,
              top: placement.top,
              maxHeight: placement.maxHeight,
              width: `min(${width}px, calc(100vw - 24px))`,
            }}
            onKeyDown={(event) => {
              const items = Array.from(
                panel.current?.querySelectorAll<HTMLElement>(
                  "button:not(:disabled), a[href], [tabindex='0']",
                ) || [],
              );
              const index = items.indexOf(
                document.activeElement as HTMLElement,
              );
              let next: number | undefined;
              if (event.key === "ArrowDown") next = (index + 1) % items.length;
              if (event.key === "ArrowUp")
                next = (index - 1 + items.length) % items.length;
              if (event.key === "Home") next = 0;
              if (event.key === "End") next = items.length - 1;
              if (next !== undefined) {
                event.preventDefault();
                items[next]?.focus();
              }
              if (event.key === "Tab") close();
            }}
          >
            {typeof children === "function" ? children(close) : children}
          </div>,
          document.body,
        )}
    </>
  );
}

/** Matches a media query on the client without breaking server rendering. */
export function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}
