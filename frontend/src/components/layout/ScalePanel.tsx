// ─── Scale Panel ──────────────────────────────────────────────────
// Left side panel: navigation accordion groups of connected items.
// DS-1 §2.2: Default open (~280px). Collapses to 0 (hidden).
// Toggle lives outside in LayoutFrame — panel is pure content.

import type { ReactNode } from "react";

interface ScalePanelProps {
  isOpen: boolean;
  children?: ReactNode;
}

export function ScalePanel({ isOpen, children }: ScalePanelProps) {
  return (
    <div
      className="shrink-0 bg-vellum border-r border-rule transition-[width] duration-200 ease-in-out overflow-hidden"
      style={{ width: isOpen ? 280 : 0 }}
    >
      <div
        className={`w-[280px] h-full overflow-y-auto overflow-x-hidden transition-opacity duration-150 ${
          isOpen ? "opacity-100 delay-75" : "opacity-0"
        }`}
      >
        {children ?? (
          <div className="p-4 text-sm text-trace">
            <p className="text-xs font-mono uppercase tracking-wide">
              Scale Panel
            </p>
            <p className="mt-2 text-xs text-trace/70">
              Connected items will appear here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
