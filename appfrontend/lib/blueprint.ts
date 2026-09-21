import { humanize } from "@/lib/api";
import type { Analysis } from "@/lib/types";

/** Plain Markdown so a blueprint can be shared from the phone's share sheet. */
export function blueprintMarkdown(name: string, data: Analysis): string {
  if (data.final_report) {
    const report = data.final_report;
    const cell = (value: string) =>
      value.replaceAll("|", "\\|").replaceAll("\n", "<br>");
    return (
      `# ${report.title}\n\nshift.AI · Strategy & implementation blueprint\n\n${
        report.report_version
          ? `Version ${report.report_version} · Prepared ${report.prepared_at}\n\n`
          : ""
      }Industry: ${report.industry} · Language: ${report.language} · Selected option: ${report.selected_option}\n\n` +
      report.sections
        .map((section, index) => {
          const parts = [
            `## ${index + 1}. ${section.title}`,
            section.applicability === "not_applicable"
              ? "Not applicable — see rationale."
              : "",
            section.narrative,
            `Evidence / assumptions: ${section.basis}`,
            ...section.items.map((item) => `- ${item}`),
          ];
          for (const table of section.tables)
            parts.push(
              `### ${table.title}\n\n| ${table.columns.map(cell).join(" | ")} |\n| ${table.columns
                .map(() => "---")
                .join(" | ")} |\n${table.rows
                .map((row) => `| ${row.map(cell).join(" | ")} |`)
                .join("\n")}`,
            );
          for (const diagram of section.diagrams) {
            const names = Object.fromEntries(
              diagram.nodes.map((node) => [node.id, node.label]),
            );
            parts.push(
              `### ${diagram.title}`,
              ...diagram.nodes.map(
                (node) => `- ${node.label} (${node.lane}; ${node.kind})`,
              ),
              ...diagram.edges.map(
                (edge) =>
                  `- ${names[edge.source]} → ${names[edge.target]}${
                    edge.label ? `: ${edge.label}` : ""
                  }`,
              ),
            );
          }
          for (const screen of section.screens)
            parts.push(
              `### ${screen.name}`,
              `${screen.persona}: ${screen.purpose}`,
              ...screen.controls.map(
                (control) => `- ${control.kind} / ${control.label}: ${control.detail}`,
              ),
            );
          for (const asset of section.code_assets)
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
        .map((entry) => (typeof entry === "object" ? render(entry, depth) : `- ${entry}`))
        .join("\n\n");
    return Object.entries(value)
      .map(
        ([key, entry]) =>
          `${"#".repeat(Math.min(depth, 6))} ${humanize(key)}\n\n${render(entry, depth + 1)}`,
      )
      .join("\n\n");
  }
  return `# ${name}\n\nStrategy & implementation blueprint · shift.AI\n\n${render(
    data,
  )}\n\n---\nAdvisory analysis. Validate assumptions and material risks before implementation.\n`;
}
