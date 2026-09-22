"use client";

import { Check, CircleAlert, Sparkles, X } from "lucide-react";
import { humanize } from "@/lib/api";
import type {
  Analysis,
  Evidence,
  Finding,
  ImplementationDocument,
  Solution,
} from "@/lib/types";
import { stagger } from "@/components/ui/states";

function Section({
  title,
  caption,
  index = 0,
  id,
  children,
}: {
  title: string;
  caption?: string;
  index?: number;
  id?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="section" id={id} style={stagger(index)}>
      <div className="section-head">
        <h2>{title}</h2>
        {caption && <p>{caption}</p>}
      </div>
      {children}
    </section>
  );
}

function Bullets({ items }: { items?: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="prose">
      <ul>
        {items.map((item, index) => (
          <li key={index}>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EvidenceList({ items }: { items?: Evidence[] }) {
  if (!items?.length) return null;
  return (
    <div className="kv">
      {items.map((item, index) => (
        <div key={index}>
          <strong>{item.title}</strong>
          <p>{item.description}</p>
          {!!item.evidence?.length && (
            <p className="muted" style={{ fontSize: 12 }}>
              Evidence: {item.evidence.join(" · ")}
            </p>
          )}
          <span className="badge" style={{ justifySelf: "start", marginTop: 4 }}>
            {Math.round((item.confidence || 0) * 100)}% confidence
          </span>
        </div>
      ))}
    </div>
  );
}

function Findings({ items }: { items?: Finding[] }) {
  if (!items?.length) return null;
  return (
    <div className="stack" style={{ gap: 8 }}>
      {items.map((finding, index) => (
        <div
          className="finding"
          data-severity={(finding.severity || "").toLowerCase()}
          key={index}
        >
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="eyebrow">{humanize(finding.category || "")}</span>
            <span
              className={`badge ${
                finding.severity?.toLowerCase() === "high"
                  ? "badge-danger"
                  : finding.severity?.toLowerCase() === "medium"
                    ? "badge-warn"
                    : "badge"
              }`}
            >
              {humanize(finding.severity || "note")}
            </span>
          </div>
          <strong>{finding.issue}</strong>
          <p>{finding.reason}</p>
          {finding.mitigation && (
            <p>
              <strong>Mitigation: </strong>
              {finding.mitigation}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

export function DiagnosisReport({ data }: { data: Analysis }) {
  const workflow = data.workflow_analysis;
  const root = data.root_cause;
  const necessity = data.ai_necessity;
  return (
    <>
      {data.problem_statement && (
        <Section title="The request" index={0}>
          <p className="prose preserve">{data.problem_statement}</p>
        </Section>
      )}
      {workflow && (
        <Section
          title="How work happens today"
          caption="Reconstructed from your answers and documents."
          index={1}
        >
          <p className="prose preserve">{workflow.business_context}</p>
          <div className="kv">
            {(
              [
                ["People", workflow.current_system.people],
                ["Technology", workflow.current_system.technology],
                ["Data", workflow.current_system.data],
              ] as const
            ).map(([label, values]) =>
              values?.length ? (
                <div key={label}>
                  <strong>{label}</strong>
                  <p>{values.join(" · ")}</p>
                </div>
              ) : null,
            )}
            {workflow.current_system.process && (
              <div>
                <strong>Process</strong>
                <p>{workflow.current_system.process}</p>
              </div>
            )}
          </div>
          {!!workflow.workflow?.length && (
            <div className="flow">
              {workflow.workflow.map((step, index) => (
                <div className="flow-step" key={index}>
                  <span>{index + 1}</span>
                  <div>
                    <strong style={{ fontSize: 13.5 }}>{step.name}</strong>
                    <p>{step.description}</p>
                    <p className="muted" style={{ fontSize: 12 }}>
                      {[step.owner, step.tools?.join(", ")]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
          {!!workflow.bottlenecks?.length && (
            <>
              <p className="eyebrow">Bottlenecks</p>
              <EvidenceList items={workflow.bottlenecks} />
            </>
          )}
        </Section>
      )}
      {root && (
        <Section
          title="The underlying problem"
          caption="What actually needs solving, not only what was asked for."
          index={2}
        >
          <div className="kv">
            <div>
              <strong>You asked for</strong>
              <p>{root.user_request}</p>
            </div>
            <div>
              <strong>The root problem</strong>
              <p>{root.root_problem}</p>
            </div>
          </div>
          <EvidenceList items={root.root_causes} />
          {!!root.assumptions?.length && (
            <>
              <p className="eyebrow">Assumptions</p>
              <Bullets items={root.assumptions} />
            </>
          )}
        </Section>
      )}
      {necessity && (
        <Section
          title="Does this need AI?"
          caption="An honest classification, including outcomes without AI."
          index={3}
        >
          <div className="row" style={{ flexWrap: "wrap" }}>
            <span className="badge badge-accent">
              <Sparkles size={12} aria-hidden="true" />
              {humanize(necessity.classification)}
            </span>
            <span className="badge">Score {necessity.score}</span>
            <span className="badge">
              {Math.round((necessity.confidence || 0) * 100)}% confidence
            </span>
          </div>
          <Bullets items={necessity.reasoning} />
          <div className="kv">
            {necessity.non_ai_alternative && (
              <div>
                <strong>Without AI</strong>
                <p>{necessity.non_ai_alternative}</p>
              </div>
            )}
            {necessity.recommended_approach && (
              <div>
                <strong>Recommended approach</strong>
                <p>{necessity.recommended_approach}</p>
              </div>
            )}
          </div>
        </Section>
      )}
      {!!data.evidence?.length && (
        <Section
          title="Evidence used"
          caption={`${data.evidence.length} facts from your answers and documents.`}
          index={4}
        >
          <div className="kv">
            {data.evidence.slice(0, 40).map((fact, index) => (
              <div key={index}>
                <strong>{humanize(fact.category)}</strong>
                <p>{fact.fact}</p>
                <p className="muted" style={{ fontSize: 12 }}>
                  {fact.source}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}
    </>
  );
}

export function SolutionReport({
  solution,
  index = 0,
}: {
  solution: Solution;
  index?: number;
}) {
  return (
    <>
      <Section
        title={solution.title || "Recommended solution"}
        caption={`${humanize(solution.solution_type || "")} · ${humanize(
          solution.complexity || "",
        )} complexity`}
        index={index}
      >
        <p className="prose preserve">{solution.summary}</p>
      </Section>
      {!!solution.components?.length && (
        <Section title="What it is made of" index={index + 1}>
          <div className="stack" style={{ gap: 8 }}>
            {solution.components.map((component, position) => (
              <div className="finding" key={position}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <strong>{component.name}</strong>
                  <span
                    className={`badge ${component.uses_ai ? "badge-accent" : "badge-good"}`}
                  >
                    {component.uses_ai ? (
                      <Check size={11} aria-hidden="true" />
                    ) : (
                      <X size={11} aria-hidden="true" />
                    )}
                    {component.uses_ai ? "Uses AI" : "No AI"}
                  </span>
                </div>
                <p>{component.responsibility}</p>
                {component.reason && <p className="muted">{component.reason}</p>}
              </div>
            ))}
          </div>
        </Section>
      )}
      {!!solution.data_flow?.length && (
        <Section title="How the work flows" index={index + 2}>
          <div className="flow">
            {solution.data_flow.map((step, position) => (
              <div className="flow-step" key={position}>
                <span>{position + 1}</span>
                <p>{step}</p>
              </div>
            ))}
          </div>
        </Section>
      )}
      {!!solution.roadmap?.length && (
        <Section title="Roadmap" index={index + 3}>
          <div className="stack" style={{ gap: 8 }}>
            {solution.roadmap.map((phase, position) => (
              <div className="finding" key={position}>
                <span className="eyebrow">{phase.phase}</span>
                <strong>{phase.title}</strong>
                <Bullets items={phase.actions} />
                {phase.exit_criteria && (
                  <p>
                    <strong>Done when: </strong>
                    {phase.exit_criteria}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}
      {(!!solution.integrations?.length ||
        !!solution.data_requirements?.length ||
        !!solution.human_in_loop?.length ||
        !!solution.constraints?.length ||
        !!solution.assumptions?.length ||
        !!solution.success_metrics?.length) && (
        <Section title="Practical detail" index={index + 4}>
          <div className="kv">
            {(
              [
                ["Integrations", solution.integrations],
                ["Data needed", solution.data_requirements],
                ["Human review", solution.human_in_loop],
                ["Constraints", solution.constraints],
                ["Assumptions", solution.assumptions],
                ["Success metrics", solution.success_metrics],
              ] as const
            ).map(([label, values]) =>
              values?.length ? (
                <div key={label}>
                  <strong>{label}</strong>
                  <p>{values.join(" · ")}</p>
                </div>
              ) : null,
            )}
          </div>
        </Section>
      )}
    </>
  );
}

export function ReviewReport({ data }: { data: Analysis }) {
  const review = data.red_team;
  const value = data.business_value;
  return (
    <>
      {review && (
        <Section
          title="Red Team review"
          caption={`Design review · ${data.red_team_cycle || 1} total cycles`}
          index={0}
        >
          <p className="prose preserve">{review.summary}</p>
          {!data.review_ledger && <Findings items={review.findings} />}
        </Section>
      )}
      {!!data.red_team_history?.length && data.red_team_history.length > 1 && (
        <Section
          title="Earlier review cycles"
          caption="Previous findings stay visible so nothing is quietly dropped."
          index={1}
        >
          <div className="stack" style={{ gap: 12 }}>
            {data.red_team_history.slice(0, -1).map((cycle, index) => (
              <div className="card-flat" key={index}>
                <p className="eyebrow">Cycle {index + 1}</p>
                <p className="prose preserve" style={{ marginTop: 6 }}>
                  {cycle.summary}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}
      {value && (
        <Section
          title="Business value"
          caption="Estimates are labelled where they rest on assumptions."
          index={2}
        >
          <p className="prose preserve">{value.summary}</p>
          {!!value.metrics?.length && (
            <div className="kv">
              {value.metrics.map((metric, index) => (
                <div key={index}>
                  <strong>{metric.metric}</strong>
                  <p>{metric.estimate}</p>
                  <p className="muted" style={{ fontSize: 12 }}>
                    {metric.basis}
                  </p>
                  {metric.is_assumption && (
                    <span
                      className="badge badge-warn"
                      style={{ justifySelf: "start", marginTop: 4 }}
                    >
                      <CircleAlert size={11} aria-hidden="true" />
                      Assumption
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
          {value.feasibility && (
            <>
              <p className="eyebrow">Feasibility</p>
              <div className="score-grid">
                {(
                  [
                    ["Technical", value.feasibility.technical],
                    ["Data", value.feasibility.data],
                    ["Integration", value.feasibility.integration],
                    ["Operational", value.feasibility.operational],
                    ["Business", value.feasibility.business],
                  ] as const
                ).map(([label, dimension]) =>
                  dimension ? (
                    <div className="score" key={label}>
                      <span>{label}</span>
                      <strong>{dimension.score}</strong>
                      <div className="meter">
                        <span style={{ width: `${dimension.score}%` }} />
                      </div>
                    </div>
                  ) : null,
                )}
                <div className="score">
                  <span>Overall</span>
                  <strong>{value.feasibility.overall}</strong>
                  <div className="meter">
                    <span style={{ width: `${value.feasibility.overall}%` }} />
                  </div>
                </div>
              </div>
            </>
          )}
          {!!value.risks?.length && (
            <>
              <p className="eyebrow">Risks</p>
              <Findings items={value.risks} />
            </>
          )}
        </Section>
      )}
      {data.conclusion && (
        <Section title="Conclusion" index={3}>
          <p className="prose preserve">{data.conclusion.executive_summary}</p>
          <div className="kv">
            <div>
              <strong>Recommendation</strong>
              <p>{data.conclusion.recommendation}</p>
            </div>
          </div>
          {!!data.conclusion.next_steps?.length && (
            <>
              <p className="eyebrow">Next steps</p>
              <Bullets items={data.conclusion.next_steps} />
            </>
          )}
        </Section>
      )}
    </>
  );
}

export function ImplementationReport({
  report,
}: {
  report: ImplementationDocument;
}) {
  return (
    <>
      <Section
        title={report.title}
        caption={`${report.industry} · ${report.language} · Selected option: ${report.selected_option}`}
        index={0}
      >
        <nav className="toc" aria-label="Report contents">
          {report.sections.map((section, index) => (
            <a href={`#chapter-${section.key}`} key={section.key}>
              <span>
                {index + 1}. {section.title}
              </span>
              <span className="muted">→</span>
            </a>
          ))}
        </nav>
      </Section>
      {report.sections.map((section, index) => (
        <Section
          key={section.key}
          id={`chapter-${section.key}`}
          title={`${index + 1}. ${section.title}`}
          index={Math.min(index + 1, 7)}
        >
          {section.applicability === "not_applicable" && (
            <span className="badge badge-warn" style={{ justifySelf: "start" }}>
              Not applicable — rationale below
            </span>
          )}
          <p className="prose preserve">{section.narrative}</p>
          <p className="field-note">
            <strong>Evidence / assumptions: </strong>
            {section.basis}
          </p>
          <Bullets items={section.items} />
          {section.tables.map((table, position) => (
            <div className="table-wrap" key={position}>
              <table>
                <caption>{table.title}</caption>
                <thead>
                  <tr>
                    {table.columns.map((column, cell) => (
                      <th key={cell} scope="col">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          {section.diagrams.map((diagram, position) => {
            const names = Object.fromEntries(
              diagram.nodes.map((node) => [node.id, node.label]),
            );
            return (
              <div className="stack" style={{ gap: 8 }} key={position}>
                <p className="eyebrow">{diagram.title}</p>
                <div className="flow">
                  {diagram.nodes.map((node) => (
                    <div className="flow-step" key={node.id}>
                      <span>{node.kind.slice(0, 1).toUpperCase()}</span>
                      <div>
                        <strong style={{ fontSize: 13.5 }}>{node.label}</strong>
                        <p className="muted" style={{ fontSize: 12 }}>
                          {node.lane} · {node.kind}
                        </p>
                        {diagram.edges
                          .filter((edge) => edge.source === node.id)
                          .map((edge, edgeIndex) => (
                            <p key={edgeIndex}>
                              → {edge.label ? `${edge.label}: ` : ""}
                              {names[edge.target]}
                            </p>
                          ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
          {section.screens.map((screen, position) => (
            <div className="card-flat stack" style={{ gap: 8 }} key={position}>
              <div>
                <strong style={{ fontSize: 14 }}>{screen.name}</strong>
                <p className="muted" style={{ fontSize: 12.5 }}>
                  {screen.persona} · {screen.purpose}
                </p>
              </div>
              {screen.controls.map((control, controlIndex) => (
                <div key={controlIndex}>
                  <span className="badge">{control.kind}</span>{" "}
                  <strong style={{ fontSize: 13 }}>{control.label}</strong>
                  <p className="field-note">{control.detail}</p>
                </div>
              ))}
            </div>
          ))}
          {section.code_assets.map((asset, position) => (
            <div className="stack" style={{ gap: 6 }} key={position}>
              <p className="eyebrow">{asset.filename}</p>
              <div className="prose">
                <pre>
                  <code>{asset.content}</code>
                </pre>
              </div>
            </div>
          ))}
        </Section>
      ))}
      <p className="field-note" style={{ padding: "0 4px" }}>
        Prepared with shift.AI. Recommendations, estimates and readiness scores are
        advisory. Validate assumptions and unresolved risks before implementation.
      </p>
    </>
  );
}
