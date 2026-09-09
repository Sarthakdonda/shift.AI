"use client";

import { T } from "@/components/locale";
import { useState } from "react";
import { humanize } from "@/lib/api";
import type { Deliverable } from "@/lib/deliverables";
type Value = string | Value[] | { [key: string]: Value };
const templates: Record<string, Value> = {
  assessments: {
    dimension: "digital_maturity",
    rating: "unknown",
    reason: "Describe the evidence or what is missing.",
    evidence: ["Identify the supporting source."],
  },
  sections: { title: "New section", narrative: "", items: [], tables: [] },
  tables: { title: "New table", columns: ["Column"], rows: [["Value"]] },
  diagrams: {
    title: "New diagram",
    kind: "workflow",
    nodes: [{ id: "Start", label: "Start", lane: "Team", kind: "start" }],
    edges: [],
  },
  nodes: { id: "Node", label: "New step", lane: "Team", kind: "task" },
  edges: { source: "Start", target: "Node", label: "" },
  screens: { name: "New screen", persona: "", purpose: "", controls: [] },
  controls: { label: "New control", kind: "input", detail: "" },
  code_assets: {
    filename: "design.sql",
    language: "sql",
    content: "-- Design for review",
  },
  rows: [""],
};
function Field({
  name,
  value,
  onChange,
  path,
}: {
  name: string;
  value: Value;
  onChange: (v: Value) => void;
  path: string;
}) {
  const [expanded, setExpanded] = useState(false);
  if (typeof value === "string")
    return (
      <label className="editor-field">
        {humanize(name)}
        <textarea
          aria-label={path}
          value={value}
          rows={value.length > 180 ? 5 : 2}
          onChange={(e) => onChange(e.target.value)}
        />
      </label>
    );
  if (Array.isArray(value))
    return (
      <details
        className="editor-group"
        open={expanded}
        onToggle={(e) => setExpanded(e.currentTarget.open)}
      >
        <summary>
          {humanize(name)} ({value.length})
        </summary>
        {expanded && (
          <>
            {value.map((item, i) => (
              <div className="editor-item" key={i}>
                <Field
                  name={`${name} ${i + 1}`}
                  path={`${path} ${i + 1}`}
                  value={item}
                  onChange={(v) =>
                    onChange(value.map((x, j) => (j === i ? v : x)))
                  }
                />
                <button
                  type="button"
                  className="button button-ghost"
                  onClick={() => onChange(value.filter((_, j) => j !== i))}
                >
                  <T text={"Remove "} />
                  {humanize(name)} {i + 1}
                </button>
              </div>
            ))}
            <button
              type="button"
              className="button button-secondary"
              onClick={() =>
                onChange([...value, structuredClone(templates[name] ?? "")])
              }
            >
              <T text={"Add "} />
              {humanize(name)}
            </button>
          </>
        )}
      </details>
    );
  return (
    <div>
      {Object.entries(value).map(([key, item]) => (
        <Field
          key={key}
          name={key}
          path={`${path} ${humanize(key)}`}
          value={item}
          onChange={(v) => onChange({ ...value, [key]: v })}
        />
      ))}
    </div>
  );
}
export function DeliverableEditor({
  value,
  onChange,
}: {
  value: Deliverable;
  onChange: (v: Deliverable) => void;
}) {
  return (
    <div className="deliverable-editor">
      <p>
        <T
          text={
            "Changes save as a new version. Diagram types: workflow, bpmn, swimlane, decision_tree, architecture, er, data_flow. Node IDs must be unique and connections must use existing IDs."
          }
        />
      </p>
      <Field
        name="Deliverable"
        path="Deliverable"
        value={value as unknown as Value}
        onChange={(v) => onChange(v as unknown as Deliverable)}
      />
    </div>
  );
}
