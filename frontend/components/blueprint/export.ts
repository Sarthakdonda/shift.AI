import { Analysis } from "@/lib/types";
import { humanize } from "@/lib/api";
export function blueprintMarkdown(name: string, data: Analysis): string {
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
