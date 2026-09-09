"use client";

import { T } from "@/components/locale";
import { useId } from "react";
import { humanize } from "@/lib/api";
import type { Deliverable, Diagram } from "@/lib/deliverables";
import { BulletList, Section } from "@/components/analysis/report";

export function DiagramView({ diagram }: { diagram: Diagram }) {
  const marker = useId().replace(/:/g, "");
  const lanes = Array.from(
    new Set(diagram.nodes.map((n) => n.lane || "Process")),
  );
  const counts: Record<string, number> = {};
  const positions = Object.fromEntries(
    diagram.nodes.map((n) => {
      const lane = n.lane || "Process";
      const col = counts[lane] || 0;
      counts[lane] = col + 1;
      return [n.id, { x: 190 + col * 240, y: 65 + lanes.indexOf(lane) * 165 }];
    }),
  );
  const width = Math.max(
    760,
    230 + Math.max(...Object.values(counts), 1) * 240,
  );
  const height = Math.max(220, lanes.length * 165 + 50);
  return (
    <figure className="diagram-figure">
      <figcaption>{diagram.title}</figcaption>
      <div
        className="diagram-scroll"
        tabIndex={0}
        aria-label={`${diagram.title}, scroll to explore`}
      >
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={diagram.title}
        >
          <defs>
            <marker
              id={marker}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#627282" />
            </marker>
          </defs>
          {lanes.map((lane, i) => (
            <g key={lane}>
              <rect
                x="0"
                y={i * 165 + 20}
                width={width}
                height="165"
                fill={i % 2 ? "#fff4e6" : "#f3f6f8"}
                stroke="#e2e8f0"
              />
              <text x="16" y={i * 165 + 98} fill="#263544" fontSize="13">
                {lane.slice(0, 23)}
              </text>
            </g>
          ))}
          {diagram.edges.map((edge, i) => {
            const a = positions[edge.source],
              b = positions[edge.target];
            if (!a || !b) return null;
            return (
              <g key={i}>
                <path
                  d={`M ${a.x + 185} ${a.y + 37} C ${a.x + 220} ${a.y + 37}, ${b.x - 35} ${b.y + 37}, ${b.x} ${b.y + 37}`}
                  stroke="#627282"
                  fill="none"
                  markerEnd={`url(#${marker})`}
                />
                <text
                  x={(a.x + 185 + b.x) / 2}
                  y={(a.y + b.y) / 2 + 25}
                  fontSize="11"
                  fill="#475569"
                >
                  {edge.label.slice(0, 32)}
                </text>
              </g>
            );
          })}
          {diagram.nodes.map((n) => {
            const p = positions[n.id];
            return (
              <g key={n.id}>
                <rect
                  x={p.x}
                  y={p.y}
                  width="185"
                  height="75"
                  rx={
                    ["start", "end"].includes(n.kind)
                      ? 35
                      : n.kind === "decision"
                        ? 20
                        : 6
                  }
                  fill="white"
                  stroke={n.kind === "decision" ? "#ff7a00" : "#738596"}
                  strokeWidth="1.5"
                />
                <foreignObject x={p.x + 10} y={p.y + 9} width="165" height="59">
                  <div className="diagram-label">
                    <small>{n.kind}</small>
                    {n.label}
                  </div>
                </foreignObject>
              </g>
            );
          })}
        </svg>
      </div>
      <details>
        <summary>
          <T text={"Connections and accessible text"} />
        </summary>
        <ul>
          {diagram.nodes.map((n) => (
            <li key={n.id}>
              <strong>{n.label}</strong> — {n.lane}
            </li>
          ))}
          {diagram.edges.map((e, i) => (
            <li key={i}>
              {diagram.nodes.find((n) => n.id === e.source)?.label} →{" "}
              {diagram.nodes.find((n) => n.id === e.target)?.label}{" "}
              {e.label && `(${e.label})`}
            </li>
          ))}
        </ul>
      </details>
    </figure>
  );
}

export function DeliverableReport({ content }: { content: Deliverable }) {
  return (
    <div className="deliverable-report report-stack" dir="auto">
      <Section title={content.title}>
        <p>{content.summary}</p>
      </Section>
      {content.sections.map((section, i) => (
        <Section key={i} title={section.title}>
          <p className="preserve-lines">{section.narrative}</p>
          <BulletList items={section.items} />
          {section.tables.map((table, j) => (
            <div className="table-scroll" key={j} tabIndex={0}>
              <table>
                <caption>{table.title}</caption>
                <thead>
                  <tr>
                    {table.columns.map((col, k) => (
                      <th key={k}>{col}</th>
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
        </Section>
      ))}
      {content.diagrams.map((diagram, i) => (
        <Section key={i} title={diagram.kind.replaceAll("_", " ")}>
          <DiagramView diagram={diagram} />
        </Section>
      ))}
      {content.screens.map((screen, i) => (
        <Section key={i} title={screen.name}>
          <p>
            {screen.persona} · {screen.purpose}
          </p>
          <div className="wireframe">
            <header>
              <span>● ● ●</span>
              <strong>{screen.name}</strong>
            </header>
            <div className="wireframe-body">
              {screen.controls.map((control, j) => (
                <div key={j} className={`wire-control wire-${control.kind}`}>
                  <strong>{control.label}</strong>
                  {control.kind === "input" || control.kind === "select" ? (
                    <div className="wire-input">{control.detail || "…"}</div>
                  ) : control.kind === "table" ? (
                    <div className="wire-table">
                      {control.detail}
                      <hr />
                      <hr />
                      <hr />
                    </div>
                  ) : (
                    <p>{control.detail}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </Section>
      ))}
      {content.code_assets.map((asset, i) => (
        <Section key={i} title={asset.filename}>
          <pre className="code-asset">
            <code>{asset.content}</code>
          </pre>
        </Section>
      ))}
      {!!content.assessments?.length && (
        <Section title="Advisory readiness assessment">
          {content.assessments.map((a) => (
            <article key={a.dimension}>
              <h3>
                {humanize(a.dimension)}: {humanize(a.rating)}
              </h3>
              <p>{a.reason}</p>
              <BulletList items={a.evidence} />
            </article>
          ))}
        </Section>
      )}
      <Section title="Assumptions">
        <BulletList items={content.assumptions} />
      </Section>
      <Section title="Validation before implementation">
        <BulletList items={content.validation_steps} />
      </Section>
    </div>
  );
}
