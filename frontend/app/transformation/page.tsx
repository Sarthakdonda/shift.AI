"use client";

import { T } from "@/components/locale";
import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import { Shell } from "@/components/layout/shell";
import { Section } from "@/components/analysis/report";
import { api, post, humanize } from "@/lib/api";
import type { Project } from "@/lib/types";
import type { Assessment } from "@/lib/deliverables";
type Outcome = {
  id: string;
  metric: string;
  unit: string;
  baseline: number;
  target: number;
  observed: number;
  note: string;
  created_at: string;
};
type Row = {
  project: Project;
  assessments: Assessment[];
  current_deliverables: string[];
  approved_deliverables: string[];
  open_design_findings: number;
  outcomes: Outcome[];
};
export default function Transformation() {
  const [rows, setRows] = useState<Row[]>([]),
    [error, setError] = useState(""),
    [pid, setPid] = useState(""),
    [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    metric: "",
    unit: "",
    baseline: 0,
    target: 0,
    observed: 0,
    note: "",
  });
  const load = useCallback(
    async () => setRows(await api<Row[]>("/transformation")),
    [],
  );
  useEffect(() => {
    void load().catch((e) => setError(e.message));
  }, [load]);
  return (
    <Shell>
      <div className="page-heading">
        <h1>
          <T text={"Transformation dashboard"} />
        </h1>
        <p>
          <T
            text={
              "Track evidence, design coverage, approvals, and measured business outcomes."
            }
          />
        </p>
      </div>
      {error && (
        <p role="alert" className="error-box">
          {error}
        </p>
      )}
      <Section title="Implementation readiness">
        <p>
          <T
            text={
              "Coverage counts current deliverables out of seven. Approval counts human-reviewed current versions. These indicators show preparation, not a guarantee of production readiness."
            }
          />
        </p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>
                  <T text={"Project"} />
                </th>
                <th>
                  <T text={"Discovery"} />
                </th>
                <th>
                  <T text={"Design coverage"} />
                </th>
                <th>
                  <T text={"Approved"} />
                </th>
                <th>
                  <T text={"Open findings"} />
                </th>
                <th>
                  <T text={"Stage"} />
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.project.id}>
                  <td>
                    <Link href={`/project/${r.project.id}/deliverables`}>
                      {r.project.name}
                    </Link>
                  </td>
                  <td>{r.project.discovery_scores.overall || 0}%</td>
                  <td>
                    <progress max={7} value={r.current_deliverables.length} />
                    <span>{r.current_deliverables.length}/7</span>
                  </td>
                  <td>{r.approved_deliverables.length}/7</td>
                  <td>{r.open_design_findings}</td>
                  <td>{humanize(r.project.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section title="Maturity, opportunities, and solution quality">
        <p>
          <T
            text={
              "These advisory assessments come from current business and transformation deliverables. Unknown means more evidence is needed; it does not mean a failing score."
            }
          />
        </p>
        {rows.map((r) => (
          <article key={r.project.id}>
            <h3>{r.project.name}</h3>
            {r.assessments.length ? (
              <div className="metric-grid">
                {r.assessments.map((a) => (
                  <article key={a.dimension}>
                    <h4>{humanize(a.dimension)}</h4>
                    <b>{humanize(a.rating)}</b>
                    <p>{a.reason}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p>
                <T
                  text={
                    "Generate business and transformation deliverables to assess readiness."
                  }
                />
              </p>
            )}
            <Link href={`/project/${r.project.id}/deliverables`}>
              <T text={"Review evidence and recommendations"} />
            </Link>
          </article>
        ))}
      </Section>
      <Section title="Record a business outcome">
        <p>
          <T
            text={
              "Use observed numbers from your pilot. Each submission adds a dated measurement, which informs future analysis."
            }
          />
        </p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await post(`/projects/${pid}/outcomes`, form);
              await load();
            } catch (err) {
              setError((err as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            <T text={"Project"} />
            <select
              required
              value={pid}
              onChange={(e) => setPid(e.target.value)}
            >
              <option value="">Choose a project</option>
              {rows.map((r) => (
                <option key={r.project.id} value={r.project.id}>
                  {r.project.name}
                </option>
              ))}
            </select>
          </label>
          <div className="two-columns">
            <label>
              <T text={"Metric"} />
              <input
                required
                value={form.metric}
                onChange={(e) => setForm({ ...form, metric: e.target.value })}
                placeholder="Median first response time"
                maxLength={120}
              />
            </label>
            <label>
              <T text={"Unit"} />
              <input
                required
                value={form.unit}
                onChange={(e) => setForm({ ...form, unit: e.target.value })}
                placeholder="hours"
                maxLength={50}
              />
            </label>
          </div>
          <div className="studio-actions">
            {(["baseline", "target", "observed"] as const).map((k) => (
              <label key={k}>
                {humanize(k)}
                <input
                  required
                  type="number"
                  step="any"
                  value={form[k]}
                  onChange={(e) =>
                    setForm({ ...form, [k]: Number(e.target.value) })
                  }
                />
              </label>
            ))}
          </div>
          <label>
            <T text={"Measurement notes"} />
            <textarea
              value={form.note}
              maxLength={2000}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
            />
          </label>
          <button className="button button-primary" disabled={busy}>
            <T text={"Save measurement"} />
          </button>
        </form>
      </Section>
      {rows
        .filter((r) => r.outcomes.length)
        .map((r) => (
          <Section key={r.project.id} title={`${r.project.name} · outcomes`}>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>
                      <T text={"Metric"} />
                    </th>
                    <th>
                      <T text={"Baseline"} />
                    </th>
                    <th>
                      <T text={"Target"} />
                    </th>
                    <th>
                      <T text={"Observed"} />
                    </th>
                    <th>
                      <T text={"Measured"} />
                    </th>
                    <th>
                      <T text={"Notes"} />
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {r.outcomes.map((o) => (
                    <tr key={o.id}>
                      <td>
                        {o.metric} ({o.unit})
                      </td>
                      <td>{o.baseline}</td>
                      <td>{o.target}</td>
                      <td>{o.observed}</td>
                      <td>{new Date(o.created_at).toLocaleString()}</td>
                      <td>{o.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        ))}
    </Shell>
  );
}
