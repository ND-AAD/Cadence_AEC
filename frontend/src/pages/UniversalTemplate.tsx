import type { ReactNode } from "react";

// ─── Shared Primitives ──────────────────────────────────

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section>
      <h2 className="text-lg font-semibold tracking-tight mb-1">{title}</h2>
      {subtitle && (
        <p className="text-sm text-graphite mb-6">{subtitle}</p>
      )}
      {!subtitle && <div className="mb-6" />}
      {children}
    </section>
  );
}

// ─── Breadcrumb ─────────────────────────────────────────

function BreadcrumbChevron({ className }: { className?: string }) {
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

function BreadcrumbSegments({
  segments,
  inactive,
}: {
  segments: string[];
  inactive?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5 text-sm">
      {segments.map((seg, i) => {
        const isLast = i === segments.length - 1;
        let style: string;
        if (inactive) {
          style = "text-trace";
        } else if (isLast) {
          style = "font-medium text-ink";
        } else if (seg === "...") {
          style = "text-trace";
        } else {
          style = "text-graphite";
        }
        return (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && (
              <BreadcrumbChevron
                className={inactive ? "text-trace/50" : undefined}
              />
            )}
            <span className={style}>{seg}</span>
          </span>
        );
      })}
    </div>
  );
}

/**
 * Breadcrumb — supports linear paths and Z-axis forks.
 *
 * Linear:  segments only
 * Forked:  `fork` provides the shared stem, active branch, and inactive branch.
 *          The inactive branch drops below with a connector line.
 */
function Breadcrumb({
  segments,
  fork,
}: {
  segments?: string[];
  fork?: {
    stem: string[];
    active: string[];
    inactive: string[];
  };
}) {
  if (segments) {
    return <BreadcrumbSegments segments={segments} />;
  }

  if (fork) {
    return (
      <div className="flex flex-col gap-0">
        {/* Active branch (on top) */}
        <div className="flex items-center gap-1.5">
          <BreadcrumbSegments segments={fork.stem} />
          <BreadcrumbChevron />
          <BreadcrumbSegments segments={fork.active} />
        </div>

        {/* Fork connector + inactive branch (below) */}
        <div className="flex items-center gap-1.5 ml-0">
          {/* Spacer to align under the fork point */}
          <div className="flex items-center gap-1.5 text-sm">
            {fork.stem.map((seg, i) => (
              <span key={i} className="flex items-center gap-1.5">
                {i > 0 && <BreadcrumbChevron className="text-transparent" />}
                <span className="text-transparent">{seg}</span>
              </span>
            ))}
          </div>
          {/* Fork line: ╰ rendered as border */}
          <div className="relative w-3.5 h-4 shrink-0">
            <div className="absolute top-0 left-1/2 w-px h-2 bg-trace/40" />
            <div className="absolute top-2 left-1/2 w-1.5 h-px bg-trace/40" />
          </div>
          <BreadcrumbSegments segments={fork.inactive} inactive />
        </div>
      </div>
    );
  }

  return null;
}

// ─── Row Types ──────────────────────────────────────────

type RowStatus = "changed" | "conflicted" | "resolved";

/**
 * PropertyRow — a static value. Not navigable.
 */
