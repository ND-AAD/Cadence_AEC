import type { ReactNode } from "react";

// ─── Helpers ─────────────────────────────────────────────

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section>
      <h2 className="text-lg font-semibold tracking-tight mb-6">{title}</h2>
      {children}
    </section>
  );
}

function Swatch({
  name,
  hex,
  className,
}: {
  name: string;
  hex: string;
  className: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className={`h-12 rounded-md border border-rule ${className}`} />
      <div className="text-xs font-mono text-graphite">{name}</div>
      <div className="text-xs font-mono text-trace">{hex}</div>
    </div>
  );
}

// ─── Typography ──────────────────────────────────────────

function TypographySection() {
  return (
    <Section title="Typography">
      <div className="bg-sheet border border-rule rounded-md p-6 space-y-5">
        <TypeRow size="2xl / 22" className="text-2xl font-semibold tracking-tight">
          Project Alpha
        </TypeRow>
        <TypeRow size="xl / 18" className="text-xl font-semibold tracking-tight">
          Building A — Floor 2
        </TypeRow>
        <TypeRow size="lg / 16" className="text-lg font-medium">
          Room 203 · Doors
        </TypeRow>
        <TypeRow size="md / 14" className="text-md">
          Finish Schedule Rev C — 150 items imported at CD
        </TypeRow>
        <TypeRow size="base / 13" className="text-base">
          Per architect&apos;s direction, schedule takes precedence for finish
          properties.
        </TypeRow>
        <TypeRow size="sm / 12" className="text-sm text-graphite">
          Last imported 2 hours ago · 3 conflicts detected
        </TypeRow>
        <TypeRow size="xs / 11" className="text-xs text-trace uppercase tracking-wide">
          Snapshot · DD Milestone · Finish Schedule
        </TypeRow>

        <div className="border-t border-rule pt-5">
          <TypeRow size="mono" className="font-mono text-sm">
            DR-101 · HW-3 · 3&apos;-0&quot; × 7&apos;-0&quot; · paint
          </TypeRow>
        </div>
      </div>
    </Section>
  );
}

function TypeRow({
  size,
  className,
  children,
}: {
  size: string;
  className: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-baseline gap-4">
      <span className="text-xs font-mono text-trace w-16 shrink-0 text-right">
        {size}
      </span>
      <span className={className}>{children}</span>
    </div>
  );
}

// ─── Colors ──────────────────────────────────────────────

function ColorSection() {
  return (
    <Section title="Tokens">
      <div className="space-y-8">
        <TokenGroup label="Surfaces">
          <Swatch name="sheet" hex="#FAF9F6" className="bg-sheet" />
          <Swatch name="vellum" hex="#F0EFEC" className="bg-vellum" />
          <Swatch name="board" hex="#E7E5E2" className="bg-board" />
        </TokenGroup>

        <TokenGroup label="Text">
          <Swatch name="ink" hex="#1C1B18" className="bg-ink" />
          <Swatch name="graphite" hex="#57554F" className="bg-graphite" />
          <Swatch name="trace" hex="#9D9B95" className="bg-trace" />
        </TokenGroup>

        <TokenGroup label="Rules">
          <Swatch name="rule" hex="#DFDDD9" className="bg-rule" />
          <Swatch name="rule-emphasis" hex="#CECCC7" className="bg-rule-emphasis" />
        </TokenGroup>

        <TokenGroup label="Redline — Conflicts (Wada vermillion)">
          <Swatch name="redline" hex="#E81A00" className="bg-redline" />
          <Swatch name="redline-muted" hex="#EE6A53" className="bg-redline-muted" />
          <Swatch name="redline-wash" hex="#FFF0EB" className="bg-redline-wash" />
          <Swatch name="redline-ink" hex="#A61400" className="bg-redline-ink" />
        </TokenGroup>

        <TokenGroup label="Pencil — Changes (Wada amber)">
          <Swatch name="pencil" hex="#FA9442" className="bg-pencil" />
          <Swatch name="pencil-muted" hex="#FBB978" className="bg-pencil-muted" />
          <Swatch name="pencil-wash" hex="#FFF5EA" className="bg-pencil-wash" />
          <Swatch name="pencil-ink" hex="#B06218" className="bg-pencil-ink" />
        </TokenGroup>

        <TokenGroup label="Stamp — Resolved">
          <Swatch name="stamp" hex="#3D7A4F" className="bg-stamp" />
          <Swatch name="stamp-wash" hex="#F0F7F2" className="bg-stamp-wash" />
          <Swatch name="stamp-ink" hex="#2D5E3B" className="bg-stamp-ink" />
        </TokenGroup>

        <div className="grid grid-cols-6 gap-3">
          <div className="col-span-6">
            <div className="text-xs font-mono text-trace uppercase tracking-wide mb-3">
              Filed / Overlay
            </div>
          </div>
          <Swatch name="filed" hex="#7D7A75" className="bg-filed" />
          <Swatch name="overlay" hex="#002FA7" className="bg-overlay" />
          <Swatch name="overlay-wash" hex="#EFF2FB" className="bg-overlay-wash" />
          <Swatch name="overlay-border" hex="#6A7EB5" className="bg-overlay-border" />
        </div>
      </div>
    </Section>
  );
}

function TokenGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="text-xs font-mono text-trace uppercase tracking-wide mb-3">
        {label}
      </div>
      <div className="grid grid-cols-6 gap-3">{children}</div>
    </div>
  );
}

// ─── Surfaces ────────────────────────────────────────────

function SurfaceSection() {
  return (
    <Section title="Surfaces & Depth">
      <p className="text-sm text-graphite mb-4">
        Borders-only depth. No shadows except floating elements.
      </p>
      <div className="flex gap-4">
        <div className="flex-1 bg-vellum border border-rule rounded-md p-4">
          <div className="text-xs font-mono text-trace mb-3">
            vellum (chrome / sidebar)
          </div>
          <div className="bg-sheet border border-rule rounded-md p-4">
            <div className="text-xs font-mono text-trace mb-3">
              sheet (content / story panel)
            </div>
            <div className="bg-vellum border border-rule rounded p-3">
              <div className="text-xs font-mono text-trace">
                vellum (nested element)
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 space-y-3">
          <div className="bg-sheet border border-rule rounded-md p-3">
            <span className="text-xs font-mono text-trace">
              border-rule — default separator
            </span>
          </div>
          <div className="bg-sheet border border-rule-emphasis rounded-md p-3">
            <span className="text-xs font-mono text-trace">
              border-rule-emphasis — strong separator
            </span>
          </div>
          <div className="bg-sheet shadow-float rounded-md p-3">
            <span className="text-xs font-mono text-trace">
              shadow-float — dropdowns, popovers only
            </span>
          </div>
          <div className="flex gap-3 pt-2">
            <div className="bg-sheet border border-rule rounded-sm px-3 py-1.5 text-xs font-mono text-trace">
              rounded-sm (2px)
            </div>
            <div className="bg-sheet border border-rule rounded-md px-3 py-1.5 text-xs font-mono text-trace">
              rounded-md (4px)
            </div>
            <div className="bg-sheet border border-rule rounded-lg px-3 py-1.5 text-xs font-mono text-trace">
              rounded-lg (6px)
            </div>
          </div>
        </div>
      </div>
    </Section>
  );
}

// ─── The Three States ────────────────────────────────────

