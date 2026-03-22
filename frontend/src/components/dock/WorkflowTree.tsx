// ─── Workflow Tree ────────────────────────────────────────────────
// Three-level navigable tree for the exec summary dock.
// DS-2 §10.1: Categories → Type groups → Instances.
//
// Categories: Conflicts, Changes, Directives, Resolved, Notes
// Conflicts/Changes: grouped by item type
// Directives: grouped by target source
// All instances clickable → page turn to workflow item.

import { useState, useCallback } from "react";

// ─── Types ──────────────────────────────────────────────────────

export interface WorkflowInstance {
  id: string;
  label: string;
  propertyName?: string;
}

export interface WorkflowTypeGroup {
  typeName: string;
  count: number;
  instances: WorkflowInstance[];
}

export interface WorkflowCategory {
  /** Category key: "conflicts" | "changes" | "directives" | "resolved" | "notes" */
  key: string;
  /** Display label. */
  label: string;
  /** Color class for the category accent (border + text). */
  colorClass: string;
  /** Border color class. */
  borderClass: string;
  /** Total count. */
  count: number;
  /** Whether collapsed by default. */
  collapsedByDefault?: boolean;
  /** Type groups within this category. */
  groups: WorkflowTypeGroup[];
}

interface WorkflowTreeProps {
  /** Categories to render. */
  categories: WorkflowCategory[];
  /** Navigate to a workflow item. */
  onNavigate: (itemId: string) => void;
}

// ─── Component ──────────────────────────────────────────────────

export function WorkflowTree({ categories, onNavigate }: WorkflowTreeProps) {
  // Track expanded state per category and per type group.
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(() => {
    // Expand non-default-collapsed categories.
    const initial = new Set<string>();
    for (const cat of categories) {
      if (!cat.collapsedByDefault && cat.count > 0) {
        initial.add(cat.key);
      }
    }
    return initial;
  });
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const toggleCategory = useCallback((key: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const toggleGroup = useCallback((key: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  if (categories.length === 0) {
    return (
      <div className="px-3 py-4 text-xs text-trace">
        No active workflow items.
      </div>
    );
  }

  return (
    <div className="divide-y divide-rule">
      {categories.map((cat) => {
        const isCatExpanded = expandedCategories.has(cat.key);

        return (
          <div key={cat.key}>
            {/* Category row */}
            <button
              type="button"
              onClick={() => toggleCategory(cat.key)}
              className={`w-full flex items-center justify-between px-3 py-2 text-left border-l-2 ${cat.borderClass} hover:bg-board/20 transition-colors duration-100`}
            >
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-trace">
                  {isCatExpanded ? "▼" : "▸"}
                </span>
                <span className={`text-sm font-semibold tracking-tight ${cat.colorClass}`}>
                  {cat.label}
                </span>
              </div>
              <span className={`text-xs font-mono ${cat.colorClass}`}>
                {cat.count}
              </span>
            </button>

            {/* Type groups */}
            {isCatExpanded && (
              <div className="ml-4">
                {cat.groups.map((group) => {
                  const groupKey = `${cat.key}:${group.typeName}`;
                  const isGroupExpanded = expandedGroups.has(groupKey);

                  return (
                    <div key={group.typeName}>
                      {/* Type row */}
                      <button
                        type="button"
                        onClick={() => toggleGroup(groupKey)}
                        className="w-full flex items-center justify-between px-2 py-1 text-left hover:bg-board/20 transition-colors duration-100"
                      >
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs text-trace">
                            {isGroupExpanded ? "▼" : "▸"}
                          </span>
                          <span className="text-xs font-medium text-ink">
                            {group.typeName}
                          </span>
                        </div>
                        <span className="text-xs font-mono text-graphite">
                          {group.count}
                        </span>
                      </button>

                      {/* Instance rows */}
                      {isGroupExpanded && (
                        <div className="ml-5">
                          {group.instances.map((instance) => (
                            <button
                              key={instance.id}
                              type="button"
                              onClick={() => onNavigate(instance.id)}
                              className="w-full flex items-center gap-1.5 px-2 py-0.5 text-left hover:bg-board/20 transition-colors duration-100"
                            >
                              <span className="text-xs font-mono text-graphite truncate">
                                {instance.label}
                              </span>
                              {instance.propertyName && (
                                <span className="text-xs text-trace truncate">
                                  · {instance.propertyName}
                                </span>
                              )}
                            </button>
                          ))}
                          {group.count > group.instances.length && (
                            <div className="px-2 py-0.5 text-xs text-trace">
                              + {group.count - group.instances.length} more
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
