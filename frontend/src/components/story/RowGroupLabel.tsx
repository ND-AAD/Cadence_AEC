// ─── Row Group Label ──────────────────────────────────────────────
// Lightweight separator between property and connection sections.
// system.md: text-xs font-mono text-trace uppercase tracking-wide bg-vellum/50

interface RowGroupLabelProps {
  label: string;
}

export function RowGroupLabel({ label }: RowGroupLabelProps) {
  return (
    <div className="px-4 py-1.5 text-xs font-mono text-trace uppercase tracking-wide bg-vellum/50">
      {label}
    </div>
  );
}