function PropertyTableSection() {
  return (
    <Section title="The Temporal Spectrum">
      <p className="text-sm text-graphite mb-4">
        Silence = alignment. Changes, conflicts, and directives are one
        operation — compare two snapshots. The temporal relationship determines
        the category. Density of annotation tells you how much trouble exists
        before you read a word.
      </p>

      <div className="bg-sheet border border-rule rounded-md overflow-hidden">
        {/* Item header */}
        <div className="px-4 py-3 border-b border-rule flex items-baseline justify-between">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-md font-medium">Door 101</span>
            <span className="text-trace">·</span>
            <span className="text-sm text-graphite">Room 203</span>
          </div>
          <span className="text-xs text-trace font-mono">
            Finish Schedule · DD → CD
          </span>
        </div>

        {/* Property rows */}
        <div className="divide-y divide-rule">
          {/* Aligned — silence */}
          <PropRow label="mark">
            <span className="font-mono">101</span>
          </PropRow>
          <PropRow label="width">
            <span className="font-mono">3&apos;-0&quot;</span>
          </PropRow>
          <PropRow label="height">
            <span className="font-mono">7&apos;-0&quot;</span>
          </PropRow>

          {/* Changed — pencil note */}
          <PropRow label="material" status="changed">
            <div className="flex items-center gap-2">
              <span className="font-mono text-trace line-through">
                hollow metal
              </span>
              <span className="text-pencil-ink">→</span>
              <span className="font-mono text-pencil-ink font-medium">
                wood
              </span>
              <span className="text-xs text-pencil-muted ml-auto">DD → CD</span>
            </div>
          </PropRow>
          <PropRow label="hardware_set" status="changed">
            <div className="flex items-center gap-2">
              <span className="font-mono text-trace line-through">HW-1</span>
              <span className="text-pencil-ink">→</span>
              <span className="font-mono text-pencil-ink font-medium">
                HW-3
              </span>
              <span className="text-xs text-pencil-muted ml-auto">DD → CD</span>
            </div>
          </PropRow>

          {/* Conflicted — redline */}
          <PropRow label="finish" status="conflicted">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-redline-ink w-28">
                  Finish Schedule
                </span>
                <span className="font-mono">stain</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-redline-ink w-28">
                  Spec §08
                </span>
                <span className="font-mono">paint</span>
              </div>
            </div>
          </PropRow>

          {/* Resolved — returns to silence with small stamp */}
          <PropRow label="fire_rating" status="resolved">
            <div className="flex items-center gap-2">
              <span className="font-mono">90 min</span>
              <span className="inline-flex items-center gap-1 text-xs text-stamp-ink">
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                  <path
                    d="M2.5 6l2.5 2.5 4.5-4.5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                resolved
              </span>
            </div>
          </PropRow>

          {/* Directive — decision made, source hasn't caught up */}
          <PropRow label="closer" status="directive">
            <div className="flex items-center gap-2">
              <span className="font-mono text-pencil-ink font-medium">
                LCN 4040
              </span>
              <span className="text-xs text-overlay">
                per Decision #12
              </span>
              <span className="text-xs text-pencil-muted ml-auto">
                Spec §08 pending
              </span>
            </div>
          </PropRow>
        </div>
      </div>
    </Section>
  );
}

