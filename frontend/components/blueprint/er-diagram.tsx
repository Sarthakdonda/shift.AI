import type { Diagram } from "@/lib/deliverables";

function Entity({ node }: { node: Diagram["nodes"][number] }) {
  const [name, ...fields] = node.label.split(/\n|\s*[·|]\s*/).filter(Boolean);
  if (node.lane) fields.push("Context: " + node.lane);
  return (
    <div className="report-er-entity">
      <strong>{name}</strong>
      {fields.length > 0 && (
        <div>
          {fields.map((field, i) => (
            <p key={i}>{field}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function Cardinality({
  value,
  x,
  direction,
}: {
  value: string;
  x: number;
  direction: number;
}) {
  if (!value) return null;
  return (
    <g>
      {value.includes("*") ? (
        [-5, 0, 5].map((offset) => (
          <line
            key={offset}
            x1={x}
            y1={20 + offset}
            x2={x + direction * 9}
            y2={20}
          />
        ))
      ) : (
        <line x1={x + direction * 5} y1={15} x2={x + direction * 5} y2={25} />
      )}
      {value.startsWith("0") ? (
        <circle cx={x + direction * 15} cy={20} r={3} fill="white" />
      ) : value !== "*" ? (
        <line x1={x + direction * 15} y1={15} x2={x + direction * 15} y2={25} />
      ) : null}
    </g>
  );
}

export function ERDiagram({ diagram }: { diagram: Diagram }) {
  const nodes = Object.fromEntries(
    diagram.nodes.map((node) => [node.id, node]),
  );
  const linked = new Set(
    diagram.edges.flatMap((edge) => [edge.source, edge.target]),
  );
  return (
    <figure className="report-er" data-testid="report-er-diagram">
      <figcaption>{diagram.title}</figcaption>
      <p className="report-er-key">
        PK = primary key · FK = foreign key · ○ optional · | one · fork many
      </p>
      {diagram.edges.map((edge, index) => {
        const match = edge.label.match(
          /^\s*(0\.\.1|1|0\.\.(?:many|\*)|1\.\.(?:many|\*)|many|\*)\s*(?:to|:|→|—|--|-)\s*(0\.\.1|1|0\.\.(?:many|\*)|1\.\.(?:many|\*)|many|\*)(?=\s|;|,|:|$)/i,
        );
        const source = nodes[edge.source],
          target = nodes[edge.target];
        if (!source || !target) return null;
        return (
          <div className="report-er-relationship" key={index}>
            <div className="report-er-pair">
              <Entity node={source} />
              <svg
                viewBox="0 0 180 40"
                role="img"
                aria-label={edge.label}
                preserveAspectRatio="none"
              >
                <g stroke="currentColor" strokeWidth="1" fill="none">
                  <line x1={0} y1={20} x2={180} y2={20} />
                  <Cardinality
                    value={match?.[1].toLowerCase().replace("many", "*") || ""}
                    x={1}
                    direction={1}
                  />
                  <Cardinality
                    value={match?.[2].toLowerCase().replace("many", "*") || ""}
                    x={179}
                    direction={-1}
                  />
                </g>
                <text x={90} y={12} textAnchor="middle" fontSize="11">
                  R{index + 1}
                </text>
              </svg>
              <Entity node={target} />
            </div>
            <p className="report-er-definition">
              R{index + 1}. {edge.label}
            </p>
          </div>
        );
      })}
      {diagram.nodes
        .filter((node) => !linked.has(node.id))
        .map((node) => (
          <Entity key={node.id} node={node} />
        ))}
    </figure>
  );
}
