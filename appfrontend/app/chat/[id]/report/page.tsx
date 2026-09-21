"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useState } from "react";
import {
  Copy,
  Download,
  FileDown,
  FileText,
  LoaderCircle,
  Share2,
  Sparkles,
} from "lucide-react";
import { Screen } from "@/components/shell/screen";
import { useRequireAuth } from "@/components/shell/guard";
import { useToast } from "@/components/providers";
import { Sheet } from "@/components/ui/sheet";
import {
  EmptyState,
  ErrorNote,
  SkeletonBlocks,
  Splash,
} from "@/components/ui/states";
import {
  DiagnosisReport,
  ImplementationReport,
  ReviewReport,
  SolutionReport,
} from "@/components/report/sections";
import { API_BASE, api, date, humanize } from "@/lib/api";
import { blueprintMarkdown } from "@/lib/blueprint";
import type { Analysis, Blueprint, Project } from "@/lib/types";

const VIEWS = [
  ["diagnosis", "Diagnosis"],
  ["solution", "Solution"],
  ["review", "Red Team"],
  ["blueprint", "Blueprint"],
] as const;

type View = (typeof VIEWS)[number][0];

export default function Report({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { ready } = useRequireAuth();
  const toast = useToast();
  const [project, setProject] = useState<Project | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("diagnosis");
  const [share, setShare] = useState(false);
  const [downloading, setDownloading] = useState("");

  const load = useCallback(async () => {
    try {
      const [p, a, b] = await Promise.all([
        api<Project>(`/projects/${id}`),
        api<Analysis | null>(`/projects/${id}/analysis`),
        api<Blueprint | null>(`/projects/${id}/blueprint`),
      ]);
      setProject(p);
      setAnalysis(a);
      setBlueprint(b);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (ready) void load();
  }, [ready, load]);

  useEffect(() => {
    if (!project?.busy) return;
    const timer = setInterval(() => void load(), 3000);
    return () => clearInterval(timer);
  }, [project?.busy, load]);

  const available = useMemo(
    () => ({
      diagnosis: !!analysis?.workflow_analysis || !!analysis?.root_cause,
      solution: !!analysis?.solution,
      review: !!analysis?.red_team || !!analysis?.business_value,
      blueprint: !!blueprint,
    }),
    [analysis, blueprint],
  );

  // Open on the most complete section the project has actually produced.
  useEffect(() => {
    if (loading) return;
    const best = [...VIEWS].reverse().find(([key]) => available[key]);
    if (best) setView(best[0]);
  }, [loading, available]);

  async function download(format: "pdf" | "docx") {
    if (!blueprint || !project) return;
    setDownloading(format);
    setError("");
    const url = `${API_BASE}/api/projects/${id}/export/blueprint/${format}?version=${blueprint.version}`;
    try {
      // The Android shell downloads authenticated URLs through its own manager.
      if (navigator.userAgent.includes("ShiftAIAndroid/")) {
        const link = document.createElement("a");
        link.href = url;
        document.body.appendChild(link);
        link.click();
        link.remove();
        toast("Download requested. Check Downloads on your device.");
        return;
      }
      const response = await fetch(url, {
        credentials: "include",
        signal: AbortSignal.timeout(120000),
      });
      if (!response.ok) throw new Error("download failed");
      const blob = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = blob;
      link.download = `${project.name
        .replace(/[^a-z0-9]+/gi, "-")
        .slice(0, 80)}-blueprint.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(blob), 1000);
      toast("Blueprint downloaded.");
    } catch {
      setError(`Could not download the ${format.toUpperCase()}. Please try again.`);
    } finally {
      setDownloading("");
      setShare(false);
    }
  }

  if (!ready) return <Splash />;

  if (loading) {
    return (
      <Screen title="Report" back={`/chat/${id}`}>
        <SkeletonBlocks />
      </Screen>
    );
  }

  if (!project) {
    return (
      <Screen title="Report" back="/chats">
        <ErrorNote
          message={error || "That project could not be opened."}
          onRetry={() => {
            setError("");
            setLoading(true);
            void load();
          }}
        />
      </Screen>
    );
  }

  const anything = Object.values(available).some(Boolean);

  return (
    <Screen
      title={project.name}
      subtitle={humanize(project.status)}
      back={`/chat/${id}`}
      padded={false}
      actions={
        blueprint ? (
          <button
            type="button"
            className="icon-btn accent"
            aria-label="Share or download the blueprint"
            onClick={() => setShare(true)}
          >
            <Share2 size={20} />
          </button>
        ) : undefined
      }
      below={
        anything ? (
          <div className="report-nav">
            <div className="segmented" role="tablist" aria-label="Report sections">
              {VIEWS.map(([key, label]) => (
                <button
                  type="button"
                  role="tab"
                  key={key}
                  aria-selected={view === key}
                  data-active={view === key ? "true" : undefined}
                  disabled={!available[key]}
                  style={available[key] ? undefined : { opacity: 0.45 }}
                  onClick={() => setView(key)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        ) : undefined
      }
    >
      <div className="report">
        {error && <ErrorNote message={error} onRetry={() => setError("")} />}

        {project.busy && (
          <p className="note note-accent" role="status">
            <LoaderCircle size={16} className="spin" aria-hidden="true" />
            <span>
              <strong>{humanize(project.status)} in progress.</strong> Your work is
              saved and this screen refreshes itself.
            </span>
          </p>
        )}

        {!anything ? (
          <EmptyState
            icon={<Sparkles size={26} />}
            title={
              project.busy
                ? "Your analysis is taking shape."
                : "Good answers start with good context."
            }
            description={
              project.busy
                ? "Each stage appears here as it completes."
                : "Finish discovery, then run analysis to see your diagnosis, solution and Red Team review."
            }
            action="Back to the conversation"
            href={`/chat/${id}`}
          />
        ) : view === "diagnosis" ? (
          analysis && <DiagnosisReport data={analysis} />
        ) : view === "solution" ? (
          analysis?.solution && <SolutionReport solution={analysis.solution} />
        ) : view === "review" ? (
          analysis && <ReviewReport data={analysis} />
        ) : (
          blueprint && (
            <>
              <div className="section">
                <div className="row" style={{ flexWrap: "wrap" }}>
                  <span className="badge badge-good">
                    <FileText size={12} aria-hidden="true" />
                    Version {blueprint.version}
                  </span>
                  <span className="badge">{date(blueprint.created_at)}</span>
                </div>
                <div className="section-head">
                  <h2>{project.name}</h2>
                  <p>From business context to a clear, reviewed direction.</p>
                </div>
                <button
                  type="button"
                  className="btn btn-primary btn-block"
                  onClick={() => setShare(true)}
                >
                  <Download size={16} aria-hidden="true" />
                  Share or download
                </button>
                {!blueprint.content.final_report && (
                  <p className="field-note">
                    This saved report uses the earlier format. Run analysis again to
                    add solution options and the complete implementation design.
                  </p>
                )}
              </div>
              {blueprint.content.final_report ? (
                <ImplementationReport report={blueprint.content.final_report} />
              ) : (
                <>
                  <DiagnosisReport data={blueprint.content} />
                  {blueprint.content.solution && (
                    <SolutionReport solution={blueprint.content.solution} />
                  )}
                  <ReviewReport data={blueprint.content} />
                </>
              )}
            </>
          )
        )}

        {anything && (
          <Link className="btn btn-secondary btn-block" href={`/chat/${id}`}>
            Back to the conversation
          </Link>
        )}
      </div>

      <Sheet
        open={share}
        onClose={() => setShare(false)}
        title="Share the blueprint"
        description="Exports are generated from the saved version on your workspace."
      >
        <div className="sheet-body" style={{ display: "grid", gap: 4 }}>
          <button
            type="button"
            className="sheet-option"
            onClick={async () => {
              if (!blueprint) return;
              const text = blueprintMarkdown(project.name, blueprint.content);
              try {
                if (navigator.share) await navigator.share({ title: project.name, text });
                else {
                  await navigator.clipboard.writeText(text);
                  toast("Blueprint copied to clipboard.");
                }
                setShare(false);
              } catch {
                setError("Sharing was blocked. Try downloading instead.");
              }
            }}
          >
            <span>
              <Copy size={16} aria-hidden="true" />
            </span>
            <span className="sheet-option-body">
              <strong>Share as text</strong>
              <small>Markdown, ready to paste anywhere</small>
            </span>
            <span />
          </button>
          <button
            type="button"
            className="sheet-option"
            disabled={!!downloading}
            onClick={() => void download("pdf")}
          >
            <span>
              {downloading === "pdf" ? (
                <LoaderCircle size={16} className="spin" aria-hidden="true" />
              ) : (
                <FileDown size={16} aria-hidden="true" />
              )}
            </span>
            <span className="sheet-option-body">
              <strong>Download PDF</strong>
              <small>Saved to your device Downloads</small>
            </span>
            <span />
          </button>
          {blueprint?.content.final_report && (
            <button
              type="button"
              className="sheet-option"
              disabled={!!downloading}
              onClick={() => void download("docx")}
            >
              <span>
                {downloading === "docx" ? (
                  <LoaderCircle size={16} className="spin" aria-hidden="true" />
                ) : (
                  <FileText size={16} aria-hidden="true" />
                )}
              </span>
              <span className="sheet-option-body">
                <strong>Download Word</strong>
                <small>Editable .docx of the full report</small>
              </span>
              <span />
            </button>
          )}
        </div>
      </Sheet>
    </Screen>
  );
}