function PropRow({
  label,
  status,
  children,
}: {
  label: string;
  status?: "changed" | "conflicted" | "resolved" | "directive";
  children: ReactNode;
}) {
  const bg =
    status === "changed"
      ? "bg-pencil-wash border-l-2 border-l-pencil"
      : status === "conflicted"
        ? "bg-redline-wash border-l-2 border-l-redline"
        : status === "directive"
          ? "bg-pencil-wash border-l-2 border-l-overlay"
          : "";

  return (
    <div className={`px-4 py-2.5 flex items-start gap-4 text-sm ${bg}`}>
      <span className="w-28 shrink-0 text-graphite">{label}</span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}

// ─── Components ──────────────────────────────────────────

function ComponentSection() {
  return (
    <Section title="Components">
      <div className="space-y-8">
        {/* Breadcrumb */}
        <div>
          <div className="text-xs font-mono text-trace uppercase tracking-wide mb-3">
            Breadcrumb
          </div>
          <div className="bg-sheet border border-rule rounded-md px-4 py-2.5 flex items-center gap-1.5 text-sm">
            <BreadcrumbSeg label="Project Alpha" />
            <Chevron />
            <BreadcrumbSeg label="Building A" />
            <Chevron />
            <BreadcrumbSeg label="Floor 2" />
            <Chevron />
            <BreadcrumbSeg label="Room 203" />
            <Chevron />
            <BreadcrumbSeg label="Door 101" current />
          </div>
        </div>

        {/* Scale panel accordion */}
        <div>
          <div className="text-xs font-mono text-trace uppercase tracking-wide mb-3">
            Scale Panel — Accordion
          </div>
          <div className="bg-vellum border border-rule rounded-md w-72 overflow-hidden">
            {/* Expanded group */}
            <div className="border-b border-rule">
              <div className="px-3 py-2 flex items-center gap-2">
                <ChevronDown />
                <span className="text-sm font-medium">Doors</span>
                <span className="text-xs text-trace">(5)</span>
              </div>
              <div className="pb-1">
                <AccItem label="Door 101" badge="2 conflicts" variant="redline" />
                <AccItem label="Door 102" badge="1 change" variant="pencil" />
                <AccItem label="Door 103" />
                <AccItem label="Door 104" />
                <AccItem label="Door 105" />
              </div>
            </div>
            {/* Collapsed groups */}
            <div className="border-b border-rule">
              <div className="px-3 py-2 flex items-center gap-2">
                <ChevronRight />
                <span className="text-sm font-medium">Schedules</span>
                <span className="text-xs text-trace">(2)</span>
              </div>
            </div>
            <div className="border-b border-rule">
              <div className="px-3 py-2 flex items-center gap-2">
                <ChevronRight />
                <span className="text-sm font-medium">Conflicts</span>
                <span className="text-xs text-trace">(2)</span>
                <StatusBadge label="2" variant="redline" />
              </div>
            </div>
            <div>
              <div className="px-3 py-2 flex items-center gap-2">
                <ChevronRight />
                <span className="text-sm font-medium">Changes</span>
                <span className="text-xs text-trace">(3)</span>
                <StatusBadge label="3" variant="pencil" />
              </div>
            </div>
          </div>
        </div>

        {/* Exec summary — Navigable dock (vertical) */}
        <div>
          <div className="text-xs font-mono text-trace uppercase tracking-wide mb-3">
            Exec Summary — Dock
          </div>
          <p className="text-sm text-graphite mb-4">
            Three levels: category → type → instance. Each level is clickable.
            Select a category to see all of that kind. Select a type to filter.
            Select an instance to navigate.
          </p>

          {/* The dock itself — constrained width to simulate sidebar */}
          <div className="bg-sheet border border-rule rounded-md overflow-hidden w-72">
            {/* ── Conflicts category ── */}
            <div className="border-l-2 border-l-redline">
              <div className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-board/30 transition-colors duration-150">
                <div className="flex items-center gap-2">
                  <ChevronDown />
                  <span className="text-sm font-semibold tracking-tight text-redline-ink">
                    Conflicts
                  </span>
                </div>
                <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-redline-wash text-redline-ink">
                  3
                </span>
              </div>
              {/* Type: Doors (expanded) */}
              <div className="ml-5">
                <div className="px-3 py-1.5 flex items-center justify-between cursor-pointer hover:bg-board/30 transition-colors duration-150">
                  <div className="flex items-center gap-1.5">
                    <ChevronDown />
                    <span className="text-xs font-medium text-ink">Doors</span>
                  </div>
                  <span className="text-xs text-redline-muted">2</span>
                </div>
                {/* Instances */}
                <div className="ml-5">
                  <div className="px-3 py-1 cursor-pointer hover:bg-board/30 transition-colors duration-150">
                    <span className="text-xs font-mono text-graphite">
                      Door 101
                    </span>
                    <span className="text-xs text-trace"> · finish</span>
                  </div>
                  <div className="px-3 py-1 cursor-pointer hover:bg-board/30 transition-colors duration-150">
                    <span className="text-xs font-mono text-graphite">
                      Door 103
                    </span>
                    <span className="text-xs text-trace"> · finish</span>
                  </div>
                </div>
              </div>
              {/* Type: Hardware (collapsed) */}
              <div className="ml-5">
                <div className="px-3 py-1.5 flex items-center justify-between cursor-pointer hover:bg-board/30 transition-colors duration-150">
                  <div className="flex items-center gap-1.5">
                    <ChevronRight />
                    <span className="text-xs font-medium text-ink">Hardware</span>
                  </div>
                  <span className="text-xs text-redline-muted">1</span>
                </div>
              </div>
              <div className="h-1" />
            </div>

            <div className="border-t border-rule" />

            {/* ── Changes category ── */}
            <div className="border-l-2 border-l-pencil">
              <div className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-board/30 transition-colors duration-150">
                <div className="flex items-center gap-2">
                  <ChevronDown />
                  <span className="text-sm font-semibold tracking-tight text-pencil-ink">
                    Changes
                  </span>
                </div>
                <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-pencil-wash text-pencil-ink">
                  5
                </span>
              </div>
              {/* Type: Doors (expanded) */}
              <div className="ml-5">
                <div className="px-3 py-1.5 flex items-center justify-between cursor-pointer hover:bg-board/30 transition-colors duration-150">
                  <div className="flex items-center gap-1.5">
                    <ChevronDown />
                    <span className="text-xs font-medium text-ink">Doors</span>
                  </div>
                  <span className="text-xs text-pencil-muted">3</span>
                </div>
                <div className="ml-5">
                  <div className="px-3 py-1 cursor-pointer hover:bg-board/30 transition-colors duration-150">
                    <span className="text-xs font-mono text-graphite">
                      Door 101
                    </span>
                    <span className="text-xs text-trace"> · material</span>
                  </div>
                  <div className="px-3 py-1 cursor-pointer hover:bg-board/30 transition-colors duration-150">
                    <span className="text-xs font-mono text-graphite">
                      Door 102
                    </span>
                    <span className="text-xs text-trace"> · width</span>
                  </div>
                  <div className="px-3 py-1 text-xs text-trace pl-3">
                    + 1 more
                  </div>
                </div>
              </div>
              {/* Type: Hardware (expanded) */}
              <div className="ml-5">
                <div className="px-3 py-1.5 flex items-center justify-between cursor-pointer hover:bg-board/30 transition-colors duration-150">
                  <div className="flex items-center gap-1.5">
                    <ChevronDown />
                    <span className="text-xs font-medium text-ink">Hardware</span>
                  </div>
                  <span className="text-xs text-pencil-muted">2</span>
                </div>
                <div className="ml-5">
                  <div className="px-3 py-1 cursor-pointer hover:bg-board/30 transition-colors duration-150">
                    <span className="text-xs font-mono text-graphite">
                      HW-3
                    </span>
                    <span className="text-xs text-trace"> · closer</span>
                  </div>
                  <div className="px-3 py-1 cursor-pointer hover:bg-board/30 transition-colors duration-150">
                    <span className="text-xs font-mono text-graphite">
                      HW-3
                    </span>
                    <span className="text-xs text-trace"> · threshold</span>
                  </div>
                </div>
              </div>
              <div className="h-1" />
            </div>

            <div className="border-t border-rule" />

            {/* ── Directives category ── */}
            <div className="border-l-2 border-l-overlay">
              <div className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-board/30 transition-colors duration-150">
                <div className="flex items-center gap-2">
                  <ChevronDown />
                  <span className="text-sm font-semibold tracking-tight text-overlay">
                    Directives
                  </span>
                </div>
                <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-pencil-wash text-overlay">
                  2
                </span>
              </div>
              {/* Type: by source — Spec §08 (expanded) */}
              <div className="ml-5">
                <div className="px-3 py-1.5 flex items-center justify-between cursor-pointer hover:bg-board/30 transition-colors duration-150">
                  <div className="flex items-center gap-1.5">
                    <ChevronDown />
                    <span className="text-xs font-medium text-ink">Spec §08</span>
                  </div>
                  <span className="text-xs text-overlay-border">1</span>
                </div>
                <div className="ml-5">
                  <div className="px-3 py-1 cursor-pointer hover:bg-board/30 transition-colors duration-150">
                    <span className="text-xs font-mono text-graphite">
                      Door 101
                    </span>
                    <span className="text-xs text-trace"> · finish</span>
                  </div>
                </div>
              </div>
              {/* Type: Schedule (collapsed) */}
              <div className="ml-5">
                <div className="px-3 py-1.5 flex items-center justify-between cursor-pointer hover:bg-board/30 transition-colors duration-150">
                  <div className="flex items-center gap-1.5">
                    <ChevronRight />
                    <span className="text-xs font-medium text-ink">Schedule</span>
                  </div>
                  <span className="text-xs text-overlay-border">1</span>
                </div>
              </div>
              <div className="h-1" />
            </div>

            <div className="border-t border-rule" />

            {/* ── Resolved — collapsed, quiet ── */}
            <div>
              <div className="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-board/30 transition-colors duration-150">
                <div className="flex items-center gap-2">
                  <ChevronRight />
                  <span className="text-sm font-medium text-graphite">
                    Resolved
                  </span>
                </div>
                <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-stamp-wash text-stamp-ink">
                  4
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Workflow statuses */}
        <div>
          <div className="text-xs font-mono text-trace uppercase tracking-wide mb-3">
            Workflow Status
          </div>
          <div className="flex gap-2">
            <StatusBadge label="needs review" variant="redline" />
            <StatusBadge label="in review" variant="pencil" />
            <StatusBadge label="needs action" variant="redline" />
            <StatusBadge label="accepted" variant="stamp" />
            <StatusBadge label="hold" variant="filed" />
          </div>
        </div>
      </div>
    </Section>
  );
}

