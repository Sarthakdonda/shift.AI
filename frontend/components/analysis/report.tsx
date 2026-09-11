"use client";

import { T } from "@/components/locale";
import {
  ArrowRight,
  Check,
  ShieldCheck,
  Sparkles,
  Workflow,
  AlertTriangle,
} from "lucide-react";
import { Analysis, Finding, Necessity } from "@/lib/types";
import { humanize } from "@/lib/api";
import { ImplementationReport } from "@/components/blueprint/implementation-report";

export function BulletList({ items }: { items: string[] }) {
  return items.length ? (
    <ul className="report-list">
      {items.map((s, i) => (
        <li key={i}>{s}</li>
      ))}
    </ul>
  ) : (
    <p className="muted">
      <T text={"None identified in the available evidence."} />
    </p>
  );
}
export function Section({
  title,
  children,
  subtitle,
}: {
  title: string;
  children: React.ReactNode;
  subtitle?: string;
}) {
  return (
    <section className="panel report-section">
      <h2>
        <T text={title} />
      </h2>
      {subtitle && <p className="section-subtitle">{subtitle}</p>}
      {children}
    </section>
  );
}
export function Decision({ value }: { value: Necessity }) {
  const noAi = [
    "AUTOMATION_SUFFICIENT",
    "PROCESS_IMPROVEMENT",
    "EXISTING_SOFTWARE_SUFFICIENT",
  ].includes(value.classification);
  return (
    <section className={`decision-card ${noAi ? "no-ai" : ""}`}>
      <div className="decision-top">
        <div>
          <span className="eyebrow">
            <T text={"AI necessity decision"} />
          </span>
          <h2>{humanize(value.classification)}</h2>
          <p>{value.recommended_approach}</p>
        </div>
        <div className="score-circle">
          <strong>
            {value.score}
            <small>/100</small>
          </strong>
          <span>
            <T text={"AI necessity"} />
          </span>
        </div>
      </div>
      <div className="decision-reasons">
        <h3>
          <T text={"Why this direction"} />
        </h3>
        <BulletList items={value.reasoning} />
      </div>
      <div className="alternative">
        <Workflow size={19} />
        <div>
          <strong>
            {noAi ? "A practical path without AI" : "The non-AI alternative"}
          </strong>
          <p>{value.non_ai_alternative}</p>
        </div>
      </div>
      <p className="score-note">
        <T
          text={"Advisory heuristic, not a scientific measurement. Confidence:"}
        />{" "}
        {Math.round(value.confidence * 100)}%.
      </p>
    </section>
  );
}
export function Findings({ findings }: { findings: Finding[] }) {
  return (
    <div className="findings">
      {!findings.length && (
        <p className="muted">
          <T text={"No findings were identified in this review."} />
        </p>
      )}
      {findings.map((f, i) => (
        <article className="finding" key={i}>
          <div className="row-between">
            <span className={`badge severity-${f.severity.toLowerCase()}`}>
              {f.severity}
            </span>
            <span className="muted small">{humanize(f.category)}</span>
          </div>
          <h3>{f.issue}</h3>
          <p>{f.reason}</p>
          <div className="mitigation">
            <ShieldCheck size={17} />
            <div>
              <strong>
                <T text={"Mitigation"} />
              </strong>
              <p>{f.mitigation}</p>
            </div>
          </div>
          {f.requires_revision && (
            <span className="finding-open">
              <AlertTriangle size={13} />
              <T text={" Requires further attention"} />
            </span>
          )}
        </article>
      ))}
    </div>
  );
}
export function DiagnosisReport({ data }: { data: Analysis }) {
  const w = data.workflow_analysis,
    r = data.root_cause;
  return (
    <div className="report-stack">
      {data.ai_necessity && <Decision value={data.ai_necessity} />}
      {r && (
        <Section title="The problem behind the request">
          <div className="root-comparison">
            <div>
              <span className="eyebrow">
                <T text={"What you asked for"} />
              </span>
              <p>{r.user_request}</p>
            </div>
            <ArrowRight size={23} />
            <div>
              <span className="eyebrow">
                <T text={"What needs to change"} />
              </span>
              <h3>{r.root_problem}</h3>
            </div>
          </div>
        </Section>
      )}
      {w && (
        <>
          <Section title="Business context">
            <p>{w.business_context}</p>
          </Section>
          <Section title="Your current system">
            <div className="system-grid">
              {Object.entries(w.current_system).map(([key, value]) => (
                <div key={key}>
                  <h3>{humanize(key)}</h3>
                  {Array.isArray(value) ? (
                    <BulletList items={value} />
                  ) : (
                    <p>{value}</p>
                  )}
                </div>
              ))}
            </div>
          </Section>
          <Section
            title="How work happens today"
            subtitle="Reconstructed from your conversation and documents."
          >
            <div className="workflow-map">
              {w.workflow.map((s, i) => (
                <div className="workflow-step" key={i}>
                  <span className="step-number">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3>{s.name}</h3>
                  <span className="owner-label">{s.owner}</span>
                  <p>{s.description}</p>
                  <div className="tag-row">
                    {s.tools.map((t, j) => (
                      <span key={j}>{t}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Section>
          <Section title="Where the process slows down">
            <div className="evidence-grid">
              {w.bottlenecks.map((b, i) => (
                <article key={i}>
                  <span className="evidence-number">0{i + 1}</span>
                  <h3>{b.title}</h3>
                  <p>{b.description}</p>
                  <details>
                    <summary>
                      <T text={"Supporting evidence · "} />
                      {Math.round(b.confidence * 100)}
                      <T text={"% confidence"} />
                    </summary>
                    <BulletList items={b.evidence} />
                  </details>
                </article>
              ))}
            </div>
          </Section>
        </>
      )}
      {r && (
        <>
          <Section title="Root causes">
            <div className="evidence-grid">
              {r.root_causes.map((b, i) => (
                <article key={i}>
                  <h3>{b.title}</h3>
                  <p>{b.description}</p>
                  <details>
                    <summary>
                      <T text={"Evidence · "} />
                      {Math.round(b.confidence * 100)}
                      <T text={"% confidence"} />
                    </summary>
                    <BulletList items={b.evidence} />
                  </details>
                </article>
              ))}
            </div>
          </Section>
          <Section title="What still needs validating">
            <BulletList items={r.assumptions} />
          </Section>
        </>
      )}
    </div>
  );
}
export function SolutionReport({
  data,
  reviewOnly = false,
}: {
  data: Analysis;
  reviewOnly?: boolean;
}) {
  const s = data.solution,
    r = data.red_team;
  return (
    <div className="report-stack">
      {!reviewOnly && s && (
        <>
          <section className="solution-hero">
            <span className="eyebrow">
              <T text={"Recommended approach"} />
            </span>
            <h2>{s.title}</h2>
            <p>{s.summary}</p>
            <div className="tag-row">
              <span>{humanize(s.solution_type)}</span>
              <span>
                {humanize(s.complexity)}
                <T text={" complexity"} />
              </span>
            </div>
          </section>
          <Section
            title="Solution architecture"
            subtitle="Each component has a purpose. AI is used only where the evidence supports it."
          >
            <div className="architecture-grid">
              {s.components.map((c, i) => (
                <article className="component-card" key={i}>
                  <div className="row-between">
                    {c.uses_ai ? (
                      <Sparkles size={22} />
                    ) : (
                      <Workflow size={22} />
                    )}
                    <span
                      className={`badge ${c.uses_ai ? "badge-orange" : ""}`}
                    >
                      {c.uses_ai ? "AI component" : "Non-AI component"}
                    </span>
                  </div>
                  <h3>{c.name}</h3>
                  <p>{c.responsibility}</p>
                  <div className="component-why">
                    <strong>
                      <T text={"Why it belongs"} />
                    </strong>
                    <p>{c.reason}</p>
                  </div>
                </article>
              ))}
            </div>
          </Section>
          <Section title="Data flow">
            <div className="data-flow">
              {s.data_flow.map((v, i) => (
                <div key={i}>
                  <span>{i + 1}</span>
                  <p>{v}</p>
                  {i < s.data_flow.length - 1 && <ArrowRight size={17} />}
                </div>
              ))}
            </div>
          </Section>
          <div className="two-columns">
            <Section title="Required data">
              <BulletList items={s.data_requirements} />
            </Section>
            <Section title="Integrations">
              <BulletList items={s.integrations} />
            </Section>
            <Section title="Human checkpoints">
              <BulletList items={s.human_in_loop} />
            </Section>
            <Section title="Constraints & assumptions">
              <BulletList items={[...s.constraints, ...s.assumptions]} />
            </Section>
          </div>
          <Section title="Implementation roadmap">
            <div className="roadmap">
              {s.roadmap.map((p, i) => (
                <article key={i}>
                  <span className="step-number">{i + 1}</span>
                  <div>
                    <small>{p.phase}</small>
                    <h3>{p.title}</h3>
                    <BulletList items={p.actions} />
                    <p className="exit-criteria">
                      <Check size={15} />
                      <strong>
                        <T text={"Ready when:"} />
                      </strong>{" "}
                      {p.exit_criteria}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          </Section>
          <Section title="What success looks like">
            <BulletList items={s.success_metrics} />
          </Section>
        </>
      )}
      {r && (
        <Section
          title="An independent second look"
          subtitle={`Red Team review · ${data.red_team_cycle || 1} of 3 maximum review cycles`}
        >
          <div className="review-intro">
            <ShieldCheck size={24} />
            <p>{r.summary}</p>
          </div>
          <Findings findings={r.findings} />
          {!!data.solution_history?.length && (
            <details className="review-history">
              <summary>
                <T text={"How the design changed"} />
              </summary>
              <p>
                <T
                  text={
                    "Each proposal is preserved with the review that followed it. Compare the actual designs before deciding whether a finding was resolved."
                  }
                />
              </p>
              {data.solution_history.map((proposal, i) => (
                <article key={i}>
                  <h3>
                    {i === 0 ? "Initial proposal" : `Revised proposal ${i}`}
                  </h3>
                  <p>{proposal.summary}</p>
                  <BulletList
                    items={proposal.components.map(
                      (c) => `${c.name}: ${c.responsibility}`,
                    )}
                  />
                  <h4>
                    <T text={"Human controls"} />
                  </h4>
                  <BulletList items={proposal.human_in_loop} />
                  <h4>
                    <T text={"Integration approach"} />
                  </h4>
                  <BulletList items={proposal.integrations} />
                  {data.red_team_history?.[i] && (
                    <p>{data.red_team_history[i].summary}</p>
                  )}
                </article>
              ))}
            </details>
          )}
          {(data.red_team_history?.length || 0) > 1 && (
            <details className="review-history">
              <summary>
                <T text={"See previous review cycles"} />
              </summary>
              {data.red_team_history?.slice(0, -1).map((review, i) => (
                <div key={i}>
                  <h3>
                    <T text={"Review cycle "} />
                    {i + 1}
                  </h3>
                  <p>{review.summary}</p>
                  <Findings findings={review.findings} />
                </div>
              ))}
            </details>
          )}
        </Section>
      )}
    </div>
  );
}
export function ValueReport({ data }: { data: Analysis }) {
  const v = data.business_value;
  if (!v) return null;
  return (
    <div className="report-stack">
      <Section
        title="Business value"
        subtitle="Estimates are decision support; outcomes depend on validated inputs and implementation."
      >
        <p>{v.summary}</p>
        <div className="value-grid">
          {v.metrics.map((m, i) => (
            <article key={i}>
              <span className="badge">
                {m.is_assumption
                  ? "Assumption / estimate"
                  : "Based on supplied inputs"}
              </span>
              <h3>{m.metric}</h3>
              <strong>{m.estimate}</strong>
              <p>{m.basis}</p>
            </article>
          ))}
        </div>
      </Section>
      <Section
        title="Feasibility"
        subtitle={`Overall advisory score: ${v.feasibility.overall}/100`}
      >
        <div className="feasibility-grid">
          {(
            [
              "technical",
              "data",
              "integration",
              "operational",
              "business",
            ] as const
          ).map((k) => (
            <article key={k}>
              <div className="row-between">
                <h3>{humanize(k)}</h3>
                <strong>
                  {v.feasibility[k].score}
                  <small>/100</small>
                </strong>
              </div>
              <div className="progress-track">
                <span style={{ width: `${v.feasibility[k].score}%` }} />
              </div>
              <p>{v.feasibility[k].reason}</p>
            </article>
          ))}
        </div>
      </Section>
      <Section title="Risk assessment">
        <Findings findings={v.risks} />
      </Section>
    </div>
  );
}
export function FullReport({ data }: { data: Analysis }) {
  if (data.final_report) return <ImplementationReport report={data.final_report} />;
  return (
    <>
      <div className="report-stack">
        {data.conclusion && (
          <Section title="Executive summary">
            <p className="executive-summary">
              {data.conclusion.executive_summary}
            </p>
          </Section>
        )}
        {data.problem_statement && (
          <Section title="Original problem statement">
            <p>{data.problem_statement}</p>
          </Section>
        )}
      </div>
      <DiagnosisReport data={data} />
      <SolutionReport data={data} />
      <ValueReport data={data} />
      {data.evidence && (
        <Section title="Evidence register">
          <div className="evidence-register">
            {data.evidence.map((f, i) => (
              <div key={i}>
                <span>{humanize(f.category)}</span>
                <p>{f.fact}</p>
                <small>{f.source}</small>
              </div>
            ))}
          </div>
        </Section>
      )}
      {data.conclusion && (
        <section className="final-recommendation">
          <span className="eyebrow">
            <T text={"Your next move"} />
          </span>
          <h2>
            <T text={"Final recommendation"} />
          </h2>
          <p>{data.conclusion.recommendation}</p>
          <BulletList items={data.conclusion.next_steps} />
        </section>
      )}
      <p className="report-disclaimer">
        <T
          text={
            "Prepared with shift.AI. Recommendations and scores are advisory. Validate assumptions, costs, and material risks before implementation."
          }
        />
      </p>
    </>
  );
}
