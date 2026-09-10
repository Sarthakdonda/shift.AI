"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUpRight,
  Ellipsis,
  MessageSquare,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { T } from "@/components/locale";
import { Popover } from "@/components/ui/popover";
import { ConfirmDialog, useToast } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";

/**
 * Conversation navigation for the sidebar.
 *
 * shift.AI has no separate conversation entity: a project *is* a conversation,
 * so the list reuses the existing `GET /projects` response (already sorted by
 * the server, newest first) and groups it by activity date on the client.
 * Search filters the loaded list locally — no new endpoint is involved.
 */
export function ChatHistory({
  projectId,
  collapsed,
  onNavigate,
}: {
  projectId?: string;
  collapsed: boolean;
  onNavigate: () => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [removing, setRemoving] = useState<Project | null>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const search = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const notify = useToast();

  const load = useCallback(async () => {
    try {
      setProjects(await api<Project[]>("/projects"));
    } catch {
      // The sidebar must never block the workspace; the page shows load errors.
      setProjects([]);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, projectId]);

  useEffect(() => {
    if (searching) search.current?.focus();
  }, [searching]);

  const groups = useMemo(() => {
    const term = query.trim().toLowerCase();
    const matched = projects.filter((p) =>
      term
        ? `${p.name} ${p.industry} ${p.initial_problem}`
            .toLowerCase()
            .includes(term)
        : true,
    );
    const startOfToday = new Date();
    startOfToday.setHours(0, 0, 0, 0);
    const day = 86400000;
    const buckets: { label: string; items: Project[] }[] = [
      { label: "Today", items: [] },
      { label: "Yesterday", items: [] },
      { label: "Previous 7 days", items: [] },
      { label: "Earlier", items: [] },
    ];
    for (const project of matched) {
      const stamp = new Date(
        project.updated_at || project.created_at,
      ).getTime();
      const age = startOfToday.getTime() - stamp;
      const index = age < 0 ? 0 : age < day ? 1 : age < day * 7 ? 2 : 3;
      buckets[index].items.push(project);
    }
    return buckets.filter((bucket) => bucket.items.length);
  }, [projects, query]);

  if (collapsed)
    return (
      <div className="dx-rail-group">
        <Link
          className="dx-rail-item"
          href="/project/new"
          title="New conversation"
          aria-label="New conversation"
          onClick={onNavigate}
        >
          <Plus size={18} />
        </Link>
        <Link
          className="dx-rail-item"
          href="/dashboard"
          title="Search conversations"
          aria-label="Search conversations"
          onClick={onNavigate}
        >
          <Search size={18} />
        </Link>
      </div>
    );

  return (
    <div className="dx-history">
      <Link className="dx-new" href="/project/new" onClick={onNavigate}>
        <Plus size={16} />
        <T text={"New conversation"} />
      </Link>

      {searching ? (
        <div className="dx-search">
          <Search size={15} />
          <input
            ref={search}
            aria-label="Search conversations"
            placeholder="Search conversations…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Escape") return;
              event.preventDefault();
              setQuery("");
              setSearching(false);
            }}
          />
          <button
            type="button"
            aria-label="Close search"
            onClick={() => {
              setQuery("");
              setSearching(false);
            }}
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <button
          type="button"
          className="dx-search dx-search-idle"
          onClick={() => setSearching(true)}
        >
          <Search size={15} />
          <span>
            <T text={"Search conversations…"} />
          </span>
        </button>
      )}

      <div className="dx-history-scroll">
        {!loaded ? (
          <div className="dx-history-skeleton" aria-hidden>
            {[0, 1, 2, 3].map((i) => (
              <span key={i} />
            ))}
          </div>
        ) : !groups.length ? (
          <p className="dx-history-empty">
            {query ? (
              <T text={"No conversation matches that search."} />
            ) : (
              <T text={"Your conversations will appear here."} />
            )}
          </p>
        ) : (
          groups.map((group) => (
            <section key={group.label}>
              <p className="dx-group-label">
                <T text={group.label} />
              </p>
              {group.items.map((project) => (
                <div
                  key={project.id}
                  className={`dx-chat-item ${project.id === projectId ? "is-active" : ""}`}
                >
                  <Link
                    href={`/project/${project.id}`}
                    onClick={onNavigate}
                    aria-current={project.id === projectId ? "page" : undefined}
                    title={project.name}
                  >
                    <MessageSquare size={14} />
                    <span>{project.name}</span>
                  </Link>
                  <Popover
                    label={`Actions for ${project.name}`}
                    align="start"
                    side="bottom"
                    width={210}
                    open={menuFor === project.id}
                    onOpenChange={(next) =>
                      setMenuFor(next ? project.id : null)
                    }
                    trigger={(props) => (
                      <button
                        {...props}
                        type="button"
                        className="dx-chat-more"
                        aria-label={`More options for ${project.name}`}
                      >
                        <Ellipsis size={15} />
                      </button>
                    )}
                  >
                    <Link
                      className="dx-pop-item"
                      href={`/project/${project.id}`}
                      onClick={onNavigate}
                    >
                      <ArrowUpRight size={15} />
                      <T text={"Open conversation"} />
                    </Link>
                    <button
                      type="button"
                      className="dx-pop-item dx-pop-danger"
                      onClick={() => {
                        setMenuFor(null);
                        setRemoving(project);
                      }}
                    >
                      <Trash2 size={15} />
                      <T text={"Delete conversation"} />
                    </button>
                  </Popover>
                </div>
              ))}
            </section>
          ))
        )}
      </div>

      <ConfirmDialog
        open={!!removing}
        onOpenChange={(open) => {
          if (!open) setRemoving(null);
        }}
        title="Delete this conversation?"
        description="The project, its messages, documents, and blueprints are permanently deleted. This cannot be undone."
        confirmLabel="Delete"
        danger
        onConfirm={async () => {
          const target = removing!;
          await api(`/projects/${target.id}`, { method: "DELETE" });
          notify("Conversation deleted.");
          setRemoving(null);
          if (target.id === projectId) router.push("/dashboard");
          else await load();
        }}
      />
    </div>
  );
}
