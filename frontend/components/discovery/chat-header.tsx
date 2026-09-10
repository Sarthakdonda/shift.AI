"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowUpRight,
  Ellipsis,
  Files,
  LoaderCircle,
  PanelRightOpen,
  Trash2,
} from "lucide-react";
import { T, LanguagePicker } from "@/components/locale";
import { SidebarToggle } from "@/components/layout/shell";
import { Popover } from "@/components/ui/popover";
import { DiscoveryProgress } from "@/components/discovery/stage-progress";
import { humanize } from "@/lib/api";
import type { Project } from "@/lib/types";

/**
 * A deliberately quiet header: enough orientation to know where you are,
 * with the workflow, context and project actions one click away.
 */
export function ChatHeader({
  project,
  documentCount,
  contextOpen,
  onToggleContext,
  onDelete,
}: {
  project: Project;
  documentCount: number;
  contextOpen: boolean;
  onToggleContext: () => void;
  onDelete: () => void;
}) {
  const overall = project.discovery_scores?.overall || 0;
  const documentsHref = `/project/${project.id}/documents`;
  const [menu, setMenu] = useState(false);
  return (
    <header className="dx-header">
      <div className="dx-header-left">
        <SidebarToggle />
        <div className="dx-title">
          <Link className="dx-crumb" href="/dashboard">
            <T text={"Workspace"} />
          </Link>
          <h1 title={project.name}>{project.name}</h1>
        </div>
        {project.busy ? (
          <span className="dx-header-status" role="status">
            <LoaderCircle size={13} className="spin" />
            {humanize(project.status)}
          </span>
        ) : (
          <span className="dx-header-status is-idle">
            {humanize(project.status)}
          </span>
        )}
      </div>
      <div className="dx-header-right">
        <DiscoveryProgress status={project.status} projectId={project.id} />
        <button
          type="button"
          className={`dx-header-chip ${contextOpen ? "is-active" : ""}`}
          aria-expanded={contextOpen}
          onClick={onToggleContext}
        >
          <PanelRightOpen size={14} />
          <span className="dx-chip-text">
            <T text={"Context"} />
          </span>
          <strong>{overall}%</strong>
        </button>
        <Link
          href={documentsHref}
          className="dx-icon-button dx-docs-button"
          aria-label="Project documents"
          title="Project documents"
        >
          <Files size={17} />
          {!!documentCount && <span aria-hidden>{documentCount}</span>}
        </Link>
        {project.status === "BLUEPRINT_READY" && (
          <Link
            href={`/project/${project.id}/blueprint`}
            className="dx-header-chip dx-header-cta"
            aria-label="View blueprint"
          >
            <span className="dx-chip-text">
              <T text={"View blueprint"} />
            </span>
            <ArrowUpRight size={14} />
          </Link>
        )}
        <Popover
          label="Project actions"
          align="end"
          side="bottom"
          width={264}
          className="dx-pop-menu"
          open={menu}
          onOpenChange={setMenu}
          trigger={(props) => (
            <button
              {...props}
              type="button"
              className="dx-icon-button"
              aria-label="Project actions"
              title="Project actions"
            >
              <Ellipsis size={17} />
            </button>
          )}
        >
          <p className="dx-pop-label">
            <T text={"Interface language"} />
          </p>
          <div className="dx-pop-field">
            <LanguagePicker />
          </div>
          <button
            type="button"
            className="dx-pop-option dx-pop-danger"
            aria-label="Delete project"
            onClick={() => {
              setMenu(false);
              onDelete();
            }}
          >
            <span>
              <strong>
                <Trash2 size={14} />
                <T text={"Delete project"} />
              </strong>
              <small>
                <T text={"Removes messages, documents and blueprints"} />
              </small>
            </span>
          </button>
        </Popover>
      </div>
    </header>
  );
}
