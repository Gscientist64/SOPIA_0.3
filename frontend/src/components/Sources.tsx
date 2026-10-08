import { FileText } from "lucide-react";
import type { Citation } from "../types";

const MAX_VISIBLE = 3;

function location(citation: Citation): string {
  return [
    citation.version ? `v${citation.version}` : null,
    citation.section ? `§ ${citation.section}` : null,
    citation.page ? `p.${citation.page}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

/**
 * The SOP excerpts a generated question was authored from.
 *
 * Quiz, exam and interview questions are grounded in the organisation's own
 * documents, so every question can be traced back to its source.
 */
export default function Sources({
  citations,
  className = "",
}: {
  citations?: Citation[] | null;
  className?: string;
}) {
  if (!citations || citations.length === 0) return null;
  const visible = citations.slice(0, MAX_VISIBLE);
  const hidden = citations.length - visible.length;

  return (
    <div className={`rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 ${className}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        Grounded in your SOPs
      </p>
      <ul className="mt-1 space-y-0.5">
        {visible.map((citation, index) => (
          <li key={index} className="flex items-start gap-1.5 text-xs text-slate-600">
            <FileText size={12} className="mt-0.5 shrink-0 text-teal-600" />
            <span className="min-w-0">
              <span className="font-medium text-slate-700">
                {citation.document_title ?? "Source document"}
              </span>
              {location(citation) && <span className="text-slate-500"> · {location(citation)}</span>}
            </span>
          </li>
        ))}
      </ul>
      {hidden > 0 && <p className="mt-0.5 text-xs text-slate-400">+{hidden} more excerpt(s)</p>}
    </div>
  );
}
