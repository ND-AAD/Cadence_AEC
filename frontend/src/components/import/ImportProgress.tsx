interface ImportProgressStep {
  label: string;
  status: "pending" | "active" | "done";
}

interface ImportProgressProps {
  steps: ImportProgressStep[];
  summary: string | null;
}

export function ImportProgress({ steps, summary }: ImportProgressProps) {
  return (
    <div className="space-y-3 py-4">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center gap-2">
          {/* Status indicator */}
          <span className="w-4 text-center shrink-0">
            {step.status === "done" && (
              <span className="text-xs text-ink">✓</span>
            )}
            {step.status === "active" && (
              <span className="text-xs text-ink animate-pulse">●</span>
            )}
            {step.status === "pending" && (
              <span className="text-xs text-trace">○</span>
            )}
          </span>

          {/* Label */}
          <span
            className={`text-sm ${
              step.status === "pending"
                ? "text-trace"
                : step.status === "active"
                ? "text-ink"
                : "text-ink"
            }`}
          >
            {step.label}
          </span>
        </div>
      ))}

      {/* Summary line */}
      {summary && (
        <div className="pt-2 border-t border-rule">
          <p className="text-sm font-medium text-ink">{summary}</p>
        </div>
      )}
    </div>
  );
}
