import type { ReactNode } from "react";

/**
 * Renders assistant/user text as readable structure.
 *
 * The API returns plain text that often contains light Markdown, so this walks
 * the string and builds React nodes for headings, lists, tables, quotes and
 * code. Nothing is injected as HTML — every node is created explicitly.
 */

type Block =
  | { kind: "p"; lines: string[] }
  | { kind: "h"; level: 2 | 3 | 4; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "quote"; lines: string[] }
  | { kind: "code"; text: string }
  | { kind: "table"; rows: string[][] };

const inlinePattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*|_[^_\n]+_)/g;

function inline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(inlinePattern).map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4)
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2)
      return <code key={key}>{part.slice(1, -1)}</code>;
    if (
      part.length > 2 &&
      ((part.startsWith("*") && part.endsWith("*")) ||
        (part.startsWith("_") && part.endsWith("_")))
    )
      return <em key={key}>{part.slice(1, -1)}</em>;
    return part;
  });
}

const isTableRow = (line: string) =>
  line.startsWith("|") && line.slice(1).includes("|");
const isDivider = (line: string) => /^\|[\s:|-]+\|?$/.test(line);
const cells = (line: string) =>
  line
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());

function parse(text: string): Block[] {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();
    if (!trimmed) {
      index += 1;
      continue;
    }
    if (trimmed.startsWith("```")) {
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        body.push(lines[index]);
        index += 1;
      }
      index += 1;
      blocks.push({ kind: "code", text: body.join("\n") });
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed);
    if (heading) {
      const level = Math.min(4, Math.max(2, heading[1].length + 1)) as
        2 | 3 | 4;
      blocks.push({ kind: "h", level, text: heading[2] });
      index += 1;
      continue;
    }
    if (isTableRow(trimmed)) {
      const rows: string[][] = [];
      while (index < lines.length && isTableRow(lines[index].trim())) {
        if (!isDivider(lines[index].trim()))
          rows.push(cells(lines[index].trim()));
        index += 1;
      }
      if (rows.length) blocks.push({ kind: "table", rows });
      continue;
    }
    if (/^[-*•]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*•]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*•]\s+/, ""));
        index += 1;
      }
      blocks.push({ kind: "ul", items });
      continue;
    }
    if (/^\d+[.)]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+[.)]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+[.)]\s+/, ""));
        index += 1;
      }
      blocks.push({ kind: "ol", items });
      continue;
    }
    if (trimmed.startsWith(">")) {
      const quoted: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quoted.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push({ kind: "quote", lines: quoted });
      continue;
    }
    const paragraph: string[] = [];
    while (index < lines.length) {
      const next = lines[index].trim();
      if (
        !next ||
        next.startsWith("```") ||
        next.startsWith(">") ||
        isTableRow(next) ||
        /^(#{1,6})\s+/.test(next) ||
        /^[-*•]\s+/.test(next) ||
        /^\d+[.)]\s+/.test(next)
      )
        break;
      paragraph.push(next);
      index += 1;
    }
    blocks.push({ kind: "p", lines: paragraph });
  }
  return blocks;
}

export function MessageText({ content }: { content: string }) {
  const blocks = parse(content);
  return (
    <>
      {blocks.map((block, i) => {
        const key = `b${i}`;
        if (block.kind === "code")
          return (
            <pre className="dx-code" key={key}>
              <code>{block.text}</code>
            </pre>
          );
        if (block.kind === "h") {
          const Tag = `h${block.level}` as "h2" | "h3" | "h4";
          return <Tag key={key}>{inline(block.text, key)}</Tag>;
        }
        if (block.kind === "ul")
          return (
            <ul key={key}>
              {block.items.map((item, j) => (
                <li key={j}>{inline(item, `${key}-${j}`)}</li>
              ))}
            </ul>
          );
        if (block.kind === "ol")
          return (
            <ol key={key}>
              {block.items.map((item, j) => (
                <li key={j}>{inline(item, `${key}-${j}`)}</li>
              ))}
            </ol>
          );
        if (block.kind === "quote")
          return (
            <blockquote key={key}>
              {inline(block.lines.join(" "), key)}
            </blockquote>
          );
        if (block.kind === "table") {
          const [head, ...body] = block.rows;
          return (
            <div className="dx-table-scroll" key={key}>
              <table>
                <thead>
                  <tr>
                    {head.map((cell, j) => (
                      <th key={j}>{inline(cell, `${key}-h${j}`)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {body.map((row, j) => (
                    <tr key={j}>
                      {row.map((cell, k) => (
                        <td key={k}>{inline(cell, `${key}-${j}-${k}`)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (block.lines.length === 1)
          return <p key={key}>{inline(block.lines[0], key)}</p>;
        return (
          <p key={key}>
            {block.lines.map((line, j) => (
              <span key={j}>
                {j > 0 && <br />}
                {inline(line, `${key}-${j}`)}
              </span>
            ))}
          </p>
        );
      })}
    </>
  );
}
