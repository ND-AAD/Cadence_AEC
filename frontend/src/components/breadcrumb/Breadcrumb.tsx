// ─── Breadcrumb ───────────────────────────────────────────────────
// Interactive breadcrumb with linear and forked display modes.
//
// DS-1 §3.3: Linear path with clickable ancestors.
// DS-1 §3.4: Z-axis fork with active branch on top, dead branch below.
// system.md: Segments separated by > chevrons. Current: font-medium text-ink.
//            Ancestors: text-graphite hover:text-ink.

import { useContext } from "react";
import { NavigationContext } from "@/context/NavigationContext";
import type { BreadcrumbItem } from "@/types/navigation";
import { BreadcrumbChevron } from "./BreadcrumbChevron";
import { BreadcrumbSegment } from "./BreadcrumbSegment";

// ─── Segment List Renderer ────────────────────────────────────────

function SegmentList({
  items,
  isInactive,
  startIndex,
  onSegmentClick,
}: {
  items: BreadcrumbItem[];
  isInactive?: boolean;
  /** The index offset within the full breadcrumb for click targeting. */
  startIndex: number;
  onSegmentClick?: (index: number) => void;
}) {
  return (
    <>
      {items.map((item, i) => {
        const isLast = !isInactive && i === items.length - 1;
        const globalIndex = startIndex + i;
        return (
          <span key={item.id + "-" + i} className="flex items-center gap-1.5">
            {i > 0 && (
              <BreadcrumbChevron
                className={isInactive ? "text-trace/50" : undefined}
              />
            )}
            <BreadcrumbSegment
              item={item}
              isLast={isLast}
              isInactive={isInactive}
              onClick={
                !isLast && !isInactive && onSegmentClick
                  ? () => onSegmentClick(globalIndex)
                  : undefined
              }
            />
          </span>
        );
      })}
    </>
  );
}

// ─── Main Breadcrumb Component ────────────────────────────────────

export function Breadcrumb() {
  const navCtx = useContext(NavigationContext);

  // Outside NavigationProvider (e.g. project list) — render empty placeholder.
  if (!navCtx) {
    return <div className="min-h-[20px]" />;
  }

  const { state, popTo } = navCtx;
  const { breadcrumb, fork, pending } = state;

  // Show the full breadcrumb path. The project root is always the first segment.
  const displayBreadcrumb = breadcrumb;

  // Empty state — breadcrumb not yet initialized.
  if (displayBreadcrumb.length === 0 && !fork) {
    return <div className="min-h-[20px]" />;
  }

  // Forked breadcrumb — Z-axis lateral jump is active.
  // Stem renders once on the centerline. The fork branches stack at
  // the split point, vertically centered so the stem stays aligned
  // with "Cadence" in the breadcrumb bar. The fork connector (╰)
  // visually links the dead branch to the split point.
  if (fork) {
    return (
      <div
        className={`flex items-center gap-1.5 min-h-[20px] transition-opacity duration-150 ${pending ? "opacity-60" : "opacity-100"}`}
      >
        {/* Shared stem — stays on the centerline */}
        <SegmentList
          items={fork.stem}
          startIndex={0}
          onSegmentClick={popTo}
        />

        {/* Fork point — two branches stacked, centered around stem baseline */}
        {(fork.active.length > 0 || fork.inactive.length > 0) && (
          <div className="flex flex-col items-start">
            {/* Active branch (top) */}
            <div className="flex items-center gap-1.5">
              {fork.stem.length > 0 && <BreadcrumbChevron />}
              <SegmentList
                items={fork.active}
                startIndex={fork.stem.length}
                onSegmentClick={popTo}
              />
            </div>

            {/* Fork connector + inactive branch (bottom) */}
            <div className="flex items-center gap-1.5">
              {/* Fork connector: vertical line + horizontal turn (╰) */}
              <div className="relative w-3.5 h-4 shrink-0">
                <div className="absolute top-0 left-1/2 w-px h-2 bg-trace/40" />
                <div className="absolute top-2 left-1/2 w-1.5 h-px bg-trace/40" />
              </div>

              <SegmentList
                items={fork.inactive}
                isInactive
                startIndex={fork.stem.length}
              />
            </div>
          </div>
        )}
      </div>
    );
  }

  // Linear breadcrumb — standard path display.
  return (
    <div
      className={`flex items-center gap-1.5 min-h-[20px] transition-opacity duration-150 ${pending ? "opacity-60" : "opacity-100"}`}
    >
      <SegmentList
        items={displayBreadcrumb}
        startIndex={0}
        onSegmentClick={popTo}
      />
    </div>
  );
}
