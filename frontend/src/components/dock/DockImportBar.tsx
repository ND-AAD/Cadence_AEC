// ─── Dock Import Bar ──────────────────────────────────────────────
// Bottom section of the exec summary dock showing last import info.
// DS-1 §7.3: "Last import: [Source Name] at [Context] · 2 hours ago"
// system.md: text-xs text-trace metadata styling.

import type { ImportSummaryResponse } from "@/types/dashboard";

// ─── Relative time formatting ────────────────────────────────────

function relativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = Date.now();
  const diffMs = now - date.getTime();

  if (diffMs < 0) return "just now";

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return "just now";

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;

  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;

  return `${Math.floor(months / 12)}y ago`;
}

// ─── Component ───────────────────────────────────────────────────

interface DockImportBarProps {
  importSummary: ImportSummaryResponse | null;
}

export function DockImportBar({ importSummary }: DockImportBarProps) {
  if (!importSummary?.imported_at) return null;

  const source = importSummary.source_identifier ?? "Unknown source";
  const context = importSummary.context_identifier;
  const time = relativeTime(importSummary.imported_at);

  return (
    <div className="px-3 py-2 border-t border-rule text-xs text-trace">
      <span className="text-graphite">Last import:</span>{" "}
      <span className="font-medium text-ink">{source}</span>
      {context && (
        <>
          {" at "}
          <span className="font-medium text-ink">{context}</span>
        </>
      )}
      {" · "}
      <span>{time}</span>
      {importSummary.new_conflicts > 0 && (
        <>
          {" · "}
          <span className="text-redline-ink">
            {importSummary.new_conflicts} new conflict
            {importSummary.new_conflicts !== 1 ? "s" : ""}
          </span>
        </>
      )}
    </div>
  );
}
