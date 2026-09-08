"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  ArrowUpRight,
  LayoutDashboard,
  Plus,
  Settings2,
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
import { useSession } from "@/components/providers";

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link
      href="/"
      className={`logo ${light ? "logo-light" : ""}`}
      aria-label="shift.AI home"
    >
      <span className="logo-mark">
        <ArrowUpRight size={23} strokeWidth={2.8} />
      </span>
      shift<span className="logo-ai">.AI</span>
    </Link>
  );
}
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
  const [error, setError] = useState("");
  const items = projectId
    ? ([
        ["Discovery", "", MessageSquare],
        ["Documents", "/documents", Files],
        ["Analysis", "/analysis", ChartNoAxesCombined],
        ["Solution", "/solution", Workflow],
        ["Red Team", "/red-team", ShieldCheck],
        ["Blueprint", "/blueprint", FileCheck2],
      ] as const)
    : ([
        ["Projects", "/dashboard", LayoutDashboard],
        ["New project", "/project/new", Plus],
      ] as const);
  return (
    <div className="app-shell">
      <button
        className="mobile-menu icon-button"
        onClick={() => setOpen(!open)}
        aria-label="Toggle navigation"
      >
        {open ? <PanelLeftClose /> : <PanelLeftOpen />}
      </button>
      {open && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <Logo light />
        <div className="workspace-label">
          <span className="workspace-avatar">S</span>
          <div>
            Strategy workspace
            <small>
              {user?.local ? "Personal · Local" : "Personal workspace"}
            </small>
          </div>
        </div>
        {projectId && (
          <Link className="back-link" href="/dashboard">
            <ArrowLeft size={15} /> All projects
          </Link>
        )}
        <p className="nav-label">
          {projectId ? "PROJECT WORKSPACE" : "WORKSPACE"}
        </p>
        {projectName && (
          <p className="sidebar-project" title={projectName}>
            {projectName}
          </p>
        )}
        <nav>
          {items.map(([label, suffix, Icon]) => {
            const href = projectId ? `/project/${projectId}${suffix}` : suffix;
            return (
              <Link
                key={label}
                href={href}
                onClick={() => setOpen(false)}
                className={`nav-item ${pathname === href ? "active" : ""}`}
              >
                <Icon size={18} />
                {label}
                {pathname === href && <span className="nav-dot" />}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="tiny-orange" />
            Clarity before complexity.
            <p>The right solution starts with the right question.</p>
          </div>
          <Link
            className={`nav-item ${pathname === "/settings" ? "active" : ""}`}
            href="/settings"
          >
            <Settings2 size={18} /> Settings & connections
          </Link>
          <div className="account">
            <span className="account-avatar">
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
                onClick={async () => {
                  try {
                    await logout();
                    router.push("/login");
                  } catch {
                    setError("Sign-out failed. Please retry.");
                  }
                }}
              >
                <LogOut size={16} />
              </button>
            )}
          </div>
          {error && <small role="alert">{error}</small>}
        </div>
      </aside>
      <div className="app-body">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span>{" "}
            <strong>
              {projectName ||
                (pathname === "/settings"
                  ? "Settings"
                  : pathname === "/project/new"
                    ? "New project"
                    : "Projects")}
            </strong>
          </div>
          <span className="topbar-tag">
            <span className="tiny-orange" /> Problem first. Possibility next.
          </span>
        </header>
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