function PropertyRow({
  label,
  status,
  children,
}: {
  label: string;
  status?: RowStatus;
  children: ReactNode;
}) {
  const bg =
    status === "changed"
      ? "bg-pencil-wash border-l-2 border-l-pencil"
      : status === "conflicted"
        ? "bg-redline-wash border-l-2 border-l-redline"
        : "";

  return (
    <div className={`px-4 py-2.5 flex items-start gap-4 text-sm ${bg}`}>
      <span className="w-32 shrink-0 text-graphite">{label}</span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}

/**
 * ConnectionRow — a navigable link to another item.
 * If `inPath` is true, clicking snaps back to that point in the breadcrumb.
 * Otherwise, clicking navigates forward (X-axis).
 */
function ConnectionRow({
  label,
  itemName,
  itemType,
  status,
  inPath,
  badge,
}: {
  label: string;
  itemName: string;
  itemType?: string;
  status?: RowStatus;
  inPath?: boolean;
  badge?: { text: string; variant: "redline" | "pencil" | "stamp" };
}) {
  const bg =
    status === "changed"
      ? "bg-pencil-wash border-l-2 border-l-pencil"
      : status === "conflicted"
        ? "bg-redline-wash border-l-2 border-l-redline"
        : "";

  return (
    <div
      className={`px-4 py-2.5 flex items-start gap-4 text-sm group cursor-pointer transition-colors duration-150 ${bg} hover:bg-board/40`}
    >
      <span className="w-32 shrink-0 text-graphite">{label}</span>
      <div className="flex-1 min-w-0 flex items-center gap-2">
        <span
          className={`font-mono ${
            inPath ? "text-trace" : "text-ink"
          }`}
        >
          {itemName}
        </span>

        {itemType && (
          <span className="text-xs text-trace">{itemType}</span>
        )}

        {badge && (
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded ${
              badge.variant === "redline"
                ? "bg-redline-wash text-redline-ink"
                : badge.variant === "pencil"
                  ? "bg-pencil-wash text-pencil-ink"
                  : "bg-stamp-wash text-stamp-ink"
            }`}
          >
            {badge.text}
          </span>
        )}

        {/* Back arrow for in-path items, forward arrow for new items */}
        <svg
          className={`w-3.5 h-3.5 ml-auto shrink-0 transition-opacity duration-150 ${
            inPath
              ? "text-trace opacity-0 group-hover:opacity-100"
              : "text-trace opacity-0 group-hover:opacity-100"
          }`}
          viewBox="0 0 14 14"
          fill="none"
        >
          <path
            d={inPath ? "M9 3l-4 4 4 4" : "M5 3l4 4-4 4"}
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </div>
  );
}

/**
 * SectionDivider — separates property rows from connection rows
 * within the same table. Light, not heavy.
 */
function RowGroupLabel({ label }: { label: string }) {
  return (
    <div className="px-4 py-1.5 text-xs font-mono text-trace uppercase tracking-wide bg-vellum/50">
      {label}
    </div>
  );
}

// ─── Exec Summary ───────────────────────────────────────

function ExecSummary({
  items,
}: {
  items: { text: string; variant: "redline" | "pencil" | "stamp" | "filed" }[];
}) {
  return (
    <div className="px-4 py-2.5 border-b border-rule flex items-center gap-2 flex-wrap">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span className="text-trace">·</span>}
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded ${
              item.variant === "redline"
                ? "bg-redline-wash text-redline-ink"
                : item.variant === "pencil"
                  ? "bg-pencil-wash text-pencil-ink"
                  : item.variant === "stamp"
                    ? "bg-stamp-wash text-stamp-ink"
                    : "bg-board text-filed"
            }`}
          >
            {item.text}
          </span>
        </span>
      ))}
    </div>
  );
}

// ─── Sibling Strip (Z-axis awareness) ───────────────────

type Sibling = {
  name: string;
  active?: boolean;
  inPath?: boolean;
  badge?: { text: string; variant: "redline" | "pencil" };
};

function SiblingStrip({
  parent,
  siblings,
}: {
  parent: string;
  siblings: Sibling[];
}) {
  return (
    <div className="px-4 py-1.5 border-b border-rule bg-vellum/60 flex items-center gap-1 text-xs overflow-x-auto">
      <span className="text-trace shrink-0">via {parent}:</span>
      {siblings.map((sib, i) => (
        <span key={i} className="flex items-center gap-1 shrink-0">
          {i > 0 && <span className="text-rule-emphasis">·</span>}
          <span
            className={`px-1.5 py-0.5 rounded-sm transition-colors duration-150 ${
              sib.active
                ? "bg-board font-medium text-ink"
                : sib.inPath
                  ? "text-trace hover:text-graphite hover:bg-board/30 cursor-pointer"
                  : "text-graphite hover:text-ink hover:bg-board/50 cursor-pointer"
            }`}
          >
            {sib.name}
          </span>
          {sib.badge && (
            <span
              className={`text-xs px-1 rounded-sm ${
                sib.badge.variant === "redline"
                  ? "text-redline-muted"
                  : "text-pencil-muted"
              }`}
            >
              {sib.badge.text}
            </span>
          )}
        </span>
      ))}
    </div>
  );
}

// ─── Item Card (Universal Template) ─────────────────────

