"use client";

import Link from "next/link";
import { ArrowUpRight, FileText, Upload, X } from "lucide-react";
import { T } from "@/components/locale";
import { humanize } from "@/lib/api";
import type { Document, Project } from "@/lib/types";

const categories = [
  "business",
  "problem",
  "workflow",
  "people",
  "technology",
  "data",
  "constraints",
  "impact",
  "integrations",
  "outcome",
];

/**
 * Context panel — the same discovery scores, facts and gaps the workspace
 * already received from the API, moved out of the conversation's way.
 * Nothing here is recalculated on the client.
 */
export function ContextPanel({
  project,
  documents,
  documentsHref,
  overlay,
  onClose,
  onUpload,
}: {
  project: Project;
  documents: Document[];
  documentsHref: string;
  overlay: boolean;
  onClose: () => void;
  onUpload: () => void;
}) {
  const overall = project.discovery_scores?.overall || 0;
  const facts = project.discovery?.collected_information || [];
  const open = [
    ...(project.discovery?.critical_missing || []),
    ...(project.discovery?.missing_information || []),
  ];
  const unique = Array.from(new Set(open)).slice(0, 6);

  return (
    <aside
      className="dx-context"
      role={overlay ? "dialog" : "complementary"}
      aria-modal={overlay || undefined}
      aria-label="Context and evidence"
    >
      <header className="dx-context-head">
        <div>
          <h2>
            <T text={"Understanding"} />
          </h2>
          <small>
            <T text={"Context gathered, not certainty."} />
          </small>
        </div>
        <strong className="dx-context-total">{overall}%</strong>
        <button
          type="button"
          className="dx-icon-button"
          aria-label="Close context panel"
          onClick={onClose}
        >
          <X size={17} />
        </button>
      </header>
      <div className="dx-context-body">
        <div className="dx-meter dx-meter-total">
          <span style={{ width: `${overall}%` }} />
        </div>
        <section>
          {categories.map((key) => (
            <div className="dx-score" key={key}>
              <div>
                <span>{humanize(key)}</span>
                <small>{project.discovery_scores?.[key] || 0}%</small>
              </div>
              <div className="dx-meter">
                <span
                  style={{ width: `${project.discovery_scores?.[key] || 0}%` }}
                />
              </div>
            </div>
          ))}
        </section>
        {!!unique.length && (
          <section className="dx-context-block">
            <h3>
              <T text={"Open questions"} />
            </h3>
            <ul>
              {unique.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        )}
        {!!facts.length && (
          <section className="dx-context-block">
            <h3>
              <T text={"Known facts"} />
            </h3>
            <ul>
              {facts.slice(0, 8).map((fact, index) => (
                <li key={`${fact.fact}-${index}`}>
                  {fact.fact}
                  <small>{humanize(fact.category)}</small>
                </li>
              ))}
            </ul>
          </section>
        )}
        <section className="dx-context-block">
          <h3>
            <T text={"Supporting documents"} />
          </h3>
          {documents.length ? (
            <div className="dx-context-docs">
              {documents.map((document) => (
                <Link
                  key={document.id}
                  href={documentsHref}
                  className="dx-doc-chip"
                >
                  <FileText size={12} />
                  <span>{document.filename}</span>
                </Link>
              ))}
            </div>
          ) : (
            <p className="dx-context-muted">
              <T text={"No documents yet. Evidence is optional but helps."} />
            </p>
          )}
          <div className="dx-context-actions">
            <button type="button" className="dx-text-link" onClick={onUpload}>
              <Upload size={14} />
              <T text={"Upload a document"} />
            </button>
            <Link className="dx-text-link" href={documentsHref}>
              <T text={"Manage documents"} />
              <ArrowUpRight size={14} />
            </Link>
          </div>
        </section>
      </div>
    </aside>
  );
}
