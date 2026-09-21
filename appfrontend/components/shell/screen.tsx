"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ChevronLeft, MessageSquareText, Settings, SquarePen } from "lucide-react";

export function AppBar({
  title,
  subtitle,
  back,
  lead,
  actions,
  scrolled,
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  /** true uses history back; a string navigates to that route. */
  back?: boolean | string;
  lead?: React.ReactNode;
  actions?: React.ReactNode;
  scrolled?: boolean;
}) {
  const router = useRouter();
  return (
    <header className="bar" data-scrolled={scrolled ? "true" : "false"}>
      <div className="bar-lead">
        {back ? (
          typeof back === "string" ? (
            <Link className="icon-btn" href={back} aria-label="Back">
              <ChevronLeft size={24} />
            </Link>
          ) : (
            <button
              type="button"
              className="icon-btn"
              aria-label="Back"
              onClick={() => router.back()}
            >
              <ChevronLeft size={24} />
            </button>
          )
        ) : (
          lead
        )}
      </div>
      <div className="bar-title">
        {title && <strong>{title}</strong>}
        {subtitle && <span>{subtitle}</span>}
      </div>
      <div className="bar-actions">{actions}</div>
    </header>
  );
}

const TABS = [
  { href: "/chats", label: "Projects", icon: MessageSquareText },
  { href: "/new", label: "New", icon: SquarePen },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function TabBar() {
  const pathname = usePathname();
  return (
    <nav className="tabs" aria-label="Main">
      {TABS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            className="tab"
            href={href}
            key={href}
            data-active={active ? "true" : "false"}
            aria-current={active ? "page" : undefined}
          >
            <Icon size={21} strokeWidth={active ? 2.2 : 1.8} aria-hidden="true" />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

/**
 * Every route renders exactly one Screen: a fixed bar, one scroll region, and
 * an optional tab bar. Nothing outside the scroll region ever moves, which is
 * what separates an application surface from a scrolling web page.
 */
export function Screen({
  title,
  subtitle,
  back,
  lead,
  actions,
  tabs,
  depth = "push",
  /** "fill" hands layout to the child, used by the conversation. */
  variant = "scroll",
  padded = true,
  children,
  below,
  floating,
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  back?: boolean | string;
  lead?: React.ReactNode;
  actions?: React.ReactNode;
  tabs?: boolean;
  depth?: "root" | "push";
  variant?: "scroll" | "fill";
  padded?: boolean;
  children: React.ReactNode;
  /** Rendered between the bar and the scroll region, e.g. a segmented control. */
  below?: React.ReactNode;
  /** Pinned above the scroll region, e.g. a floating action button. */
  floating?: React.ReactNode;
}) {
  const sentinel = useRef<HTMLDivElement>(null);
  const [scrolled, setScrolled] = useState(variant === "fill");

  useEffect(() => {
    if (variant === "fill") return;
    const node = sentinel.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    // A sentinel crossing the top edge is cheaper than a scroll listener.
    const observer = new IntersectionObserver(
      ([entry]) => setScrolled(!entry.isIntersecting),
      { threshold: 1 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [variant]);

  return (
    <div className="frame">
      <div>
        <AppBar
          title={title}
          subtitle={subtitle}
          back={back}
          lead={lead}
          actions={actions}
          scrolled={scrolled}
        />
        {below}
      </div>
      <main className="screen" data-depth={depth} id="main">
        {variant === "fill" ? (
          children
        ) : (
          <div className="scroll">
            <div ref={sentinel} style={{ height: 1 }} aria-hidden="true" />
            <div className={padded ? "pad" : undefined}>{children}</div>
          </div>
        )}
        {floating}
      </main>
      {tabs ? <TabBar /> : <div />}
    </div>
  );
}