function ItemCard({
  breadcrumb,
  breadcrumbFork,
  name,
  context,
  milestone,
  exec,
  siblings,
  children,
}: {
  breadcrumb?: string[];
  breadcrumbFork?: { stem: string[]; active: string[]; inactive: string[] };
  name: string;
  context?: string;
  milestone?: string;
  exec?: { text: string; variant: "redline" | "pencil" | "stamp" | "filed" }[];
  siblings?: { parent: string; siblings: Sibling[] };
  children: ReactNode;
}) {
  return (
    <div className="bg-sheet border border-rule rounded-md overflow-hidden">
      {/* Breadcrumb bar */}
      <div className="px-4 py-2 border-b border-rule bg-vellum">
        <Breadcrumb segments={breadcrumb} fork={breadcrumbFork} />
      </div>

      {/* Sibling strip — Z-axis awareness */}
      {siblings && (
        <SiblingStrip parent={siblings.parent} siblings={siblings.siblings} />
      )}

      {/* Item header */}
      <div className="px-4 py-3 border-b border-rule flex items-baseline justify-between">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-md font-medium">{name}</span>
          {context && (
            <>
              <span className="text-trace">·</span>
              <span className="text-sm text-graphite">{context}</span>
            </>
          )}
        </div>
        {milestone && (
          <span className="text-xs text-trace font-mono">{milestone}</span>
        )}
      </div>

      {/* Exec summary */}
      {exec && exec.length > 0 && <ExecSummary items={exec} />}

      {/* Unified rows: properties + connections */}
      <div className="divide-y divide-rule">{children}</div>
    </div>
  );
}

// ─── Junction 1: Room 203 ───────────────────────────────

function Junction1() {
  return (
    <Section
      title="Junction 1 — Room 203"
      subtitle="A container. Few properties, many connections. The connections ARE the story."
    >
      <ItemCard
        breadcrumb={["Project Alpha", "Building A", "Floor 2", "Room 203"]}
        name="Room 203"
        context="Conference Room"
        milestone="CD"
        exec={[
          { text: "2 conflicts", variant: "redline" },
          { text: "3 changes", variant: "pencil" },
          { text: "1 resolved", variant: "stamp" },
        ]}
      >
        <RowGroupLabel label="Properties" />
        <PropertyRow label="room_number">
          <span className="font-mono">203</span>
        </PropertyRow>
        <PropertyRow label="name">
          <span className="font-mono">Conference Room</span>
        </PropertyRow>
        <PropertyRow label="area" status="changed">
          <div className="flex items-center gap-2">
            <span className="font-mono text-trace line-through">425 sf</span>
            <span className="text-pencil-ink">→</span>
            <span className="font-mono text-pencil-ink font-medium">
              450 sf
            </span>
            <span className="text-xs text-pencil-muted ml-auto">DD → CD</span>
          </div>
        </PropertyRow>
        <PropertyRow label="floor_finish">
          <span className="font-mono">carpet tile</span>
        </PropertyRow>

        <RowGroupLabel label="Doors" />
        <ConnectionRow
          label="door"
          itemName="Door 101"
          badge={{ text: "2 conflicts", variant: "redline" }}
        />
        <ConnectionRow
          label="door"
          itemName="Door 102"
          badge={{ text: "1 change", variant: "pencil" }}
        />
        <ConnectionRow label="door" itemName="Door 103" />
        <ConnectionRow label="door" itemName="Door 104" />
        <ConnectionRow label="door" itemName="Door 105" />

        <RowGroupLabel label="Sources" />
        <ConnectionRow label="source" itemName="Finish Schedule" itemType="schedule" />
        <ConnectionRow label="source" itemName="Spec §08" itemType="schedule" />
      </ItemCard>
    </Section>
  );
}

// ─── Junction 2: Door 101 (from Room 203) ───────────────

