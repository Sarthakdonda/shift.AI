"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  LayoutDashboard,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
  ArrowLeft,
  MessageSquare,
  Files,
  ChartNoAxesCombined,
  Workflow,
  ShieldCheck,
  FileCheck2,
  LogOut,
} from "lucide-react";
import { Logo } from "@/components/layout/logo";
import { T, LanguagePicker } from "@/components/locale";
import { useSession } from "@/components/providers";
import { ConfirmDialog, useToast } from "@/components/ui/feedback";

const projectNav = [
  ["Discovery", "", MessageSquare],
  ["Documents", "/documents", Files],
  ["Analysis", "/analysis", ChartNoAxesCombined],
  ["Solution", "/solution", Workflow],
  ["Red Team", "/red-team", ShieldCheck],
  ["Blueprint", "/blueprint", FileCheck2],
  ["Deliverables", "/deliverables", Files],
] as const;

const workspaceNav = [
  ["Projects", "/dashboard", LayoutDashboard],
  ["New project", "/project/new", Plus],
  ["Teams & admin", "/workspaces", ShieldCheck],
  ["Transformation", "/transformation", ChartNoAxesCombined],
] as const;

export function Shell({
  children,
  projectId,
  projectName,
}: {
  children: React.ReactNode;
  projectId?: string;
  projectName?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useSession();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const toast = useToast();
  const sidebar = useRef<HTMLElement>(null);
  const items = projectId ? projectNav : workspaceNav;

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const focusable = () =>
      Array.from(
        sidebar.current?.querySelectorAll<HTMLElement>(
          "a[href], button:not([disabled])",
        ) || [],
      );
    focusable()[0]?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
      if (event.key !== "Tab") return;
      const items = focusable();
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    const onResize = () => {
      if (window.innerWidth > 960) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    return () => {
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
      previous?.focus();
    };
  }, [open]);

  const section = projectId
    ? projectNav.find(
        ([, suffix]) => pathname === `/project/${projectId}${suffix}`,
      )?.[0]
    : undefined;
  const page =
    projectName ||
    workspaceNav.find(([, url]) => url === pathname)?.[0] ||
    "Projects";

  return (
    <div className="app-shell">
      <button
        className="mobile-menu icon-button"
        onClick={() => setOpen(!open)}
        aria-label="Toggle navigation"
        aria-expanded={open}
      >
        {open ? <PanelLeftClose size={19} /> : <PanelLeftOpen size={19} />}
      </button>
      {open && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        ref={sidebar}
        className={`sidebar ${open ? "is-open" : ""}`}
        role={open ? "dialog" : undefined}
        aria-modal={open || undefined}
        aria-label="Workspace navigation"
      >
        <Logo light />
        <div className="workspace-label">
          <span className="workspace-avatar" aria-hidden>
            S
          </span>
          <div>
            <T text={"Strategy workspace"} />
            <small>
              {user?.local ? "Personal · Local" : "Personal workspace"}
            </small>
          </div>
        </div>
        {projectId && (
          <Link
            className="back-link"
            href="/dashboard"
            onClick={() => setOpen(false)}
          >
            <ArrowLeft size={15} />
            <T text={" All projects"} />
          </Link>
        )}
        <p className="nav-label">
          {projectId ? "Project workspace" : "Workspace"}
        </p>
        {projectName && (
          <p className="sidebar-project" title={projectName}>
            {projectName}
          </p>
        )}
        <nav aria-label="Primary">
          {items.map(([label, suffix, Icon]) => {
            const href = projectId ? `/project/${projectId}${suffix}` : suffix;
            const active = pathname === href;
            return (
              <Link
                key={label}
                href={href}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                className={`nav-item ${active ? "active" : ""}`}
              >
                <Icon size={18} />
                <T text={label} />
                {active && <span className="nav-dot" />}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="tiny-orange" />
            <T text={"Clarity before complexity."} />
            <p>
              <T text={"The right solution starts with the right question."} />
            </p>
          </div>
          <div className="account">
            <span className="account-avatar" aria-hidden>
              {user?.name?.charAt(0) || "S"}
            </span>
            <div>
              <strong>{user?.name || "Your workspace"}</strong>
              <small>
                {user?.local ? "Local access" : user?.email || "Not signed in"}
              </small>
            </div>
            {user && !user.local && (
              <button
                className="icon-button"
                aria-label="Sign out"
                onClick={() => {
                  setOpen(false);
                  setSigningOut(true);
                }}
              >
                <LogOut size={16} />
              </button>
            )}
          </div>
          {(!user || user.local) && (
            <Link
              className="sidebar-signin"
              href="/login"
              onClick={() => setOpen(false)}
            >
              <T text={"Sign in to your account "} />
              <ArrowLeft size={14} />
            </Link>
          )}
        </div>
      </aside>
      <div className="app-body" inert={open}>
        <header className="topbar">
          <LanguagePicker />
          <div className="breadcrumb">
            <Link href="/dashboard">
              <T text={"Workspace"} />
            </Link>
            <span aria-hidden>/</span>
            {section ? (
              <>
                <Link href={`/project/${projectId}`}>{page}</Link>
                <span aria-hidden>/</span>
                <strong>{section}</strong>
              </>
            ) : (
              <strong>{page}</strong>
            )}
          </div>
          <span className="topbar-tag">
            <span className="tiny-orange" />
            <T text={" Personal workspace"} />
          </span>
        </header>
        <main className="main-content" id="main">
          {children}
        </main>
      </div>
      <ConfirmDialog
        open={signingOut}
        onOpenChange={setSigningOut}
        title="Sign out of your workspace?"
        description="Your saved projects will be here when you return. Any message you haven’t sent will be cleared."
        confirmLabel="Sign out"
        signout
        onConfirm={async () => {
          await logout();
          toast("You’ve been signed out.");
          router.replace("/login");
        }}
      />
    </div>
  );
}
