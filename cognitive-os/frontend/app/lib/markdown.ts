/**
 * Tiny markdown subset renderer for chat replies.
 *
 * Handles: paragraphs, line breaks, **bold**, *italic*, `code`, simple URLs,
 * bullet lists, code fences. Output is HTML-escaped first, then small
 * substitutions are applied. Good enough for the chat panel; not a full
 * markdown engine.
 */
export function renderMarkdownLite(input: string): string {
  if (!input) return "";
  const escaped = input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  const codeFenced = escaped.replace(
    /```([\s\S]*?)```/g,
    (_match, code) => `<pre>${code}</pre>`
  );

  // Process per-paragraph (split on double newline)
  const paragraphs = codeFenced.split(/\n\n+/);
  const rendered = paragraphs.map((paragraph) => {
    if (paragraph.startsWith("<pre>")) return paragraph;
    const lines = paragraph.split("\n");
    const isList = lines.every((line) => /^\s*[-*]\s+/.test(line) || line.trim() === "");
    if (isList) {
      const items = lines
        .filter((line) => line.trim() !== "")
        .map((line) => line.replace(/^\s*[-*]\s+/, ""));
      return `<ul>${items.map((item) => `<li>${inline(item)}</li>`).join("")}</ul>`;
    }
    return `<p>${lines.map(inline).join("<br>")}</p>`;
  });
  return rendered.join("");
}

function inline(text: string): string {
  // bold + italic + code spans
  let out = text
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
  // bare URLs
  out = out.replace(
    /(https?:\/\/[^\s<>"']+)/g,
    '<a href="$1" target="_blank" rel="noreferrer">$1</a>'
  );
  return out;
}