function Junction2() {
  return (
    <Section
      title="Junction 2 — Door 101"
      subtitle="Navigated from Room 203. Many properties, a few connections. Room 203 is in the path — visible but not navigable."
    >
      <ItemCard
        breadcrumb={["...", "Floor 2", "Room 203", "Door 101"]}
        name="Door 101"
        context="Room 203"
        milestone="Finish Schedule · DD → CD"
        siblings={{
          parent: "Room 203",
          siblings: [
            { name: "Door 101", active: true },
            { name: "Door 102", badge: { text: "1", variant: "pencil" } },
            { name: "Door 103" },
            { name: "Door 104" },
            { name: "Door 105" },
          ],
        }}
        exec={[
          { text: "1 conflict", variant: "redline" },
          { text: "2 changes", variant: "pencil" },
        ]}
      >
        <RowGroupLabel label="Properties" />
        <PropertyRow label="mark">
          <span className="font-mono">101</span>
        </PropertyRow>
        <PropertyRow label="width">
          <span className="font-mono">3&apos;-0&quot;</span>
        </PropertyRow>
        <PropertyRow label="height">
          <span className="font-mono">7&apos;-0&quot;</span>
        </PropertyRow>
        <PropertyRow label="material" status="changed">
          <div className="flex items-center gap-2">
            <span className="font-mono text-trace line-through">
              hollow metal
            </span>
            <span className="text-pencil-ink">→</span>
            <span className="font-mono text-pencil-ink font-medium">wood</span>
            <span className="text-xs text-pencil-muted ml-auto">DD → CD</span>
          </div>
        </PropertyRow>
        <PropertyRow label="finish" status="conflicted">
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
        </PropertyRow>
        <PropertyRow label="fire_rating">
          <span className="font-mono">90 min</span>
        </PropertyRow>

        <RowGroupLabel label="Connections" />
        <ConnectionRow
          label="room"
          itemName="Room 203"
          inPath
        />
        <ConnectionRow
          label="hardware"
          itemName="HW-3"
          status="changed"
          badge={{ text: "new at CD", variant: "pencil" }}
        />
        <ConnectionRow
          label="source"
          itemName="Finish Schedule"
          itemType="schedule"
        />
        <ConnectionRow
          label="source"
          itemName="Spec §08"
          itemType="schedule"
        />
      </ItemCard>
    </Section>
  );
}

// ─── Junction 3: HW-3 (from Door 101, via Room 203) ────

function Junction3() {
  return (
    <Section
      title="Junction 3 — HW-3"
      subtitle="Navigated through Room 203 → Door 101 → HW-3. Both are in the path. But Door 105 and Door 108 are reachable — forward motion through a shared junction."
    >
      <ItemCard
        breadcrumb={["...", "Room 203", "Door 101", "HW-3"]}
        name="HW-3"
        context="Hardware Set"
        milestone="CD"
        siblings={{
          parent: "Door 101",
          siblings: [
            { name: "Room 203", inPath: true },
            { name: "HW-3", active: true },
            { name: "Finish Schedule" },
            { name: "Spec §08", badge: { text: "1", variant: "redline" } },
          ],
        }}
        exec={[
          { text: "1 change", variant: "pencil" },
        ]}
      >
        <RowGroupLabel label="Properties" />
        <PropertyRow label="set_id">
          <span className="font-mono">HW-3</span>
        </PropertyRow>
        <PropertyRow label="lockset">
          <span className="font-mono">cylindrical</span>
        </PropertyRow>
        <PropertyRow label="closer" status="changed">
          <div className="flex items-center gap-2">
            <span className="font-mono text-trace line-through">
              LCN 4011
            </span>
            <span className="text-pencil-ink">→</span>
            <span className="font-mono text-pencil-ink font-medium">
              LCN 4040
            </span>
            <span className="text-xs text-pencil-muted ml-auto">DD → CD</span>
          </div>
        </PropertyRow>
        <PropertyRow label="hinges">
          <span className="font-mono">3× 4.5&quot; ball bearing</span>
        </PropertyRow>
        <PropertyRow label="threshold">
          <span className="font-mono">none</span>
        </PropertyRow>

        <RowGroupLabel label="Doors (using this set)" />
        <ConnectionRow
          label="door"
          itemName="Door 101"
          inPath
        />
        <ConnectionRow
          label="door"
          itemName="Door 105"
        />
        <ConnectionRow
          label="door"
          itemName="Door 108"
        />
        <ConnectionRow
          label="door"
          itemName="Door 112"
        />

        <RowGroupLabel label="Sources" />
        <ConnectionRow
          label="source"
          itemName="Hardware Schedule"
          itemType="schedule"
        />
      </ItemCard>
    </Section>
  );
}

// ─── Junction 4: Z-axis — Spec §08 (lateral from HW-3) ──

