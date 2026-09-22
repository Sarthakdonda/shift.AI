"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, RefreshCw, ArrowRight, History } from "lucide-react";
import { api, post, humanize } from "@/lib/api";
import type { Analysis, Blueprint } from "@/lib/types";
import type { ReviewFinding } from "@/lib/review";

const labels = {
  open: "Still open",
  fixed: "Fixed in design",
  mitigated: "Mitigated",
  needs_input: "Needs your input",
  accepted_risk: "Risk accepted",
};
const gates = {
  blocked: "Draft · unresolved blockers",
  conditional: "Reviewed · remaining risks",
  passed: "Design review passed",
};

function readable(value: unknown, depth = 0): string {
  if (value === null || value === undefined) return "Not present";
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value))
    return value.map((v) => readable(v, depth)).join("\n\n");
  return Object.entries(value)
    .filter(
      ([key]) =>
        !["key", "component_refs", "entity_refs", "integration_refs"].includes(
          key,
        ),
    )
    .map(([key, v]) =>
      typeof v === "object"
        ? humanize(key) + ":\n" + readable(v, depth + 1)
        : humanize(key) + ": " + String(v),
    )
    .join("\n");
}

function FindingCard({
  finding,
  disabled,
  onDecision,
}: {
  finding: ReviewFinding;
  disabled: boolean;
  onDecision?: (
    finding: ReviewFinding,
    action: "answer" | "accept_risk",
    response: string,
  ) => Promise<boolean>;
}) {
  const [response, setResponse] = useState("");
  const [accepting, setAccepting] = useState(false);
  const pending = finding.status === "open" || finding.status === "needs_input";
  return (
    <article className="rt-finding" data-status={finding.status}>
      <div className="rt-row">
        <span className="rt-tag">
          {finding.id} · {finding.severity}
        </span>
        <span className="rt-status">{labels[finding.status]}</span>
      </div>
      <h3>{finding.issue}</h3>
      <p>{finding.reason}</p>
      <dl className="rt-facts">
        <div>
          <dt>Decision</dt>
          <dd>{finding.decision || finding.mitigation}</dd>
        </div>
        {!!finding.affected_sections?.length && (
          <div>
            <dt>Affected design</dt>
            <dd>{finding.affected_sections.map(humanize).join(", ")}</dd>
          </div>
        )}
        {finding.validation && (
          <div>
            <dt>Done when</dt>
            <dd>{finding.validation}</dd>
          </div>
        )}
        {finding.verification && (
          <div>
            <dt>Review result</dt>
            <dd>{finding.verification}</dd>
          </div>
        )}
        {finding.residual_risk && (
          <div>
            <dt>Remaining risk</dt>
            <dd>{finding.residual_risk}</dd>
          </div>
        )}
        {finding.acceptance_reason && (
          <div>
            <dt>Your acceptance reason</dt>
            <dd>{finding.acceptance_reason}</dd>
          </div>
        )}
      </dl>
      {finding.verification_quote && (
        <blockquote className="rt-evidence">
          <small>Design evidence · {humanize(finding.verified_section)}</small>
          <p>{finding.verification_quote}</p>
        </blockquote>
      )}
      {pending && finding.question && (
        <p className="rt-question">
          <strong>Your decision is needed:</strong> {finding.question}
        </p>
      )}
      {pending && onDecision && (
        <form
          className="rt-response"
          onSubmit={async (event) => {
            event.preventDefault();
            if (
              await onDecision(
                finding,
                accepting ? "accept_risk" : "answer",
                response.trim(),
              )
            ) {
              setResponse("");
              setAccepting(false);
            }
          }}
        >
          <label htmlFor={"response-" + finding.id}>
            {accepting
              ? "Why are you accepting this remaining risk?"
              : "Add evidence or answer this finding"}
          </label>
          <textarea
            id={"response-" + finding.id}
            required
            minLength={5}
            maxLength={12000}
            disabled={disabled}
            value={response}
            onChange={(event) => setResponse(event.target.value)}
            placeholder={
              accepting
                ? "Record your reason and any conditions…"
                : "Provide the business facts shift.AI needs…"
            }
          />
          {accepting && (
            <p className="rt-muted">
              Acceptance records your decision. It does not mark the issue as
              fixed.
            </p>
          )}
          <div className="rt-actions">
            <button
              className="rt-button"
              disabled={disabled || response.trim().length < 5}
            >
              {accepting
                ? "Confirm risk acceptance"
                : "Use answer & revise blueprint"}
              <ArrowRight size={15} />
            </button>
            <button
              type="button"
              className="rt-button rt-secondary"
              disabled={disabled}
              onClick={() => setAccepting(!accepting)}
            >
              {accepting ? "Cancel acceptance" : "Accept remaining risk"}
            </button>
          </div>
        </form>
      )}
    </article>
  );
}

