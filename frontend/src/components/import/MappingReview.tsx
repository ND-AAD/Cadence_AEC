import { useState } from "react";
import { useTypeRegistry } from "@/hooks/useTypeRegistry";
import { CreateTypeInline } from "./CreateTypeInline";
import type { ColumnProposal, ProposedMappingResponse } from "@/api/import";

interface MappingReviewProps {
  proposal: ProposedMappingResponse;
  onConfirm: (corrections: Record<string, string | null>, targetType?: string) => void;
  onCancel: () => void;
  /** Re-run analysis after creating a new type. */
  onReanalyze?: () => void;
}

export function MappingReview({ proposal, onConfirm, onCancel, onReanalyze }: MappingReviewProps) {
  const { registry, getType, refresh: refreshTypes } = useTypeRegistry();
  const [showCreateType, setShowCreateType] = useState(false);
  const [corrections, setCorrections] = useState<Record<string, string | null>>({});
  const [customInputs, setCustomInputs] = useState<Set<string>>(new Set());
  const [customValues, setCustomValues] = useState<Record<string, string>>({});

  // Get property definitions for the target item type
  const typeConfig = getType(proposal.target_item_type);
  const propertyOptions = typeConfig?.properties ?? [];

  function handlePropertyChange(columnName: string, value: string) {
    if (value === "__custom__") {
      setCustomInputs((prev) => new Set(prev).add(columnName));
      // Auto-generate a snake_case property name from the column header
      const snake = columnName.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
      setCustomValues((prev) => ({ ...prev, [columnName]: snake }));
      setCorrections((prev) => ({ ...prev, [columnName]: snake }));
      return;
    }
    setCustomInputs((prev) => { const s = new Set(prev); s.delete(columnName); return s; });
    setCorrections((prev) => ({
      ...prev,
      [columnName]: value === "__skip__" ? null : value,
    }));
  }

  function handleCustomPropertyName(columnName: string, propName: string) {
    const snake = propName.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    setCustomValues((prev) => ({ ...prev, [columnName]: snake }));
    setCorrections((prev) => ({ ...prev, [columnName]: snake || null }));
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
    const typeOverride = selectedType !== proposal.target_item_type ? selectedType : undefined;
    onConfirm(corrections, typeOverride);
  }

  const proposedColumnNames = new Set(proposal.columns.map((c) => c.column_name));
  const allColumns = [
    ...proposal.columns,
    ...proposal.unmatched_columns
      .filter((name) => !proposedColumnNames.has(name))
      .map((name) => ({
        column_name: name,
        proposed_property: null,
        confidence: 0,
        match_method: "unmatched",
        alternatives: [],
      })),
  ];

  function handleTypeCreated(_typeName: string) {
    setShowCreateType(false);
    refreshTypes();
    onReanalyze?.();
  }

  if (showCreateType) {
    const allColumnNames = [
      ...proposal.columns.map((c) => c.column_name),
      ...proposal.unmatched_columns,
    ];
    return (
      <CreateTypeInline
        unmatchedColumns={proposal.unmatched_columns}
        allColumns={allColumnNames}
        onTypeCreated={handleTypeCreated}
        onCancel={() => setShowCreateType(false)}
      />
    );
  }

  // Build list of importable types for the type selector
  const allTypes = registry
    ? Object.entries(registry)
        .filter(([, tc]) => tc.category === "spatial")
        .map(([name, tc]) => ({ name, label: tc.label }))
        .sort((a, b) => a.label.localeCompare(b.label))
    : [];

  const [selectedType, setSelectedType] = useState(proposal.target_item_type);
  // When the user changes the target type, update the property options
  const activeTypeConfig = getType(selectedType);
  const activePropertyOptions = activeTypeConfig?.properties ?? propertyOptions;

  function handleTypeChange(newType: string) {
    setSelectedType(newType);
    // Clear all corrections since the property set changed
    setCorrections({});
    setCustomInputs(new Set());
    setCustomValues({});
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-ink mb-1">Column Mapping Review</h3>
        <p className="text-xs text-graphite">
          Confirm the data type and column mappings before importing.
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

        {/* Data type row — first row in table */}
        <div className="flex items-center gap-2 px-3 py-2 bg-vellum">
          <div className="flex-1 min-w-0">
            <span className="text-xs font-medium text-graphite uppercase tracking-wider">Data Type</span>
          </div>
          <span className="text-trace text-xs shrink-0">→</span>
          <div className="flex-1 min-w-0">
            <select
              value={selectedType}
              onChange={(e) => {
                if (e.target.value === "__create__") {
                  setShowCreateType(true);
                } else {
                  handleTypeChange(e.target.value);
                }
              }}
              className="w-full px-2 py-1 text-sm font-mono bg-sheet border border-rule text-ink
                         focus:outline-none focus:border-ink transition-colors"
            >
              {allTypes.map((t) => (
                <option key={t.name} value={t.name}>{t.label}</option>
              ))}
              {!allTypes.some((t) => t.name === proposal.target_item_type) && (
                <option value={proposal.target_item_type}>{proposal.target_item_type}</option>
              )}
              <option value="__create__">+ New Type</option>
            </select>
          </div>
          <div className="w-8 text-center shrink-0">
            <span className="text-xs text-trace">
              {Math.round(proposal.overall_confidence * 100)}%
            </span>
          </div>
        </div>

        {/* Column mapping rows — skip empty column names */}
        {allColumns.filter((col) => col.column_name.trim()).map((col) => {
          const isIdentifier = col.column_name === proposal.identifier_column;
          const effective = getEffectiveProperty(col);
          return (
            <div
              key={col.column_name}
              className={`flex items-center gap-2 px-3 py-2 ${
                isIdentifier ? "bg-vellum" : ""
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
                  <span className="text-sm text-ink font-medium">{selectedType} ID</span>
                ) : customInputs.has(col.column_name) ? (
                  <div className="flex gap-1">
                    <input
                      type="text"
                      value={customValues[col.column_name] ?? ""}
                      onChange={(e) => handleCustomPropertyName(col.column_name, e.target.value)}
                      placeholder="property_name"
                      autoFocus
                      className="flex-1 px-2 py-1 text-sm font-mono bg-sheet border border-ink text-ink
                                 focus:outline-none transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => handlePropertyChange(col.column_name, "__skip__")}
                      className="px-1.5 text-xs text-trace hover:text-ink transition-colors"
                      title="Cancel custom property"
                    >
                      ×
                    </button>
                  </div>
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
                    {activePropertyOptions
                      .filter((p) => p.name !== col.proposed_property)
                      .map((p) => (
                        <option key={p.name} value={p.name}>
                          {p.label || p.name}
                        </option>
                      ))}
                    <option value="__custom__">— new property —</option>
                  </select>
                )}
              </div>

              {/* Status indicator */}
              <div className="w-8 text-center shrink-0">
                {isIdentifier ? (
                  <span className="text-xs text-trace">🔑</span>
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
