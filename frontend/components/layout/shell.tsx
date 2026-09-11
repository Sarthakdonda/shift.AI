"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  LayoutDashboard,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
  MessageSquare,
  Files,
  ChartNoAxesCombined,
  ChevronRight,
  Workflow,
  ShieldCheck,
  FileCheck2,
  LogOut,
  FolderOpen,
} from "lucide-react";
import { Logo } from "@/components/layout/logo";
import { ChatHistory } from "@/components/layout/chat-history";
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

type SidebarState = {
  /** Mobile/tablet drawer. */
  open: boolean;
  setOpen: (open: boolean) => void;
  /** Desktop icon rail. */
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
};

const SidebarContext = createContext<SidebarState>({
  open: false,
  setOpen: () => {},
  collapsed: false,
  setCollapsed: () => {},
});

/** Lets a page header host the navigation toggles instead of a floating button. */
export const useShellSidebar = () => useContext(SidebarContext);

export function Shell({
  children,
  projectId,
  projectName,
  /** `chat` gives the page the full viewport and its own header. */
  chrome = "page",
}: {
  children: React.ReactNode;
  projectId?: string;
  projectName?: string;
  chrome?: "page" | "chat";
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useSession();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const toast = useToast();
  const sidebar = useRef<HTMLElement>(null);
  const items = projectId ? projectNav : workspaceNav;
  const conversational = chrome === "chat";

  useEffect(() => {
    setCollapsed(localStorage.getItem("shift-sidebar") === "collapsed");
  }, []);

  const changeCollapsed = useCallback((next: boolean) => {
    setCollapsed(next);
    localStorage.setItem("shift-sidebar", next ? "collapsed" : "expanded");
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const focusable = () =>
      Array.from(
        sidebar.current?.querySelectorAll<HTMLElement>(
          "a[href], button:not([disabled]), input:not([disabled])",
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
  const rail = collapsed && !open;
  const close = () => setOpen(false);

  return (
    <SidebarContext.Provider
      value={{ open, setOpen, collapsed, setCollapsed: changeCollapsed }}
    >
      <div
        className={`app-shell ${conversational ? "shell-chat" : ""} ${rail ? "shell-rail" : ""}`}
      >
        {!conversational && (
          <button
            className="mobile-menu icon-button"
            onClick={() => setOpen(!open)}
            aria-label="Toggle navigation"
            aria-expanded={open}
          >
            {open ? <PanelLeftClose size={19} /> : <PanelLeftOpen size={19} />}
          </button>
        )}
        {open && (
          <button
            className="sidebar-scrim"
            aria-label="Close navigation"
            onClick={close}
          />
        )}
        <aside
          ref={sidebar}
          className={`sidebar dx-sidebar ${open ? "is-open" : ""}`}
          role={open ? "dialog" : undefined}
          aria-modal={open || undefined}
          aria-label="Workspace navigation"
        >
          <div className="dx-sidebar-top">
            <Logo light />
            <button
              type="button"
              className="dx-collapse"
              aria-label={rail ? "Expand sidebar" : "Collapse sidebar"}
              aria-pressed={rail}
              title={rail ? "Expand sidebar" : "Collapse sidebar"}
              onClick={() => changeCollapsed(!collapsed)}
            >
              {rail ? (
                <PanelLeftOpen size={17} />
              ) : (
                <PanelLeftClose size={17} />
              )}
            </button>
          </div>

          <ChatHistory
            projectId={projectId}
            collapsed={rail}
            onNavigate={close}
          />

          <div className="dx-sidebar-nav">
            <p className="nav-label">
              {projectId ? "Project tools" : "Workspace"}
            </p>
            <nav aria-label="Primary">
              {items.map(([label, suffix, Icon]) => {
                const href = projectId
                  ? `/project/${projectId}${suffix}`
                  : suffix;
                const active = pathname === href;
                return (
                  <Link
                    key={label}
                    href={href}
                    onClick={close}
                    aria-current={active ? "page" : undefined}
                    title={label}
                    className={`nav-item ${active ? "active" : ""}`}
                  >
                    <Icon size={18} />
                    <span className="dx-nav-text">
                      <T text={label} />
                    </span>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="sidebar-bottom">
            <Link className="dx-switcher" href="/dashboard" onClick={close}>
              <span className="dx-switcher-icon" aria-hidden>
                <FolderOpen size={16} />
              </span>
              <span className="dx-nav-text">
                <strong>
                  <T text={"All projects"} />
                </strong>
                <small>
                  {user?.local ? "Personal · Local" : "Personal workspace"}
                </small>
              </span>
              <ChevronRight
                className="dx-switcher-go dx-nav-text"
                size={14}
                aria-hidden
              />
            </Link>
            <div className="account">
              <span className="account-avatar" aria-hidden>
                {user?.name?.charAt(0) || "S"}
              </span>
              <div className="dx-nav-text">
                <strong>{user?.name || "Your workspace"}</strong>
                <small>
                  {user?.local
                    ? "Local access"
                    : user?.email || "Not signed in"}
                </small>
              </div>
              {user && !user.local && (
                <button
                  className="icon-button dx-nav-text"
                  aria-label="Sign out"
                  onClick={() => {
                    close();
                    setSigningOut(true);
                  }}
                >
                  <LogOut size={16} />
                </button>
              )}
            </div>
            {(!user || user.local) && (
              <Link
                className="sidebar-signin dx-nav-text"
                href="/login"
                onClick={close}
              >
                <T text={"Sign in to your account"} />
              </Link>
            )}
          </div>
        </aside>
        <div className="app-body" inert={open}>
          {!conversational && (
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
          )}
          <main
            className={`main-content ${conversational ? "main-chat" : ""}`}
            id="main"
          >
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
    </SidebarContext.Provider>
  );
}

/** Drawer toggle for pages that render their own header instead of the topbar. */
export function SidebarToggle() {
  const { open, setOpen } = useShellSidebar();
  return (
    <button
      type="button"
      className="dx-icon-button dx-drawer-toggle"
      aria-label="Toggle navigation"
      aria-expanded={open}
      onClick={() => setOpen(!open)}
    >
      {open ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
    </button>
  );
}