export function ReviewWorkbench({
  data,
  projectId,
  version,
  busy = false,
  onRefresh,
}: {
  data: Analysis;
  projectId?: string;
  version?: number;
  busy?: boolean;
  onRefresh?: () => Promise<void>;
}) {
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [versions, setVersions] = useState<
    { version: number; created_at: string }[]
  >([]);
  const [preview, setPreview] = useState<Blueprint | null>(null);
  const [restoreConfirm, setRestoreConfirm] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [showVersions, setShowVersions] = useState(false);
  const ledger = data.review_ledger || [];
  const disabled = busy || working;
  const writable = !!(projectId && version && onRefresh);
  useEffect(() => {
    setPreview(null);
    setRestoreConfirm(false);
    setNotice((current) =>
      current.startsWith("Review started.") ? "" : current,
    );
  }, [version]);
  async function revise(
    action: "review" | "answer" | "accept_risk",
    finding?: ReviewFinding,
    response = "",
  ) {
    if (!writable || disabled) return false;
    setWorking(true);
    setError("");
    setNotice("");
    try {
      await post(`/projects/${projectId}/red-team/revise`, {
        version,
        action,
        finding_id: finding?.id || "",
        response,
      });
      setNotice(
        "Review started. The revised blueprint will be saved as a new version.",
      );
      await onRefresh?.();
      return true;
    } catch (failure) {
      setError((failure as Error).message);
      return false;
    } finally {
      setWorking(false);
    }
  }
  return (
    <section className="rt-workbench" aria-label="Red Team revisions">
      <header className="rt-header">
        <div className="rt-row">
          <span className="rt-kicker">
            <ShieldCheck size={17} /> Red Team outcomes
          </span>
          {version && <span className="rt-tag">Blueprint v{version}</span>}
        </div>
        <h2>
          {busy
            ? "Reviewing and revising your design…"
            : data.review_gate
              ? gates[data.review_gate]
              : "Review this saved blueprint"}
        </h2>
        <p>
          Follow every finding from decision to design change and verification.
          Verification checks the proposed design; implementation tests still
          need to be run.
        </p>
        {!!ledger.length && (
          <div className="rt-counts">
            {(
              [
                "fixed",
                "mitigated",
                "needs_input",
                "open",
                "accepted_risk",
              ] as const
            ).map((status) => (
              <span key={status}>
                <b>{ledger.filter((f) => f.status === status).length}</b>
                {labels[status]}
              </span>
            ))}
          </div>
        )}
        {writable && (
          <div className="rt-actions">
            <button
              type="button"
              className="rt-button"
              disabled={disabled}
              onClick={() => void revise("review")}
            >
              <RefreshCw size={15} />
              {disabled ? "Working…" : "Review & improve blueprint"}
            </button>
            <button
              type="button"
              className="rt-button rt-secondary"
              disabled={disabled}
              onClick={async () => {
                setError("");
                try {
                  setVersions(
                    await api(`/projects/${projectId}/blueprint/versions`),
                  );
                  setShowVersions(!showVersions);
                } catch (failure) {
                  setError((failure as Error).message);
                }
              }}
            >
              <History size={15} />
              Version history
            </button>
          </div>
        )}
      </header>
      {error && (
        <p className="rt-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="rt-notice" role="status">
          {notice}
        </p>
      )}
      {showVersions && (
        <div className="rt-history">
          <h3>Saved blueprint versions</h3>
          <div className="rt-actions">
            {versions.map((item) => (
              <button
                className="rt-button rt-secondary"
                type="button"
                key={item.version}
                disabled={disabled || previewLoading}
                onClick={async () => {
                  setError("");
                  setRestoreConfirm(false);
                  setPreviewLoading(true);
                  try {
                    setPreview(
                      await api<Blueprint>(
                        `/projects/${projectId}/blueprint/versions/${item.version}`,
                      ),
                    );
                  } catch (failure) {
                    setError((failure as Error).message);
                  } finally {
                    setPreviewLoading(false);
                  }
                }}
              >
                v{item.version} ·{" "}
                {new Date(item.created_at).toLocaleDateString()}
              </button>
            ))}
          </div>
          {preview && (
            <div className="rt-version">
              <h3>
                Version {preview.version}
                {preview.version === version ? " · current" : ""}
              </h3>
              <p>
                {preview.content.conclusion?.recommendation ||
                  preview.content.solution?.summary}
              </p>
              <p className="rt-muted">
                {preview.content.review_gate
                  ? gates[preview.content.review_gate]
                  : "Earlier review format"}
              </p>
              <details>
                <summary>Read this saved design</summary>
                <pre>
                  {readable(
                    preview.content.final_report || preview.content.solution,
                  )}
                </pre>
              </details>
              {preview.version !== version && (
                <div className="rt-actions">
                  {!restoreConfirm ? (
                    <button
                      type="button"
                      className="rt-button rt-secondary"
                      disabled={disabled}
                      onClick={() => setRestoreConfirm(true)}
                    >
                      Restore this version…
                    </button>
                  ) : (
                    <>
                      <p>
                        This creates a new copy as the current blueprint.
                        Existing versions stay available.
                      </p>
                      <button
                        type="button"
                        className="rt-button"
                        disabled={disabled}
                        onClick={async () => {
                          setWorking(true);
                          setError("");
                          try {
                            await post(
                              `/projects/${projectId}/blueprint/versions/${preview.version}/restore`,
                              { version },
                            );
                            await onRefresh?.();
                            setNotice(
                              "Earlier design restored as a new version.",
                            );
                            setShowVersions(false);
                          } catch (failure) {
                            setError((failure as Error).message);
                          } finally {
                            setWorking(false);
                            setRestoreConfirm(false);
                          }
                        }}
                      >
                        Confirm restore
                      </button>
                      <button
                        type="button"
                        className="rt-button rt-secondary"
                        disabled={disabled}
                        onClick={() => setRestoreConfirm(false)}
                      >
                        Cancel
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
      {ledger.map((finding) => (
        <FindingCard
          key={finding.id}
          finding={finding}
          disabled={disabled}
          onDecision={
            writable
              ? (f, action, response) => revise(action, f, response)
              : undefined
          }
        />
      ))}
      {!!data.design_changes?.length && (
        <section className="rt-changes">
          <h3>What changed in the blueprint</h3>
          {data.design_changes.map((change, index) => (
            <article key={index} className="rt-change">
              <div className="rt-row">
                <strong>Revision {index + 1}</strong>
                <span className="rt-tag">Review cycle {change.cycle}</span>
              </div>
              <p>{change.decisions?.join(" ")}</p>
              <p className="rt-muted">{change.finding_ids?.join(" · ")}</p>
              {change.changed_sections.length ? (
                <p>{change.changed_sections.map(humanize).join(", ")}</p>
              ) : (
                <p>
                  No design content changed in this pass. This does not resolve
                  a finding.
                </p>
              )}
              {change.diffs?.map((diff) => (
                <details key={diff.section}>
                  <summary>{humanize(diff.section)} · before / after</summary>
                  <div className="rt-compare">
                    <div>
                      <h4>Before</h4>
                      <pre>{readable(diff.before)}</pre>
                    </div>
                    <div>
                      <h4>After</h4>
                      <pre>{readable(diff.after)}</pre>
                    </div>
                  </div>
                </details>
              ))}
            </article>
          ))}
        </section>
      )}
    </section>
  );
}
