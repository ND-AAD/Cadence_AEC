// ─── Breadcrumb Segment ───────────────────────────────────────────
// A single clickable segment in the breadcrumb path.
//
// Styling per system.md:
//   Current (last):    font-medium text-ink  (not clickable)
//   Ancestor:          text-graphite hover:text-ink cursor-pointer
//   Inactive (dead):   text-trace
//   Gap ("..."):       text-trace  (not clickable)

import type { BreadcrumbItem } from "@/types/navigation";

interface BreadcrumbSegmentProps {
  item: BreadcrumbItem;
  /** Is this the last (current) segment? */
  isLast: boolean;
  /** Is this on the inactive/dead fork branch? */
  isInactive?: boolean;
  /** Click handler for ancestor navigation. Undefined = not clickable. */
  onClick?: () => void;
}

export function BreadcrumbSegment({
  item,
  isLast,
  isInactive,
  onClick,
}: BreadcrumbSegmentProps) {
  const isGap = item.name === "...";

  // Determine styling based on segment position and state.
  let className: string;
  if (isInactive) {
    className = "text-trace";
  } else if (isLast) {
    className = "font-medium text-ink";
  } else if (isGap) {
    className = "text-trace";
  } else {
    className = "text-graphite hover:text-ink cursor-pointer transition-colors duration-100";
  }

  // Only ancestors (not last, not gap, not inactive) are clickable.
  const isClickable = !isLast && !isGap && !isInactive && !!onClick;

  if (isClickable) {
    return (
      <button
        onClick={onClick}
        className={`${className} bg-transparent border-none p-0 text-sm focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-1 rounded-sm`}
        type="button"
      >
        {item.name}
      </button>
    );
  }

  return <span className={`text-sm ${className}`}>{item.name}</span>;
}
