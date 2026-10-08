/**
 * Minimal, dependency-free markdown renderer for assistant responses.
 * Escapes HTML first, then applies a small, safe subset of markdown.
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function inline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|\s)\*(?!\s)(.+?)\*/g, "$1<em>$2</em>")
    .replace(/`([^`]+)`/g, '<code class="rounded bg-slate-100 px-1 py-0.5 text-[0.85em]">$1</code>');
}

export function toHtml(markdown: string): string {
  const lines = escapeHtml(markdown ?? "").split("\n");
  const out: string[] = [];
  let listType: "ul" | "ol" | null = null;

  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`);
      listType = null;
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      closeList();
      continue;
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      closeList();
      out.push(
        `<h3 class="mt-4 mb-2 text-base font-semibold text-slate-800">${inline(heading[2])}</h3>`,
      );
      continue;
    }

    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    if (bullet) {
      if (listType !== "ul") {
        closeList();
        out.push('<ul class="my-2 list-disc space-y-1 pl-5">');
        listType = "ul";
      }
      out.push(`<li>${inline(bullet[1])}</li>`);
      continue;
    }

    const ordered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (ordered) {
      if (listType !== "ol") {
        closeList();
        out.push('<ol class="my-2 list-decimal space-y-1 pl-5">');
        listType = "ol";
      }
      out.push(`<li>${inline(ordered[1])}</li>`);
      continue;
    }

    closeList();
    out.push(`<p class="my-2 leading-relaxed">${inline(line)}</p>`);
  }
  closeList();
  return out.join("");
}

export default function Markdown({ content }: { content: string }) {
  return <div dangerouslySetInnerHTML={{ __html: toHtml(content) }} />;
}
