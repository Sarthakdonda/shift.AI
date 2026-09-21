"use client";

import { useState } from "react";
import { Download, LoaderCircle } from "lucide-react";
import { Select } from "@/components/ui/select";
import { T } from "@/components/locale";
import { API_BASE } from "@/lib/api";
import styles from "./download.module.css";

const formats = [
  { value: "pdf", label: "PDF document (.pdf)" },
  { value: "docx", label: "Word document (.docx)" },
  { value: "xlsx", label: "Excel workbook (.xlsx)" },
  { value: "pptx", label: "PowerPoint slides (.pptx)" },
  { value: "md", label: "Markdown (.md)" },
  { value: "json", label: "Structured data (.json)" },
  { value: "zip", label: "Document bundle (.zip)" },
];

export function DeliverableDownload({
  projectId,
  kind,
  version,
  editing,
}: {
  projectId: string;
  kind: string;
  version?: number;
  editing: boolean;
}) {
  const [format, setFormat] = useState("pdf");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const unavailable = !version || editing;
  async function download() {
    if (busy || unavailable) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(
        `${API_BASE}/api/projects/${projectId}/export/${kind}/${format}?version=${version}`,
        {
          credentials: "include",
          signal: AbortSignal.timeout(120000),
        },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(
          response.status === 401
            ? "Your session expired. Sign in again to download this file."
            : typeof body.detail === "string"
              ? body.detail
              : "The download could not be prepared. Please try again.",
        );
      }
      // A proxy can return a login/error HTML page with status 200.
      if (response.headers.get("Content-Type")?.includes("text/html")) {
        throw new Error(
          "The download is temporarily unavailable. Please try again.",
        );
      }
      const blob = await response.blob();
      if (!blob.size)
        throw new Error("The downloaded file was empty. Please try again.");
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `shift-ai-${kind}-v${version}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      // Give the browser time to consume the object URL before releasing it.
      window.setTimeout(() => URL.revokeObjectURL(url), 10000);
      setNotice(`Download started for version ${version}.`);
    } catch (cause) {
      setError(
        cause instanceof Error &&
          cause.name !== "TypeError" &&
          cause.name !== "TimeoutError"
          ? cause.message
          : "We couldn’t download the file. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={`${styles.panel} no-print`}>
      <div className={styles.row}>
        <label className={styles.format}>
          <T text="Download format" />
          <Select
            aria-label="Download format"
            value={format}
            onValueChange={setFormat}
            disabled={busy}
            options={
              kind === "process"
                ? [
                    ...formats,
                    { value: "bpmn", label: "Process diagram (.bpmn)" },
                  ]
                : formats
            }
          />
        </label>
        <button
          type="button"
          className="button button-secondary"
          disabled={busy || unavailable}
          onClick={() => void download()}
        >
          {busy ? (
            <LoaderCircle
              size={16}
              className={styles.spinner}
              aria-hidden="true"
            />
          ) : (
            <Download size={16} aria-hidden="true" />
          )}
          <T text={busy ? "Preparing download…" : "Download file"} />
        </button>
        <span className={styles.hint}>
          {editing ? (
            <T text="Save or discard your changes before downloading." />
          ) : !version ? (
            <T text="Generate or save a draft to enable downloads." />
          ) : (
            <>
              <T text="Saved version" /> {version}
            </>
          )}
        </span>
      </div>
      {error && (
        <p role="alert" className="error-box">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className={styles.hint}>
          {notice}
        </p>
      )}
    </div>
  );
}
