// ─── Breadcrumb Chevron ───────────────────────────────────────────
// Shared chevron SVG used between breadcrumb segments.
// Extracted from UniversalTemplate.tsx prototype.

interface BreadcrumbChevronProps {
  className?: string;
}

export function BreadcrumbChevron({ className }: BreadcrumbChevronProps) {
  return (
    <svg
      className={`w-3.5 h-3.5 shrink-0 ${className ?? "text-trace"}`}
      viewBox="0 0 14 14"
      fill="none"
    >
      <path
        d="M5 3l4 4-4 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
