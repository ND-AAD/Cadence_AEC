import { useState } from "react";
import { useTypeRegistry } from "@/hooks/useTypeRegistry";
import type { ColumnProposal, ProposedMappingResponse } from "@/api/import";

interface MappingReviewProps {
  proposal: ProposedMappingResponse;
  onConfirm: (corrections: Record<string, string | null>) => void;
  onCancel: () => void;
}

export function MappingReview({ proposal, onConfirm, onCancel }: MappingReviewProps) {
  const { getType } = useTypeRegistry();
  const [corrections, setCorrections] = useState<Record<string, string | null>>({});
  const [editing, setEditing] = useState<Set<string>>(new Set());

  // Get property definitions for the target item type
  const typeConfig = getType(proposal.target_item_type);
  const propertyOptions = typeConfig?.properties ?? [];

  function handlePropertyChange(columnName: string, value: string) {
    setCorrections((prev) => ({
      ...prev,
      [columnName]: value === "__skip__" ? null : value,
    }));
  }

  function getEffectiveProperty(col: ColumnProposal): string | null {
    const colName = columnName(col);
    if (colName in corrections) return corrections[colName];
    return col.proposed_property;
  }

  function columnName(col: ColumnProposal): string {
    return col.column_name;
  }

  function handleConfirm() {
    onConfirm(corrections);
  }

  const allColumns = [
    ...proposal.columns,
    ...proposal.unmatched_columns.map((name) => ({
      column_name: name,
      proposed_property: null,
      confidence: 0,
      match_method: "unmatched",
      alternatives: [],
    })),
  ];

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-ink mb-1">Column Mapping Review</h3>
        <p className="text-xs text-graphite">
          We detected columns of <span className="font-mono">{proposal.target_item_type}</span> data.
          Here's how we mapped your columns:
        </p>
      </div>

      {/* Mapping table */}
      <div className="border border-rule divide-y divide-rule">
        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2 bg-vellum">
          <span className="flex-1 text-xs font-medium text-graphite uppercase tracking-wider">Column</span>
          <span className="w-8" />
          <span className="flex-1 text-xs font-medium text-graphite uppercase tracking-wider">Property</span>
          <span className="w-8" />
        </div>

        {/* Rows */}
        {allColumns.map((col) => {
          const isIdentifier = col.column_name === proposal.identifier_column;
          const effective = getEffectiveProperty(col);
          const isHighConfidence = col.confidence >= 0.8 && col.proposed_property;
          const isLowConfidence = col.confidence > 0 && col.confidence < 0.8 && col.proposed_property;
          const isUnmapped = !col.proposed_property && !(col.column_name in corrections);

          return (
            <div
              key={col.column_name}
              className={`flex items-center gap-2 px-3 py-2 ${
                isIdentifier ? "bg-vellum" : isLowConfidence || isUnmapped ? "bg-pencil-wash/30" : ""
              }`}
            >
              {/* Column name */}
              <div className="flex-1 min-w-0">
                <span className="text-sm text-ink font-mono truncate block">
                  {col.column_name}
                </span>
                {isIdentifier && (
                  <span className="text-[10px] text-trace uppercase tracking-wider">identifier</span>
                )}
              </div>

              {/* Arrow */}
              <span className="text-trace text-xs shrink-0">→</span>

              {/* Property mapping */}
              <div className="flex-1 min-w-0">
                {isIdentifier ? (
                  <span className="text-sm text-ink font-medium">{proposal.target_item_type} ID</span>
                ) : isHighConfidence && !editing.has(col.column_name) && !(col.column_name in corrections) ? (
                  <span className="text-sm text-ink">{col.proposed_property}</span>
                ) : (
                  <select
                    value={effective ?? "__skip__"}
                    onChange={(e) => handlePropertyChange(col.column_name, e.target.value)}
                    className="w-full px-2 py-1 text-sm bg-sheet border border-rule text-ink
                               focus:outline-none focus:border-ink transition-colors"
                  >
                    <option value="__skip__">— skip —</option>
                    {col.proposed_property && (
                      <option value={col.proposed_property}>{col.proposed_property}</option>
                    )}
                    {propertyOptions
                      .filter((p) => p.name !== col.proposed_property)
                      .map((p) => (
                        <option key={p.name} value={p.name}>
                          {p.label || p.name}
                        </option>
                      ))}
                  </select>
                )}
              </div>

              {/* Status indicator / edit toggle */}
              <div className="w-8 text-center shrink-0">
                {isIdentifier ? (
                  <span className="text-xs text-trace">🔑</span>
                ) : isHighConfidence && !editing.has(col.column_name) && !(col.column_name in corrections) ? (
                  <button
                    type="button"
                    onClick={() => setEditing((prev) => new Set(prev).add(col.column_name))}
                    className="text-xs text-trace hover:text-ink transition-colors cursor-pointer"
                    title="Edit mapping"
                  >
                    ✎
                  </button>
                ) : (
                  <span className="text-xs text-trace">✎</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary line */}
      <div className="text-xs text-trace">
        Identifier: <span className="font-mono text-ink">{proposal.identifier_column}</span>
        {" · "}
        Type: <span className="font-mono text-ink">{proposal.target_item_type}</span>
        {" · "}
        Confidence: <span className="font-mono text-ink">{Math.round(proposal.overall_confidence * 100)}%</span>
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="px-3 py-1.5 text-xs text-graphite border border-rule hover:text-ink transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleConfirm}
          className="px-3 py-1.5 text-xs font-medium bg-ink text-sheet hover:bg-ink/90 transition-colors"
        >
          Confirm & Import
        </button>
      </div>
    </div>
  );
}