function Junction4() {
  return (
    <Section
      title="Junction 4 — Z-axis: Spec §08"
      subtitle="A lateral jump. You're at HW-3 and decide to jump to Spec §08 instead of going forward. Both are siblings — connected to Door 101. The breadcrumb forks: HW-3 drops below and fades, Spec §08 appears on top."
    >
      <ItemCard
        breadcrumbFork={{
          stem: ["...", "Room 203", "Door 101"],
          active: ["Spec §08"],
          inactive: ["HW-3"],
        }}
        name="Spec §08"
        context="Division 08 — Openings"
        milestone="CD"
        siblings={{
          parent: "Door 101",
          siblings: [
            { name: "Room 203", inPath: true },
            { name: "HW-3" },
            { name: "Finish Schedule" },
            { name: "Spec §08", active: true },
          ],
        }}
        exec={[
          { text: "3 conflicts", variant: "redline" },
          { text: "5 changes", variant: "pencil" },
        ]}
      >
        <RowGroupLabel label="Properties" />
        <PropertyRow label="title">
          <span className="font-mono">Division 08 — Openings</span>
        </PropertyRow>
        <PropertyRow label="revision">
          <span className="font-mono">Rev C</span>
        </PropertyRow>
        <PropertyRow label="date" status="changed">
          <div className="flex items-center gap-2">
            <span className="font-mono text-trace line-through">
              2024-03-15
            </span>
            <span className="text-pencil-ink">→</span>
            <span className="font-mono text-pencil-ink font-medium">
              2024-06-01
            </span>
            <span className="text-xs text-pencil-muted ml-auto">DD → CD</span>
          </div>
        </PropertyRow>
        <PropertyRow label="issued_by">
          <span className="font-mono">Architect of Record</span>
        </PropertyRow>

        <RowGroupLabel label="Items described" />
        <ConnectionRow
          label="door"
          itemName="Door 101"
          inPath
          badge={{ text: "1 conflict", variant: "redline" }}
        />
        <ConnectionRow
          label="door"
          itemName="Door 102"
        />
        <ConnectionRow
          label="door"
          itemName="Door 103"
          badge={{ text: "1 conflict", variant: "redline" }}
        />
        <ConnectionRow
          label="door"
          itemName="Door 105"
        />
        <ConnectionRow
          label="door"
          itemName="Door 110"
          badge={{ text: "2 changes", variant: "pencil" }}
        />

        <RowGroupLabel label="Cross-references" />
        <ConnectionRow
          label="schedule"
          itemName="Finish Schedule"
          itemType="schedule"
          badge={{ text: "1 conflict", variant: "redline" }}
        />
      </ItemCard>
    </Section>
  );
}

// ─── Junction 5: Door 105 (forward from Spec §08, fork persists) ─

function Junction5() {
  return (
    <Section
      title="Junction 5 — Door 105"
      subtitle="Forward from Spec §08 to Door 105. The dead branch (HW-3) persists below — you can still see where you were. Door 101 and Spec §08 are in the active path."
    >
      <ItemCard
        breadcrumbFork={{
          stem: ["...", "Room 203", "Door 101"],
          active: ["Spec §08", "Door 105"],
          inactive: ["HW-3"],
        }}
        name="Door 105"
        context="Room 208"
        milestone="CD"
        siblings={{
          parent: "Spec §08",
          siblings: [
            { name: "Door 101", inPath: true },
            { name: "Door 102" },
            { name: "Door 103", badge: { text: "1", variant: "redline" } },
            { name: "Door 105", active: true },
            { name: "Door 110", badge: { text: "2", variant: "pencil" } },
          ],
        }}
      >
        <RowGroupLabel label="Properties" />
        <PropertyRow label="mark">
          <span className="font-mono">105</span>
        </PropertyRow>
        <PropertyRow label="width">
          <span className="font-mono">3&apos;-0&quot;</span>
        </PropertyRow>
        <PropertyRow label="height">
          <span className="font-mono">7&apos;-0&quot;</span>
        </PropertyRow>
        <PropertyRow label="material">
          <span className="font-mono">wood</span>
        </PropertyRow>
        <PropertyRow label="finish">
          <span className="font-mono">paint</span>
        </PropertyRow>
        <PropertyRow label="fire_rating">
          <span className="font-mono">—</span>
        </PropertyRow>

        <RowGroupLabel label="Connections" />
        <ConnectionRow
          label="room"
          itemName="Room 208"
        />
        <ConnectionRow
          label="hardware"
          itemName="HW-3"
          itemType="on dead branch"
        />
        <ConnectionRow
          label="source"
          itemName="Spec §08"
          itemType="schedule"
          inPath
        />
        <ConnectionRow
          label="source"
          itemName="Finish Schedule"
          itemType="schedule"
        />
      </ItemCard>
    </Section>
  );
}

// ─── Junction 6: HW-3 (branch absorption) ───────────────