function BreadcrumbSeg({
  label,
  current,
}: {
  label: string;
  current?: boolean;
}) {
  return (
    <span
      className={
        current
          ? "font-medium text-ink"
          : "text-graphite hover:text-ink cursor-pointer transition-colors duration-150"
      }
    >
      {label}
    </span>
  );
}

function Chevron() {
  return (
    <svg
      className="w-3.5 h-3.5 text-trace shrink-0"
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

function ChevronRight() {
  return (
    <svg className="w-3 h-3 text-trace shrink-0" viewBox="0 0 12 12" fill="none">
      <path
        d="M4.5 2.5l3.5 3.5-3.5 3.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronDown() {
  return (
    <svg className="w-3 h-3 text-trace shrink-0" viewBox="0 0 12 12" fill="none">
      <path
        d="M2.5 4.5l3.5 3.5 3.5-3.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function AccItem({
  label,
  badge,
  variant,
}: {
  label: string;
  badge?: string;
  variant?: "redline" | "pencil";
}) {
  return (
    <div className="px-3 py-1.5 pl-8 flex items-center gap-2 cursor-pointer hover:bg-board/50 transition-colors duration-150">
      <span className="font-mono text-sm">{label}</span>
      {badge && (
        <span
          className={`text-xs ${
            variant === "redline"
              ? "text-redline-ink"
              : variant === "pencil"
                ? "text-pencil-ink"
                : "text-trace"
          }`}
        >
          {badge}
        </span>
      )}
    </div>
  );
}

function StatusBadge({
  label,
  variant,
}: {
  label: string;
  variant: "redline" | "pencil" | "stamp" | "filed";
}) {
  const classes = {
    redline: "bg-redline-wash text-redline-ink",
    pencil: "bg-pencil-wash text-pencil-ink",
    stamp: "bg-stamp-wash text-stamp-ink",
    filed: "bg-board text-filed",
  }[variant];

  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded ${classes}`}>
      {label}
    </span>
  );
}

// ─── Comparison Mode ─────────────────────────────────────

function ComparisonSection() {
  return (
    <Section title="Comparison Mode">
      <p className="text-sm text-graphite mb-4">
        The 4th dimension. The entire environment transforms — borders, tint,
        column headers. Unmistakable at a glance.
      </p>

      <div className="bg-overlay-wash border-2 border-overlay-border rounded-md overflow-hidden">
        {/* Header */}
        <div className="px-4 py-3 border-b border-overlay-border flex items-baseline justify-between">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-md font-medium">Door 101</span>
            <span className="text-trace">·</span>
            <span className="text-sm text-graphite">Room 203</span>
          </div>
          <span className="text-xs font-medium text-overlay bg-overlay/10 px-2 py-0.5 rounded">
            Comparing: DD ↔ CD
          </span>
        </div>

        {/* Column headers */}
        <div className="grid grid-cols-[120px_1fr_1fr] px-4 py-2 border-b border-overlay-border/40 text-xs font-mono text-graphite uppercase tracking-wide">
          <span>Property</span>
          <span className="px-2">DD</span>
          <span className="px-2">CD</span>
        </div>

        {/* Comparison rows */}
        <div className="divide-y divide-overlay-border/20">
          <CompRow label="mark" dd="101" cd="101" />
          <CompRow label="width" dd="3'-0&quot;" cd="3'-0&quot;" />
          <CompRow label="material" dd="hollow metal" cd="wood" status="changed" />
          <CompRow label="finish" dd="paint" cd="stain ≠ paint" status="conflicted" />
          <CompRow label="fire_rating" dd="—" cd="90 min" status="added" />
        </div>
      </div>
    </Section>
  );
}

function CompRow({
  label,
  dd,
  cd,
  status,
}: {
  label: string;
  dd: string;
  cd: string;
  status?: "changed" | "conflicted" | "added";
}) {
  const cdClass =
    status === "changed"
      ? "bg-pencil-wash/60 text-pencil-ink font-medium"
      : status === "conflicted"
        ? "bg-redline-wash/60 text-redline-ink font-medium"
        : status === "added"
          ? "bg-stamp-wash/60 text-stamp-ink font-medium"
          : "";

  return (
    <div className="grid grid-cols-[120px_1fr_1fr] px-4 py-2.5 text-sm">
      <span className="text-graphite">{label}</span>
      <span className={`font-mono px-2 ${status ? "text-trace" : ""}`}>
        {dd}
      </span>
      <span className={`font-mono px-2 rounded-sm ${cdClass}`}>{cd}</span>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────

export default function DesignReference() {
  return (
    <div className="min-h-screen bg-vellum">
      {/* Header */}
      <header className="bg-sheet border-b border-rule">
        <div className="max-w-5xl mx-auto px-6 py-4">
          <h1 className="text-2xl font-semibold tracking-tight">Cadence</h1>
          <p className="text-sm text-graphite mt-0.5">
            Visual Identity · First Pass
          </p>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-5xl mx-auto px-6 py-10 space-y-14">
        <TypographySection />
        <ColorSection />
        <SurfaceSection />
        <PropertyTableSection />
        <ComponentSection />
        <ComparisonSection />
      </main>
    </div>
  );
}
