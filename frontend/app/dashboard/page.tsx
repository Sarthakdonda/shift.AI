"use client";

import { T } from "@/components/locale";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Plus,
  Search,
  ArrowUpRight,
  FolderOpen,
  FileCheck2,
  Activity,
  ArrowRight,
  LayoutGrid,
  List,
} from "lucide-react";
import { Shell } from "@/components/layout/shell";
import { useSession } from "@/components/providers";
import { api, date, humanize } from "@/lib/api";
import { Project } from "@/lib/types";
import { Empty, ErrorBox, Loading } from "@/components/ui/states";
import { delay } from "@/lib/utils";

export default function Dashboard() {
  const { user, loading: authLoading } = useSession();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [view, setView] = useState("grid");
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setProjects(await api<Project[]>("/projects"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    if (!authLoading) void load();
  }, [authLoading, load]);
  const filtered = projects.filter(
    (p) =>
      `${p.name} ${p.industry}`.toLowerCase().includes(search.toLowerCase()) &&
      (filter === "all" ||
        (filter === "complete"
          ? p.status === "BLUEPRINT_READY"
          : p.status !== "BLUEPRINT_READY")),
  );
  const completed = projects.filter(
    (p) => p.status === "BLUEPRINT_READY",
  ).length;
  return (
    <Shell>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            <T text={"YOUR WORKSPACE, AT A GLANCE"} />
          </span>
          <h1>
            {user && !user.local
              ? `Welcome back, ${user.name.split(" ")[0]}.`
              : "A clearer way forward."}
          </h1>
          <p>
            <T
              text={
                "Pick up a thought. Explore a possibility. Make your next shift."
              }
            />
          </p>
        </div>
        <Link className="button button-primary" href="/project/new">
          <Plus size={18} />
          <T text={" New project"} />
        </Link>
      </div>

      {!authLoading && !user && (
        <div className="panel signin-prompt enter">
          <div>
            <h2>
              <T text={"Sign in to see your projects"} />
            </h2>
            <p className="muted">
              <T
                text={
                  "Each account keeps its own private workspace, projects, and blueprints."
                }
              />
            </p>
          </div>
          <Link href="/login" className="button button-primary">
            <T text={"Sign in "} />
            <ArrowRight size={16} />
          </Link>
        </div>
      )}

      <section className="dashboard-banner enter">
        <div>
          <span className="eyebrow">
            <T text={"MAKE SPACE FOR WHAT’S NEXT"} />
          </span>
          <h2>
            <T text={"Your next big idea"} />
            <br />
            <T text={"starts with a better question."} />
          </h2>
          <p>
            <T
              text={
                "Turn the challenge on your mind into a practical plan for your team."
              }
            />
          </p>
          <Link href="/project/new" className="button button-primary button-sm">
            <T text={"Start something new "} />
            <ArrowUpRight size={16} />
          </Link>
        </div>
        <div className="banner-diagram" aria-hidden>
          <div>
            <Search size={20} />
            <span>
              <T text={"Understand"} />
            </span>
          </div>
          <span className="diagram-line" />
          <div>
            <Activity size={20} />
            <span>
              <T text={"Evaluate"} />
            </span>
          </div>
          <span className="diagram-line" />
          <div className="diagram-final">
            <ArrowUpRight size={20} />
            <span>
              <T text={"Move forward"} />
            </span>
          </div>
        </div>
      </section>

      <div className="stats-grid">
        {(
          [
            [
              FolderOpen,
              "Total projects",
              projects.length,
              "Ideas worth exploring",
            ],
            [
              Activity,
              "In progress",
              projects.length - completed,
              "Building a clearer picture",
            ],
            [
              FileCheck2,
              "Blueprints ready",
              completed,
              "Ready for your next step",
            ],
          ] as const
        ).map(([Icon, title, count, caption], i) => (
          <div className="stat-card enter" style={delay(i * 80)} key={title}>
            <div>
              <span>{title}</span>
              <Icon size={19} />
            </div>
            <strong>{String(count).padStart(2, "0")}</strong>
            <small>{caption}</small>
          </div>
        ))}
      </div>

      <div className="section-toolbar">
        <div>
          <h2>
            <T text={"Your projects "} />
            <span className="count">{projects.length}</span>
          </h2>
          <p className="muted">
            <T text={"Pick up exactly where you left off."} />
          </p>
        </div>
        <div className="toolbar-controls">
          <label className="search-input">
            <Search size={17} />
            <input
              aria-label="Search projects"
              placeholder="Search projects…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <div className="view-toggle">
            <button
              aria-label="Grid view"
              aria-pressed={view === "grid"}
              onClick={() => setView("grid")}
              className={view === "grid" ? "selected" : ""}
            >
              <LayoutGrid size={17} />
            </button>
            <button
              aria-label="List view"
              aria-pressed={view === "list"}
              onClick={() => setView("list")}
              className={view === "list" ? "selected" : ""}
            >
              <List size={17} />
            </button>
          </div>
        </div>
      </div>

      <div className="filter-tabs">
        {[
          ["all", "All projects"],
          ["progress", "In progress"],
          ["complete", "Blueprint ready"],
        ].map(([k, label]) => (
          <button
            key={k}
            className={filter === k ? "active" : ""}
            onClick={() => setFilter(k)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox message={error} onRetry={load} />
      ) : !projects.length ? (
        <Empty
          title="Your next shift starts with a question."
          description="Create a project, describe your challenge, and build a clearer picture of what comes next."
          href="/project/new"
          action="Create your first project"
        />
      ) : !filtered.length ? (
        <Empty
          title="No projects match."
          description="Try another search term or filter."
        />
      ) : (
        <div
          className={`project-grid ${view === "list" ? "project-list" : ""}`}
        >
          {filtered.map((p, i) => (
            <Link
              href={`/project/${p.id}`}
              className="project-card enter"
              style={delay(Math.min(i, 8) * 60)}
              key={p.id}
            >
              <div className="row-between">
                <span className="project-icon">
                  <FolderOpen size={22} />
                </span>
                <span
                  className={`badge ${p.status === "BLUEPRINT_READY" ? "badge-green" : "badge-orange"}`}
                >
                  {humanize(p.status)}
                </span>
              </div>
              <h3>{p.name}</h3>
              <p className="project-description">{p.initial_problem}</p>
              <div className="project-category">
                {p.industry || "Business strategy"}
              </div>
              <div className="row-between progress-label">
                <span>
                  <T text={"Discovery completeness"} />
                </span>
                <strong>{p.discovery_scores.overall || 0}%</strong>
              </div>
              <div className="progress-track">
                <span
                  style={{ width: `${p.discovery_scores.overall || 0}%` }}
                />
              </div>
              {p.ai_necessity && (
                <div className="decision-mini">
                  {humanize(p.ai_necessity.classification)}
                </div>
              )}
              <footer>
                <span>
                  <T text={"Updated "} />
                  {date(p.updated_at)}
                </span>
                <ArrowUpRight size={18} />
              </footer>
            </Link>
          ))}
        </div>
      )}
    </Shell>
  );
}
