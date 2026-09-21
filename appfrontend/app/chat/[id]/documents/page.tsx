"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import {
  FilePlus2,
  FileText,
  LoaderCircle,
  ShieldCheck,
  Trash2,
  Upload,
} from "lucide-react";
import { Screen } from "@/components/shell/screen";
import { useRequireAuth } from "@/components/shell/guard";
import { useSession, useToast } from "@/components/providers";
import { ConfirmSheet } from "@/components/ui/sheet";
import {
  ErrorNote,
  SkeletonBlocks,
  Splash,
  stagger,
} from "@/components/ui/states";
import { api, humanize } from "@/lib/api";
import type { Document, Project } from "@/lib/types";

export default function Documents({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { ready } = useRequireAuth();
  const { health } = useSession();
  const toast = useToast();
  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [error, setError] = useState("");
  const [action, setAction] = useState("");
  const [removing, setRemoving] = useState<Document | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [p, d] = await Promise.all([
        api<Project>(`/projects/${id}`),
        api<Document[]>(`/projects/${id}/documents`),
      ]);
      setProject(p);
      setDocuments(d);
    } catch (failure) {
      setError((failure as Error).message);
      setDocuments([]);
    }
  }, [id]);

  useEffect(() => {
    if (ready) void load();
  }, [ready, load]);

  const processing = (documents || []).some(
    (document) => document.status === "processing",
  );
  const busy = !!action || !!project?.busy;

  useEffect(() => {
    if (!processing && !project?.busy) return;
    const timer = setInterval(() => void load(), 3000);
    return () => clearInterval(timer);
  }, [processing, project?.busy, load]);

  async function upload(file?: File) {
    if (!file || busy) return;
    const limit = health?.max_upload_mb || 15;
    if (file.size > limit * 1024 * 1024) {
      setError(`Files must be ${limit} MB or smaller.`);
      return;
    }
    if (!/\.(pdf|docx|pptx|txt|csv|xlsx)$/i.test(file.name)) {
      setError("Choose a PDF, DOCX, PPTX, TXT, CSV, or XLSX file.");
      return;
    }
    const body = new FormData();
    body.append("file", file);
    setAction("upload");
    setError("");
    try {
      await api(`/projects/${id}/documents`, { method: "POST", body });
      toast("Document uploaded. We’re reading it now.");
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      await load();
      setAction("");
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  if (!ready) return <Splash />;

  return (
    <Screen
      title="Documents"
      subtitle={project?.name}
      back={`/chat/${id}`}
      actions={
        <button
          type="button"
          className="icon-btn accent"
          aria-label="Upload a document"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          {action === "upload" ? (
            <LoaderCircle size={20} className="spin" />
          ) : (
            <FilePlus2 size={20} />
          )}
        </button>
      }
    >
      <input
        ref={fileInput}
        type="file"
        hidden
        accept=".pdf,.docx,.pptx,.txt,.csv,.xlsx"
        onChange={(event) => void upload(event.target.files?.[0])}
      />

      <div className="stack-lg">
        {error && <ErrorNote message={error} onRetry={() => setError("")} />}

        <div className="dropzone">
          <span className="empty-icon">
            <Upload size={22} />
          </span>
          <h2>Bring your business into focus.</h2>
          <p>
            Optional: process notes, spreadsheets and requirements help us ask
            better questions.
          </p>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={busy}
            onClick={() => fileInput.current?.click()}
          >
            <Upload size={16} aria-hidden="true" />
            Choose a file
          </button>
          <small className="muted">
            PDF, DOCX, PPTX, TXT, CSV, XLSX · up to {health?.max_upload_mb || 15} MB
            · 20 files per project
          </small>
        </div>

        {!documents ? (
          <SkeletonBlocks rows={2} />
        ) : !documents.length ? null : (
          <div className="stack">
            <p className="eyebrow">In this project · {documents.length}</p>
            {documents.map((document, index) => (
              <article className="doc-card" key={document.id} style={stagger(index)}>
                <div className="row-between">
                  <span className="doc-type">
                    <FileText size={17} aria-hidden="true" />
                    {document.file_type.toUpperCase()}
                  </span>
                  <span
                    className={`badge ${
                      document.status === "processed"
                        ? "badge-good"
                        : document.status === "failed"
                          ? "badge-danger"
                          : "badge-accent"
                    }`}
                  >
                    {document.status === "processing" && (
                      <LoaderCircle size={11} className="spin" aria-hidden="true" />
                    )}
                    {humanize(document.status)}
                  </span>
                </div>
                <h3>{document.filename}</h3>
                <small className="muted">
                  {(document.size / 1024).toFixed(1)} KB
                  {document.chunk_count ? ` · ${document.chunk_count} text chunks` : ""}
                </small>
                <p>
                  {document.summary ||
                    (document.status === "processing"
                      ? "Reading your document and gathering useful facts…"
                      : document.error || "No summary available.")}
                </p>
                {document.warnings?.map((warning) => (
                  <p className="field-note" key={warning}>
                    {warning}
                  </p>
                ))}
                {!!document.facts?.length && (
                  <details>
                    <summary className="link" style={{ fontSize: 13 }}>
                      {document.facts.length} extracted facts
                    </summary>
                    <div className="prose" style={{ marginTop: 10 }}>
                      <ul>
                        {document.facts.map((fact, position) => (
                          <li key={position}>
                            <span>
                              {fact.fact} <em className="muted">({fact.source})</em>
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </details>
                )}
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ justifySelf: "start", color: "var(--danger)" }}
                  disabled={busy}
                  onClick={() => setRemoving(document)}
                >
                  <Trash2 size={15} aria-hidden="true" />
                  Remove
                </button>
              </article>
            ))}
          </div>
        )}

        <p className="note">
          <ShieldCheck size={16} aria-hidden="true" />
          <span>
            Text is extracted for analysis. Scanned PDFs need OCR before upload.
            Original files are not retained.
          </span>
        </p>
      </div>

      <ConfirmSheet
        open={!!removing}
        onClose={() => setRemoving(null)}
        title="Remove this document?"
        description="This removes the document and its extracted evidence. Refresh discovery and run analysis again to update your results."
        confirmLabel="Remove"
        danger
        onConfirm={async () => {
          await api(`/projects/${id}/documents/${removing?.id}`, {
            method: "DELETE",
          });
          toast("Document removed.");
          await load();
        }}
      />
    </Screen>
  );
}
