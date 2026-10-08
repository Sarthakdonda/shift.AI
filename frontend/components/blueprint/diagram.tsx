"use client";
import { useId } from "react";
import type { Diagram } from "@/lib/deliverables";

export function BlueprintDiagram({ diagram }: { diagram: Diagram }) {
  const id = useId().replaceAll(":", "");
  const er = diagram.kind === "er";
  const lanes = [...new Set(diagram.nodes.map(n => n.lane || "Process"))];
  const swimlane = diagram.kind === "swimlane" || diagram.kind === "bpmn";
  const columns = swimlane ? Math.max(1, lanes.length) : Math.min(3, diagram.nodes.length);
  const boxWidth = 250, gap = 85, padding = 32;
  const width = columns * (boxWidth + gap) + padding;
  const offsets = Array(columns).fill(swimlane ? 65 : 24) as number[];
  const nodes = diagram.nodes.map((node, index) => {
    const column = swimlane ? lanes.indexOf(node.lane || "Process") : index % columns;
    const lines = node.label.split(/\n|\s*[·|]\s*/).filter(Boolean);
    const textLines = lines.reduce((sum, text) => sum + Math.max(1, Math.ceil(text.length / 27)), 0);
    const height = Math.max(85, 38 + textLines * 22 + (node.lane ? 22 : 0));
    const result = { ...node, lines, x: padding + column * (boxWidth + gap), y: offsets[column], height };
    offsets[column] += height + 80;
    return result;
  });
  const positions = Object.fromEntries(nodes.map(n => [n.id, n]));
  const height = Math.max(...offsets) + 12;
  const invalid = diagram.edges.some(e => !positions[e.source] || !positions[e.target]);
  if (invalid || !nodes.length) return <p role="alert">This diagram has invalid connections. Edit or regenerate its blueprint section.</p>;
  const marker = (cardinality: string) => cardinality.includes("*") || cardinality.includes("many") ? (cardinality.startsWith("0") ? "optionalMany" : "many") : cardinality.startsWith("0") ? "optionalOne" : "one";
  return <figure className="blueprint-diagram" data-testid={er ? "report-er-diagram" : "report-architecture-diagram"}>
    <figcaption>{diagram.title}</figcaption>
    {er && <p className="report-er-key">PK = primary key · FK = foreign key · circle = optional · bar = one · fork = many</p>}
    <div className="blueprint-diagram-scroll" tabIndex={0} aria-label={`${diagram.title}; scroll to explore`}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={diagram.title} style={{ minWidth: Math.min(width, 900) }}>
        <defs>
          <marker id={`${id}-arrow`} markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M1 1 L9 5 L1 9" fill="none" stroke="#647b8e" /></marker>
          {["one", "optionalOne", "many", "optionalMany"].map(kind => <marker key={kind} id={`${id}-${kind}`} markerWidth="23" markerHeight="16" refX="23" refY="8" orient="auto-start-reverse" markerUnits="userSpaceOnUse"><g fill="white" stroke="#465f73" strokeWidth="1.4">
            {kind.toLowerCase().includes("many") ? <path d="M22 1 L12 8 L22 15 M22 8 L12 8" fill="none" /> : <path d="M18 1 V15" />}
            {kind.startsWith("optional") ? <circle cx="5" cy="8" r="4" /> : <path d="M5 1 V15" />}
          </g></marker>)}
        </defs>
        {swimlane && lanes.map((lane, i) => <g key={lane}><rect x={padding+i*(boxWidth+gap)-12} y="10" width={boxWidth+24} height={height-24} rx="6" fill={i%2 ? "#f7f9fb" : "#edf2f6"}/><text x={padding+i*(boxWidth+gap)+8} y="38" fontSize="14" fill="#344c60">{lane}</text></g>)}
        {diagram.edges.map((edge, index) => {
          const a = positions[edge.source], b = positions[edge.target];
          const sameColumn = a.x === b.x;
          const backwards = b.x < a.x;
          const fromX = backwards ? a.x : a.x + boxWidth, fromY = a.y+a.height/2;
          const toX = sameColumn || backwards ? b.x+boxWidth : b.x, toY = b.y+b.height/2;
          const rail = sameColumn ? fromX+25+(index%3)*12 : (fromX+toX)/2;
          const cardinality = edge.label.match(/^\s*(0\.\.1|1|0\.\.(?:many|\*)|1\.\.(?:many|\*)|many|\*)\s*(?:to|:|→|—|--|-)\s*(0\.\.1|1|0\.\.(?:many|\*)|1\.\.(?:many|\*)|many|\*)/i);
          return <g key={index}><path d={`M${fromX} ${fromY} H${rail} V${toY} H${toX}`} stroke="#647b8e" strokeWidth="1.4" fill="none" markerStart={er && cardinality ? `url(#${id}-${marker(cardinality[1])})` : undefined} markerEnd={`url(#${id}-${er && cardinality ? marker(cardinality[2]) : "arrow"})`} />
            <rect x={rail-13} y={(fromY+toY)/2-14} width="27" height="19" fill="white"/><text x={rail} y={(fromY+toY)/2} textAnchor="middle" fontSize="11" fill="#344c60">R{index+1}</text>
          </g>;
        })}
        {nodes.map(node => <g key={node.id}>
          {node.kind === "decision" ? <path d={`M${node.x+14} ${node.y} H${node.x+boxWidth-14} L${node.x+boxWidth} ${node.y+node.height/2} L${node.x+boxWidth-14} ${node.y+node.height} H${node.x+14} L${node.x} ${node.y+node.height/2} Z`} fill="#fffaf0" stroke="#b79c69"/> : <rect x={node.x} y={node.y} width={boxWidth} height={node.height} rx={node.kind === "start" || node.kind === "end" ? 20 : 5} fill="white" stroke="#8da1b2"/>}
          <foreignObject x={node.x+12} y={node.y+12} width={boxWidth-24} height={node.height-20}><div className="blueprint-node-content"><strong>{node.lines[0]}</strong>{node.lines.slice(1).map((line,i)=><div key={i}>{line}</div>)}{node.lane && <small>{node.lane}</small>}</div></foreignObject>
        </g>)}
      </svg>
    </div>
    <ol className="blueprint-relationships">{diagram.edges.map((edge,i)=><li key={i}><strong>R{i+1}.</strong> {positions[edge.source].lines[0]} → {positions[edge.target].lines[0]}: {edge.label}</li>)}</ol>
  </figure>;
}