function Junction6() {
  return (
    <Section
      title="Junction 6 — HW-3 (branch absorbed)"
      subtitle="Navigate from Door 105 to HW-3. HW-3 was on the dead branch — so the dead branch disappears and HW-3 appends to the active path. The fork resolves into a straight line."
    >
      <ItemCard
        breadcrumb={["...", "Door 101", "Spec §08", "Door 105", "HW-3"]}
        name="HW-3"
        context="Hardware Set"
        milestone="CD"
        siblings={{
          parent: "Door 105",
          siblings: [
            { name: "Room 208" },
            { name: "HW-3", active: true },
            { name: "Spec §08", inPath: true },
            { name: "Finish Schedule" },
          ],
        }}
        exec={[
          { text: "1 change", variant: "pencil" },
        ]}
      >
        <RowGroupLabel label="Properties" />
        <PropertyRow label="set_id">
          <span className="font-mono">HW-3</span>
        </PropertyRow>
        <PropertyRow label="lockset">
          <span className="font-mono">cylindrical</span>
        </PropertyRow>
        <PropertyRow label="closer" status="changed">
          <div className="flex items-center gap-2">
            <span className="font-mono text-trace line-through">
              LCN 4011
            </span>
            <span className="text-pencil-ink">→</span>
            <span className="font-mono text-pencil-ink font-medium">
              LCN 4040
            </span>
            <span className="text-xs text-pencil-muted ml-auto">DD → CD</span>
          </div>
        </PropertyRow>
        <PropertyRow label="hinges">
          <span className="font-mono">3× 4.5&quot; ball bearing</span>
        </PropertyRow>
        <PropertyRow label="threshold">
          <span className="font-mono">none</span>
        </PropertyRow>

        <RowGroupLabel label="Doors (using this set)" />
        <ConnectionRow
          label="door"
          itemName="Door 101"
          inPath
        />
        <ConnectionRow
          label="door"
          itemName="Door 105"
          inPath
        />
        <ConnectionRow
          label="door"
          itemName="Door 108"
        />
        <ConnectionRow
          label="door"
          itemName="Door 112"
        />

        <RowGroupLabel label="Sources" />
        <ConnectionRow
          label="source"
          itemName="Hardware Schedule"
          itemType="schedule"
        />
      </ItemCard>
    </Section>
  );
}

// ─── Main Page ──────────────────────────────────────────

export default function UniversalTemplate() {
  return (
    <div className="min-h-screen bg-vellum">
      <header className="bg-sheet border-b border-rule">
        <div className="max-w-5xl mx-auto px-6 py-4">
          <h1 className="text-2xl font-semibold tracking-tight">
            Universal Template
          </h1>
          <p className="text-sm text-graphite mt-0.5">
            One template. Every scale. Properties and connections share the same
            language.
          </p>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-14">
        {/* Narrative */}
        <div className="bg-sheet border border-rule rounded-md p-6 space-y-3 text-sm text-graphite">
          <p>
            <strong className="text-ink">X-axis (forward):</strong>{" "}
            Room 203 → Door 101 → HW-3. Each step extends the breadcrumb
            linearly. Even through diamonds, forward always feels like forward.
          </p>
          <p>
            <strong className="text-ink">Z-axis (lateral):</strong>{" "}
            At HW-3, jump to Spec §08 — both are siblings connected to
            Door 101. The breadcrumb forks: HW-3 drops below and fades,
            Spec §08 appears on top. This is the only time the breadcrumb has
            vertical dimension.
          </p>
          <p>
            <strong className="text-ink">Fork persists:</strong>{" "}
            Continue forward from Spec §08 to Door 105. The dead branch
            (HW-3) stays visible below — a record of the path not taken.
          </p>
          <p>
            <strong className="text-ink">Branch absorption:</strong>{" "}
            Navigate from Door 105 to HW-3. Since HW-3 was on the dead branch,
            the branch disappears and HW-3 appends to the live path. The fork
            resolves into a straight line.
          </p>
          <p>
            <strong className="text-ink">Sibling strip:</strong>{" "}
            Below the breadcrumb, a minimal strip shows the Z-axis options —
            other items connected to the parent you arrived from. The active
            item is highlighted. Clicking a sibling triggers a Z-axis jump.
            The strip answers: &ldquo;what else is here?&rdquo; without
            competing with the content.
          </p>
          <p>
            <strong className="text-ink">Snap-back:</strong>{" "}
            In-path items are always clickable — in the sibling strip, in the
            connection rows, in the breadcrumb. Clicking one snaps you back to
            that point, trimming everything after it. Back-arrow (←) on hover
            instead of forward-arrow (→). No loop — you&apos;re retracing,
            not extending.
          </p>
        </div>

        <Junction1 />
        <Junction2 />
        <Junction3 />
        <Junction4 />
        <Junction5 />
        <Junction6 />
      </main>
    </div>
  );
}
