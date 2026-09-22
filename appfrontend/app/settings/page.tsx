"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ChevronRight,
  CircleHelp,
  Database,
  Globe,
  LogOut,
  Mail,
  Search,
  ServerCog,
  Sparkles,
} from "lucide-react";
import { Screen } from "@/components/shell/screen";
import { useRequireAuth } from "@/components/shell/guard";
import { useSession, useToast } from "@/components/providers";
import { ConfirmSheet, Sheet } from "@/components/ui/sheet";
import { Splash } from "@/components/ui/states";
import { API_BASE, api } from "@/lib/api";
import type { Project } from "@/lib/types";

function StatusRow({
  icon,
  label,
  detail,
  state,
}: {
  icon: React.ReactNode;
  label: string;
  detail: string;
  state: "ok" | "warn" | "bad";
}) {
  return (
    <div className="list-row">
      <span className="avatar">{icon}</span>
      <span className="list-row-body">
        <strong>{label}</strong>
        <span>{detail}</span>
      </span>
      <span className="status-dot" data-state={state} aria-hidden="true" />
    </div>
  );
}

export default function Settings() {
  const { ready } = useRequireAuth();
  const { user, health, logout } = useSession();
  const router = useRouter();
  const toast = useToast();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [signOut, setSignOut] = useState(false);
  const [about, setAbout] = useState(false);

  useEffect(() => {
    if (!ready) return;
    api<Project[]>("/projects")
      .then(setProjects)
      .catch(() => setProjects([]));
  }, [ready]);

  if (!ready || !user) return <Splash />;

  const complete = (projects || []).filter(
    (project) => project.status === "BLUEPRINT_READY",
  ).length;

  return (
    <Screen depth="root" tabs title="Settings" padded={false}>
      <div className="settings">
        <section className="profile">
          <div className="profile-identity">
            <span className="profile-avatar" aria-hidden="true">
              {user.name.trim().slice(0, 1).toUpperCase() || "S"}
            </span>
            <div>
              <span className="hero-kicker">Your workspace</span>
              <strong>{user.name}</strong>
              <span className="selectable">{user.email}</span>
            </div>
          </div>
          <div className="profile-stats">
            <span><b>{projects?.length || 0}</b> Projects</span>
            <span><b>{complete}</b> Blueprints</span>
            <span><b>{health?.database === "connected" ? "Live" : "Check"}</b> Sync</span>
          </div>
        </section>

        <div className="settings-group">
          <p className="eyebrow">Workspace</p>
          <div className="group">
            <div className="list-row">
              <span className="avatar">
                <Sparkles size={17} />
              </span>
              <span className="list-row-body">
                <strong>
                  {projects
                    ? `${projects.length} ${projects.length === 1 ? "project" : "projects"}`
                    : "Projects"}
                </strong>
                <span>
                  {complete === 1
                    ? "1 with a finished blueprint"
                    : `${complete} with a finished blueprint`}
                </span>
              </span>
              <Link
                className="btn btn-ghost btn-sm"
                href="/chats"
                aria-label="Open your projects"
              >
                Open
              </Link>
            </div>
          </div>
        </div>

        <div className="settings-group">
          <p className="eyebrow">Connection</p>
          <div className="group">
            <StatusRow
              icon={<ServerCog size={17} />}
              label="Workspace API"
              detail={API_BASE.replace(/^https?:\/\//, "")}
              state={health ? "ok" : "bad"}
            />
            <StatusRow
              icon={<Database size={17} />}
              label="Database"
              detail={
                health?.database === "connected"
                  ? "Connected"
                  : health?.database === "not_configured"
                    ? "Not configured on the server"
                    : "Unavailable"
              }
              state={health?.database === "connected" ? "ok" : "bad"}
            />
            <StatusRow
              icon={<Sparkles size={17} />}
              label="AI provider"
              detail={health?.gemini_configured ? "Connected" : "No API key configured"}
              state={health?.gemini_configured ? "ok" : "warn"}
            />
            <StatusRow
              icon={<Search size={17} />}
              label="Semantic retrieval"
              detail={
                health?.vector_search_configured
                  ? "Vector search configured"
                  : "Keyword retrieval"
              }
              state={health?.vector_search_configured ? "ok" : "warn"}
            />
            <StatusRow
              icon={<Mail size={17} />}
              label="Password reset email"
              detail={health?.email_configured ? "SMTP configured" : "Not configured"}
              state={health?.email_configured ? "ok" : "warn"}
            />
          </div>
        </div>

        <div className="settings-group">
          <p className="eyebrow">Account</p>
          <div className="group">
            <button
              type="button"
              className="list-row"
              onClick={() => setAbout(true)}
            >
              <span className="avatar">
                <CircleHelp size={17} />
              </span>
              <span className="list-row-body">
                <strong>About this app</strong>
                <span>What it does, and what it does not</span>
              </span>
              <ChevronRight size={18} className="list-row-chevron" aria-hidden="true" />
            </button>
            <button
              type="button"
              className="list-row"
              onClick={() => setSignOut(true)}
            >
              <span className="avatar" style={{ background: "var(--danger-soft)" }}>
                <LogOut size={17} color="var(--danger)" />
              </span>
              <span className="list-row-body">
                <strong style={{ color: "var(--danger)" }}>Sign out</strong>
                <span>Your projects stay on your account</span>
              </span>
              <ChevronRight size={18} className="list-row-chevron" aria-hidden="true" />
            </button>
          </div>
        </div>

        <p className="app-footer">
          shift.AI · Clarity before complexity
          <br />
          Projects, evidence and blueprints are stored on your workspace, not on this
          device.
        </p>
      </div>

      <Sheet open={about} onClose={() => setAbout(false)} title="About shift.AI">
        <div className="sheet-body stack">
          <p>
            shift.AI diagnoses the actual problem before recommending AI,
            automation, existing software, a process change, or a hybrid.
          </p>
          <div className="group">
            <div className="list-row">
              <span className="avatar">
                <Globe size={17} />
              </span>
              <span className="list-row-body">
                <strong>Connected app</strong>
                <span>Work is saved on your workspace, never only on the phone</span>
              </span>
              <span />
            </div>
          </div>
          <p className="field-note">
            Google sign-in, twenty-language selection and the full deliverable
            editor live on the website. Sign in here with your email to reach the
            same projects.
          </p>
        </div>
      </Sheet>

      <ConfirmSheet
        open={signOut}
        onClose={() => setSignOut(false)}
        title="Sign out?"
        description="You will need your email and password to sign back in. Nothing is deleted."
        confirmLabel="Sign out"
        danger
        onConfirm={async () => {
          await logout();
          toast("Signed out.");
          router.replace("/login");
        }}
      />
    </Screen>
  );
}
