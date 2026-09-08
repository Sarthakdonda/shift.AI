"use client";
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
export default function Dashboard() {
  const { user, health, loading: authLoading } = useSession();
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
          <span className="eyebrow">YOUR NEXT MOVE STARTS HERE</span>
          <h1>Let’s make progress.</h1>
          <p>
            Big questions. Clear direction. All your projects, in one place.
          </p>
        </div>
        <Link className="button button-primary" href="/project/new">
          <Plus size={18} /> New project
        </Link>
      </div>
      {!authLoading && !user && (
        <ErrorBox message="Sign in to see your projects." />
      )}
      {!authLoading && !user && (
        <Link href="/login" className="button button-secondary">
          Sign in with Google <ArrowRight size={16} />
        </Link>
      )}
      <section className="dashboard-banner">
        <div>
          <span className="eyebrow">A BETTER STARTING POINT</span>
          <h2>
            You bring the challenge.
            <br />
            We’ll help find the right direction.
          </h2>
          <p>Start with what’s not working. The solution comes after.</p>
          <Link href="/project/new" className="text-button">
            Explore a new problem <ArrowRight size={16} />
          </Link>
        </div>
        <div className="banner-diagram">
          <div>
            <Search size={20} />
            <span>Understand</span>
          </div>
          <span className="diagram-line" />
          <div>
            <Activity size={20} />
            <span>Evaluate</span>
          </div>
          <span className="diagram-line" />
          <div className="diagram-final">
            <ArrowUpRight size={20} />
            <span>Move forward</span>
          </div>
        </div>
      </section>
      <div className="stats-grid">
        {[
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
        ].map(([Icon, title, count, caption]) => {
          const I = Icon as typeof FolderOpen;
          return (
            <div className="stat-card" key={String(title)}>
              <div>
                <span>{String(title)}</span>
                <I size={19} />
              </div>
              <strong>{String(count).padStart(2, "0")}</strong>
              <small>{String(caption)}</small>
            </div>
          );
        })}
      </div>
      <div className="section-toolbar">
        <div>
          <h2>
            Your projects <span className="count">{projects.length}</span>
          </h2>
          <p className="muted">Pick up where you left off.</p>
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
          description="Try another search or filter."
        />
      ) : (
        <div
          className={`project-grid ${view === "list" ? "project-list" : ""}`}
        >
          {filtered.map((p) => (
            <Link href={`/project/${p.id}`} className="project-card" key={p.id}>
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
                <span>Discovery completeness</span>
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
                <span>Updated {date(p.updated_at)}</span>
                <ArrowUpRight size={18} />
              </footer>
            </Link>
          ))}
        </div>
      )}
      {health && !health.gemini_configured && (
        <div className="setup-note">
          <span className="tiny-orange" />
          <span>
            One connection away. Add your Gemini key to activate discovery.
          </span>
          <Link href="/settings">
            Connection settings <ArrowRight size={14} />
          </Link>
        </div>
      )}
    </Shell>
  );
}
