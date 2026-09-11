import { Analysis } from "@/lib/types";
import { humanize } from "@/lib/api";
export function blueprintMarkdown(name: string, data: Analysis): string {
  if (data.final_report) {
    const report = data.final_report;
    const cell = (value: string) =>
      value.replaceAll("|", "\\|").replaceAll("\n", "<br>");
    return (
      `# ${report.title}\n\nshift.AI · Strategy & implementation blueprint\n\n${report.report_version ? `Version ${report.report_version} · Prepared ${report.prepared_at}\n\n` : ""}Industry: ${report.industry} · Language: ${report.language} · Selected option: ${report.selected_option}\n\n` +
      report.sections
        .map((s, i) => {
          const parts = [
            `## ${i + 2}. ${s.title}`,
            s.applicability === "not_applicable"
              ? "Not applicable — see rationale."
              : "",
            s.narrative,
            `Evidence / assumptions: ${s.basis}`,
            ...s.items.map((x) => `- ${x}`),
          ];
          for (const table of s.tables)
            parts.push(
              `### ${table.title}\n\n| ${table.columns.map(cell).join(" | ")} |\n| ${table.columns.map(() => "---").join(" | ")} |\n${table.rows.map((row) => `| ${row.map(cell).join(" | ")} |`).join("\n")}`,
            );
          for (const diagram of s.diagrams) {
            const names = Object.fromEntries(
              diagram.nodes.map((n) => [n.id, n.label]),
            );
            parts.push(
              `### ${diagram.title}`,
              ...diagram.nodes.map(
                (n) => `- ${n.label} (${n.lane}; ${n.kind})`,
              ),
              ...diagram.edges.map(
                (e) =>
                  `- ${names[e.source]} → ${names[e.target]}${e.label ? `: ${e.label}` : ""}`,
              ),
            );
          }
          for (const screen of s.screens)
            parts.push(
              `### ${screen.name}`,
              `${screen.persona}: ${screen.purpose}`,
              ...screen.controls.map(
                (c) => `- ${c.kind} / ${c.label}: ${c.detail}`,
              ),
            );
          for (const asset of s.code_assets)
            parts.push(
              `### ${asset.filename}\n\n\`\`\`\`${asset.language}\n${asset.content}\n\`\`\`\``,
            );
          return parts.filter(Boolean).join("\n\n");
        })
        .join("\n\n") +
      "\n\nAdvisory design. Validate assumptions and material risks before implementation.\n"
    );
  }
  function render(value: unknown, depth = 2): string {
    if (value === null || value === undefined) return "";
    if (typeof value !== "object") return String(value);
    if (Array.isArray(value))
      return value
        .map((v) => (typeof v === "object" ? render(v, depth) : `- ${v}`))
        .join("\n\n");
    return Object.entries(value)
      .map(
        ([k, v]) =>
          `${"#".repeat(Math.min(depth, 6))} ${humanize(k)}\n\n${render(v, depth + 1)}`,
      )
      .join("\n\n");
  }
  return `# ${name}\n\nStrategy & implementation blueprint · shift.AI\n\n${render(data)}\n\n---\nAdvisory analysis. Validate assumptions and material risks before implementation.\n`;
}
