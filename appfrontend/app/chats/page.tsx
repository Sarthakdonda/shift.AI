"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowUpRight,
  CheckCircle2,
  FolderOpen,
  Loader,
  MessagesSquare,
  Plus,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { Screen } from "@/components/shell/screen";
import { useRequireAuth } from "@/components/shell/guard";
import { api, humanize, relativeTime } from "@/lib/api";
import type { Project } from "@/lib/types";
import {
  BrandMark,
  EmptyState,
  ErrorNote,
  SkeletonList,
  stagger,
} from "@/components/ui/states";

const FILTERS = [
  ["all", "All"],
  ["progress", "In progress"],
  ["complete", "Blueprint ready"],
] as const;

export default function Chats() {
  const { ready, loading: authLoading, user } = useRequireAuth();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);
  const [filter, setFilter] = useState<string>("all");

  const load = useCallback(async () => {
    setError("");
    try {
      setProjects(await api<Project[]>("/projects"));
    } catch (failure) {
      setError((failure as Error).message);
      setProjects([]);
    }
  }, []);

  useEffect(() => {
    if (ready) void load();
  }, [ready, load]);

  const all = projects || [];
  const complete = all.filter((p) => p.status === "BLUEPRINT_READY").length;
  const visible = all.filter(
    (project) =>
      `${project.name} ${project.industry} ${project.initial_problem}`
        .toLowerCase()
        .includes(search.trim().toLowerCase()) &&
      (filter === "all" ||
        (filter === "complete"
          ? project.status === "BLUEPRINT_READY"
          : project.status !== "BLUEPRINT_READY")),
  );

  return (
    <Screen
      depth="root"
      tabs
      title="Projects"
      lead={
        <span style={{ paddingLeft: 8 }}>
          <BrandMark />
        </span>
      }
      actions={
        <button
          type="button"
          className="icon-btn"
          aria-label={searching ? "Close search" : "Search projects"}
          aria-pressed={searching}
          onClick={() => {
            setSearching(!searching);
            if (searching) setSearch("");
          }}
        >
          {searching ? <X size={20} /> : <Search size={20} />}
        </button>
      }
      padded={false}
      floating={
        <Link className="fab" href="/new" aria-label="Start a new project">
          <Plus size={19} aria-hidden="true" />
          New project
        </Link>
      }
    >
      <div className="chats-head">
        {searching ? (
          <label className="search">
            <Search size={17} aria-hidden="true" />
            <input
              autoFocus
              aria-label="Search projects"
              placeholder="Search projects…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
        ) : (
          <section className="workspace-hero">
            <div className="workspace-hero-copy">
              <span className="hero-kicker">
                <Sparkles size={13} aria-hidden="true" />
                Strategy workspace
              </span>
              <h1>
                {user && !user.local
                  ? `Good to see you, ${user.name.split(" ")[0]}.`
                  : "Turn business friction into a clear plan."}
              </h1>
              <p>Continue discovery, review evidence, or shape your next move.</p>
            </div>
            <Link className="hero-action" href="/new">
              <Plus size={17} aria-hidden="true" />
              Start a brief
            </Link>
          </section>
        )}

        <div className="stats" aria-label="Workspace overview">
          {(
            [
              [FolderOpen, "Projects", all.length],
              [Loader, "In progress", all.length - complete],
              [CheckCircle2, "Ready", complete],
            ] as const
          ).map(([Icon, label, count], index) => (
            <div className="stat" key={label} style={stagger(index)}>
              <span className="stat-icon"><Icon size={16} aria-hidden="true" /></span>
              <span className="stat-copy">
                <strong>{String(count).padStart(2, "0")}</strong>
                <span>{label}</span>
              </span>
            </div>
          ))}
        </div>

        {!!all.length && (
          <div className="project-toolbar">
            <div>
              <span className="eyebrow">Active work</span>
              <strong>{visible.length} {visible.length === 1 ? "project" : "projects"}</strong>
            </div>
            <div className="chip-scroller">
            {FILTERS.map(([key, label]) => (
              <button
                type="button"
                className="chip"
                key={key}
                data-active={filter === key ? "true" : undefined}
                aria-pressed={filter === key}
                onClick={() => setFilter(key)}
              >
                {label}
              </button>
            ))}
            </div>
          </div>
        )}
      </div>

      <div className="chat-list">
        {error && <ErrorNote message={error} onRetry={() => void load()} />}
        {!projects || authLoading ? (
          <SkeletonList />
        ) : !all.length ? (
          <EmptyState
            icon={<MessagesSquare size={26} />}
            title="Your next shift starts with a question."
            description="Describe a challenge and build a clearer picture of what comes next."
            action="Start a project"
            href="/new"
          />
        ) : !visible.length ? (
          <EmptyState
            icon={<Search size={26} />}
            title="Nothing matches."
            description="Try another search term or a different filter."
          />
        ) : (
          visible.map((project, index) => (
            <Link
              className="chat-card"
              href={`/chat/${project.id}`}
              key={project.id}
              style={stagger(index)}
            >
              <div className="project-card-head">
                <span
                  className={`badge ${
                    project.status === "BLUEPRINT_READY"
                      ? "badge-good"
                      : "badge-accent"
                  }`}
                >
                  {humanize(project.status)}
                </span>
                <ArrowUpRight className="project-card-arrow" size={18} aria-hidden="true" />
              </div>
              <span className="project-industry">
                {project.industry || "Business strategy"}
              </span>
              <h3 className="clamp-2">{project.name}</h3>
              <p className="clamp-2">{project.initial_problem}</p>
              <div className="chat-progress">
                <div className="chat-progress-label">
                  <span>Discovery</span>
                  <strong>{project.discovery_scores.overall || 0}%</strong>
                </div>
                <div className="meter">
                  <span
                    style={{
                      width: `${project.discovery_scores.overall || 0}%`,
                    }}
                  />
                </div>
              </div>
              <footer>
                <span>{relativeTime(project.updated_at)}</span>
                <span>{project.discovery_scores.overall || 0}% context mapped</span>
              </footer>
            </Link>
          ))
        )}
      </div>
    </Screen>
  );
}
