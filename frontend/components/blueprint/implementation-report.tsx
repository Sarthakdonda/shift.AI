"use client";

import type { Diagram, Deliverable, Table } from "@/lib/deliverables";
import { T } from "@/components/locale";
type Screen = Deliverable["screens"][number];
type CodeAsset = Deliverable["code_assets"][number];

export type ReportChapter = {
  key: string;
  title: string;
  narrative: string;
  basis: string;
  applicability: "applicable" | "not_applicable";
  items: string[];
  tables: Table[];
  diagrams: Diagram[];
  screens: Screen[];
  code_assets: CodeAsset[];
};

export type ImplementationDocument = {
  schema_version: number;
  report_version?: number;
  prepared_at?: string;
  title: string;
  industry: string;
  language: string;
  source_revision: number;
  selected_option: string;
  sections: ReportChapter[];
};

// A node and its labelled outgoing connections form one printable flow row.
// Large graphs paginate at rows rather than shrinking a 30-node SVG to tiny text.
function ReportFlow({ diagram }: { diagram: Diagram }) {
  const names = Object.fromEntries(diagram.nodes.map((n) => [n.id, n.label]));
  return (
    <figure className="report-flow">
      <figcaption>{diagram.title}</figcaption>
      {diagram.nodes.map((node) => {
        const edges = diagram.edges.filter((e) => e.source === node.id);
        return (
          <div className="report-flow-row" key={node.id}>
            <div className={`report-flow-node report-flow-${node.kind}`}>
              <small>
                {node.lane} · {node.kind}
              </small>
              <strong>{node.label}</strong>
            </div>
            <div className="report-flow-connections">
              {edges.map((edge, i) => (
                <p key={i}>
                  <span aria-hidden="true">→ </span>
                  {edge.label && <em>{edge.label}: </em>}
                  {names[edge.target]}
                </p>
              ))}
              {!edges.length && (
                <p className="muted">
                  <T text="No outgoing connection" />
                </p>
              )}
            </div>
          </div>
        );
      })}
    </figure>
  );
}

function Wireframe({ screen }: { screen: Screen }) {
  return (
    <figure className="report-screen">
      <figcaption>{screen.name}</figcaption>
      <p>
        {screen.persona} · {screen.purpose}
      </p>
      <div className="report-screen-controls">
        {screen.controls.map((control, i) => (
          <div
            className={`report-screen-control report-control-${control.kind}`}
            key={i}
          >
            <small>{control.kind}</small>
            <strong>{control.label}</strong>
            <p>{control.detail}</p>
          </div>
        ))}
      </div>
    </figure>
  );
}

export function ImplementationReport({
  report,
}: {
  report: ImplementationDocument;
}) {
  return (
    <article className="implementation-report" dir="auto">
      <nav className="report-contents" aria-label="Report contents">
        <h2>
          <T text="Report contents" />
        </h2>
        <ol start={2}>
          {report.sections.map((section) => (
            <li key={section.key}>
              <a href={`#report-${section.key}`}>{section.title}</a>
            </li>
          ))}
        </ol>
      </nav>
      {report.sections.map((section, i) => (
        <section
          className="implementation-chapter"
          id={`report-${section.key}`}
          key={section.key}
        >
          <h2>
            <span>{String(i + 2).padStart(2, "0")}</span> {section.title}
          </h2>
          {section.applicability === "not_applicable" && (
            <p className="report-basis">
              <T text="Not applicable — rationale below" />
            </p>
          )}
          <p className="preserve-lines">{section.narrative}</p>
          <p className="report-basis">
            <strong>
              <T text="Evidence / assumptions:" />
            </strong>{" "}
            {section.basis}
          </p>
          {!!section.items.length && (
            <ul>
              {section.items.map((item, j) => (
                <li key={j}>{item}</li>
              ))}
            </ul>
          )}
          {section.tables.map((table, j) => (
            <div className="report-table-wrap" key={j}>
              <table>
                <caption>{table.title}</caption>
                <thead>
                  <tr>
                    {table.columns.map((column, k) => (
                      <th key={k} scope="col">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((row, k) => (
                    <tr key={k}>
                      {row.map((cell, l) => (
                        <td key={l}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          {section.diagrams.map((diagram, j) => (
            <ReportFlow key={j} diagram={diagram} />
          ))}
          {section.screens.map((screen, j) => (
            <Wireframe key={j} screen={screen} />
          ))}
          {section.code_assets.map((asset, j) => (
            <div className="report-code" key={j}>
              <h3>{asset.filename}</h3>
              <pre>
                <code>{asset.content}</code>
              </pre>
            </div>
          ))}
        </section>
      ))}
      <p className="report-disclaimer">
        <T text="Prepared with shift.AI. Recommendations, estimates and readiness scores are advisory. Validate assumptions and unresolved risks before implementation." />
      </p>
    </article>
  );
}
