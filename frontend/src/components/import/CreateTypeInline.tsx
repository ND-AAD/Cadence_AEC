import { useState } from "react";
import { createType } from "@/api/types";

interface PropertyRow {
  name: string;
  label: string;
  dataType: string;
  included: boolean;
}

interface CreateTypeInlineProps {
  /** Column headers from the uploaded file (for pre-populating properties). */
  unmatchedColumns: string[];
  /** All column headers (for identifier detection). */
  allColumns: string[];
  /** Called when type is successfully created. */
  onTypeCreated: (typeName: string) => void;
  /** Called when user cancels. */
  onCancel: () => void;
}

/** Convert a label to a snake_case identifier. "Hardware Set" → "hardware_set" */
function toIdentifier(label: string): string {
  return label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
}

const DATA_TYPES = ["string", "number", "boolean", "date", "enum"];

export function CreateTypeInline({
  unmatchedColumns,
  allColumns: _allColumns,
  onTypeCreated,
  onCancel,
}: CreateTypeInlineProps) {
  const [typeLabel, setTypeLabel] = useState("");
  const [typeName, setTypeName] = useState("");
  const [labelTouched, setLabelTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pre-populate property rows from unmatched columns
  const [properties, setProperties] = useState<PropertyRow[]>(() =>
    unmatchedColumns.map((col) => ({
      name: toIdentifier(col),
      label: col,
      dataType: "string",
      included: true,
    })),
  );

  function handleLabelChange(value: string) {
    setTypeLabel(value);
    setLabelTouched(true);
    // Auto-generate identifier unless user has manually edited it
    if (!labelTouched || typeName === toIdentifier(typeLabel)) {
      setTypeName(toIdentifier(value));
    }
  }

  function handleNameChange(value: string) {
    setTypeName(toIdentifier(value));
  }

  function toggleProperty(index: number) {
    setProperties((prev) =>
      prev.map((p, i) => (i === index ? { ...p, included: !p.included } : p)),
    );
  }

  function updatePropertyDataType(index: number, dataType: string) {
    setProperties((prev) =>
      prev.map((p, i) => (i === index ? { ...p, dataType } : p)),
    );
  }

  function addProperty() {
    setProperties((prev) => [
      ...prev,
      { name: "", label: "", dataType: "string", included: true },
    ]);
  }

  function updatePropertyLabel(index: number, label: string) {
    setProperties((prev) =>
      prev.map((p, i) =>
        i === index ? { ...p, label, name: toIdentifier(label) } : p,
      ),
    );
  }

  async function handleCreate() {
    if (!typeName) return;
    setSubmitting(true);
    setError(null);

    const includedProps = properties
      .filter((p) => p.included && p.name)
      .map((p) => ({
        name: p.name,
        label: p.label || p.name,
        data_type: p.dataType,
      }));

    try {
      await createType({
        type_name: typeName,
        label: typeLabel || typeName,
        property_defs: includedProps.length > 0 ? includedProps : undefined,
      });
      onTypeCreated(typeName);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create type");
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-ink mb-1">Create New Type</h3>
        <p className="text-xs text-graphite">
          Define a new item type for this data. Properties are pre-populated from
          unmatched columns.
        </p>
      </div>

      {/* Type name fields */}
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-graphite mb-1">
            Type Label
          </label>
          <input
            type="text"
            value={typeLabel}
            onChange={(e) => handleLabelChange(e.target.value)}
            placeholder="e.g. Hardware Set"
            className="w-full px-2 py-1.5 text-sm bg-sheet border border-rule text-ink
                       placeholder:text-trace focus:outline-none focus:border-ink transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-graphite mb-1">
            Identifier
          </label>
          <input
            type="text"
            value={typeName}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="hardware_set"
            className="w-full px-2 py-1.5 text-sm bg-sheet border border-rule text-ink font-mono
                       placeholder:text-trace focus:outline-none focus:border-ink transition-colors"
          />
        </div>
      </div>

      {/* Property list */}
      {properties.length > 0 && (
        <div>
          <label className="block text-xs font-medium text-graphite mb-1.5">
            Properties
          </label>
          <div className="border border-rule divide-y divide-rule">
            {/* Header */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-vellum">
              <span className="w-6" />
              <span className="flex-1 text-xs font-medium text-graphite uppercase tracking-wider">
                Name
              </span>
              <span className="w-24 text-xs font-medium text-graphite uppercase tracking-wider">
                Type
              </span>
            </div>
            {properties.map((prop, i) => (
              <div
                key={i}
                className={`flex items-center gap-2 px-3 py-1.5 ${
                  prop.included ? "" : "opacity-40"
                }`}
              >
                <input
                  type="checkbox"
                  checked={prop.included}
                  onChange={() => toggleProperty(i)}
                  className="w-4 h-4 shrink-0 accent-ink"
                />
                <div className="flex-1 min-w-0">
                  <input
                    type="text"
                    value={prop.label}
                    onChange={(e) => updatePropertyLabel(i, e.target.value)}
                    className="w-full text-sm text-ink bg-transparent focus:outline-none
                               border-b border-transparent focus:border-rule transition-colors"
                  />
                  <span className="text-[10px] text-trace font-mono">{prop.name}</span>
                </div>
                <select
                  value={prop.dataType}
                  onChange={(e) => updatePropertyDataType(i, e.target.value)}
                  disabled={!prop.included}
                  className="w-24 px-1 py-0.5 text-xs bg-sheet border border-rule text-ink
                             focus:outline-none focus:border-ink transition-colors"
                >
                  {DATA_TYPES.map((dt) => (
                    <option key={dt} value={dt}>
                      {dt}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={addProperty}
            className="mt-1.5 text-xs text-trace hover:text-ink transition-colors"
          >
            + Add property
          </button>
        </div>
      )}

      {/* Error message */}
      {error && (
        <p className="text-xs text-redline-ink">{error}</p>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          disabled={submitting}
          className="px-3 py-1.5 text-xs text-graphite border border-rule hover:text-ink transition-colors
                     disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onClick={handleCreate}
          disabled={!typeName || submitting}
          className="px-3 py-1.5 text-xs font-medium bg-ink text-sheet hover:bg-ink/90
                     transition-colors disabled:opacity-50"
        >
          {submitting ? "Creating..." : "Create Type"}
        </button>
      </div>
    </div>
  );
}
