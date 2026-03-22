# Cadence Design System

> Construction data reconciliation. Paper-and-ink metaphor.
> Silence = alignment — only disagreement gets visual treatment.

## Direction

**Domain:** Architectural drawing sets, redlining, light tables, document reconciliation.

**Signature:** Silence is the primary design material. A clean view means sources agree. The density of visual annotation tells you how much trouble exists before you read a word.

**Depth strategy:** Borders only. No shadows except floating elements (dropdowns, popovers). Surface hierarchy creates layering through color, not elevation.

**The Temporal Spectrum:** Changes, conflicts, and directives are one operation — compare two snapshots. The temporal relationship determines the category:
1. **Silence** — aligned properties. Paper-and-ink, no decoration.
2. **Pencil** — changes (past → present). Amber wash + amber left border. A source disagrees with its own past.
3. **Redline** — conflicts (present ↔ present). Red wash + red left border. Two sources disagree with each other now.
4. **Directive** — obligations (present → future). Amber wash + blue left border. A decision made that a source doesn't yet reflect. Lives in the pencil family (temporal) but the blue border signals the time dimension.
5. **Stamp** — resolved. Returns to silence with a small checkmark. The disagreement is settled.

Disagreements flow between categories. A conflict is resolved → the decision creates a directive on every source that doesn't yet reflect the chosen value. A directive is fulfilled → the source updates, creating a change. A change is imported → it may introduce a new conflict. The lifecycle is a cycle: detect → resolve → propagate → confirm → detect.

**Fourth dimension:** Comparison mode transforms the entire environment (blue wash, heavier borders, column layout). It's a persistent lens, not a modal — it stays active through navigation.

## Visibility Framework — Present / Adjacent / Silent

The architecture says everything is an item in a flat graph. But what the *user* sees depends on their current perspective — what context they're standing at, what comparisons are active. This framework governs how information renders.

### Three proximity states

**Present** — your perspective affords a direct view. The item, disagreement, or annotation lives at your exact context. It renders **inline**, fully expanded, as part of the content. You don't click to reveal it; it IS the display.

- Conflict at your current context → **perspective-dependent**: your source's value shown inline with redline left border + filled red pip. Expanding the row reveals the other source's name (red string, clickable Z-axis shift) and their value. Only the conflict item view (pip click → page turn) shows both sources side by side in the comparison grid. The main row tells you YOUR value and that a story exists; the expansion tells you what the story is.
- Change visible in comparison mode → both columns show values, left border carries the spectrum color. The change is present because comparison made both time contexts visible.
- Directive targeting your current source → inline with blue border + pencil wash, obligation text visible.

**Adjacent** — shares some context but not fully aligned. Something exists nearby — at another time, in another source's view — that exerts pressure on the current perspective. It renders as a **membrane indicator** (pip): a small colored dot on the right edge of the property row. Hovering reveals a quick detail line. Clicking navigates to the workflow item.

- Change from another time context (single-context view) → amber pip. The change happened at DD but you're looking at CD. You can't see both values without entering comparison mode, but you know something shifted.
- Conflict at another context → red pip. The conflict exists but isn't at your current vantage point.
- Directive from another source → blue pip. An obligation exists but isn't addressed to your current source.

**Silent** — aligned. Sources agree, time contexts match, no pressure. Nothing renders. The value stands on its own, clean ink on paper. Silence is the primary design material.

### Navigation from proximity

Present items are already visible — their inline display contains navigable elements (source names as red strings, conflict annotations as cross-references). You're already looking at the thing; the question is where to go next.

Adjacent items are navigable through their pip. Click the pip → navigate to the workflow item (conflict, change, directive) via page turn. The workflow item's own template shows its full story: sources, values, resolution, connections.

Property names are always navigable regardless of proximity. Click any property name → cross-instance view showing all items with that property, grouped by value. "fire rating" → every door and wall that's fire rated. This axis is spatial (content), not temporal (workflow). There are no dead ends.

### Cairn — human voice in a data-driven system

Conflicts, changes, and directives are all system-detected — they emerge from snapshot comparison. The cairn is the other half: where a human (or eventually an LLM) injects their own voice into the story. A note about a door's width. Meeting minutes that formalize a change. A site photo documenting field conditions. An RFI tied to a property. These are all the same gesture — someone planting a marker in the graph that says "I was here, and this matters."

Cairns exist in a separate visual register from the disagreement system. They serve two purposes:

1. **Human-authored notes** — no lifecycle endpoint, they persist. Someone thought this was worth documenting.
2. **Resolved story markers** — when a conflict is resolved but a directive is still pending, the pip disappears (pips are active workflow items only) and a cairn takes its place. The cairn says "there's a story here but it doesn't need action." When the directive is fulfilled, the cairn drops. Full silence.

In both cases, cairns should never demand attention the way a conflict does.

**Metaphor: a cairn** — a trail marker left by someone who passed through. Quiet, persistent, deliberate. Not a notification. Not a pressure signal. A record that someone thought this spot was worth marking.

**Rendering:** A triangle icon (16px container, 10px triangle), larger than a pip (7px) but still quiet. Uses `graphite` or `trace` — the same register as metadata, not the disagreement color families. Three states:

- **Present** (filled △) — cairn at your exact context. Solid fill in `trace`, hover to `graphite`.
- **Adjacent** (hollow △) — cairn nearby but not at your context. Stroke only, no fill.
- **Active** (filled ▽) — selected. Triangle inverts (points down), row expands below to show the cairn's content: context, date, text, author. Same color as present — geometry change + animation is sufficient feedback. The inversion is the affordance — pointing down toward the expanded content.

Cairns and pips share the indicator lane on the right edge of the property row. Each icon occupies a fixed-width cell (14px); icons center within their cell. This creates equal center-to-center distance between all adjacent icons regardless of size — the rhythm of centers stays even while edge gaps absorb the size difference naturally. The 28px grid column accommodates 2 indicators (common case); 3+ overflow leftward via `overflow: visible` and `flex-direction: row-reverse`.

**Ordering** (right to left, highest priority first):
1. Cairn (always position 1 if present — the datum)
2. Present pips (exact context match): directive → conflict → change
3. Adjacent pips (nearby, not aligned): directive → conflict → change

**Filled / hollow** — one rule for the entire lane. Filled = present (at your context). Hollow = adjacent (nearby). Applies to both pips and cairns. A filled red pip means "active conflict here." A hollow red pip means "active conflict nearby." A filled cairn means "note or resolved story here." A hollow cairn means "note or resolved story nearby."

**Pips are active workflow items only.** No ghost or faded state. When a workflow item resolves, its pip disappears entirely. Acknowledged changes go directly to silence. Resolved conflicts with pending directives get a cairn (not a faded pip). When the directive is fulfilled, the cairn drops too. Full silence = lifecycle complete.

**Directive pips scoped:** When a conflict is resolved on a property and spawns directives, those directives don't add pips to that property's main row — they appear as sub-rows inside the expansion. Directives targeting a different property follow normal pip rules (present inline or adjacent hollow pip).

**Pip position stability:** When comparison mode changes a pip from adjacent (hollow) to present (filled), the pip stays in its current position in the lane. No reordering during mode transitions.

**Pip size:** 7px dot. At this size, the filled vs. hollow distinction reads clearly (1.5px stroke leaves a ~4px interior), and the pip remains clearly subordinate to the 16px cairn (10px triangle) — preserving the visual hierarchy between human voice and system-detected events.

**Proximity rules:** Cairns follow the same present/adjacent/silent framework but with different thresholds. When you're "close enough" to a cairn's context (same item at the same or adjacent milestone), the indicator is always visible. Cairns don't hide or expire — someone felt this was important enough to document, and that intent persists.

**Accessibility from afar:** Cairns are items in the graph. They have connections (to the item, to the milestone, to the source). They appear in the exec summary dock, rolled up like any other item category. You can stumble across a cairn while navigating, but you can also search for them, see them in rollup counts, and navigate directly to them from the exec summary. The local icon is the near indicator; the graph is the global access path.

**Scope:** Notes are the MVP cairn type. Meeting minutes, site photos, RFIs, and other human-authored artifacts are the same pattern — different content, same architecture, same visual register. Out of scope for MVP but the design accommodates them without new machinery.

## Tokens

All tokens are defined in `frontend/tailwind.config.js`. Reference implementation at `frontend/src/pages/DesignReference.tsx`.

### Surfaces (paper grades)

| Token    | Hex       | Use                              |
|----------|-----------|----------------------------------|
| sheet    | `#FAF9F6` | Content areas, story panel       |
| vellum   | `#F0EFEC` | Chrome, sidebars, page bg        |
| board    | `#E7E5E2` | Nested elements, hover states    |

### Text (ink on paper)

| Token    | Hex       | Use                              |
|----------|-----------|----------------------------------|
| ink      | `#1C1B18` | Primary text, headings           |
| graphite | `#57554F` | Secondary text, labels           |
| trace    | `#9D9B95` | Tertiary, metadata, mono labels  |

### Borders (architectural rules)

| Token          | Hex       | Use                          |
|----------------|-----------|------------------------------|
| rule           | `#DFDDD9` | Default separators           |
| rule-emphasis  | `#CECCC7` | Strong separators, sections  |

### Redline — Conflicts (Wada vermillion C9 M90 Y100 K0)

| Token         | Hex       | Use                              |
|---------------|-----------|----------------------------------|
| redline       | `#E81A00` | Left border accent               |
| redline-muted | `#EE6A53` | Secondary indicators, stale (non-chosen) values post-resolution |
| redline-wash  | `#FFF0EB` | Row/cell background              |
| redline-ink   | `#A61400` | Text on wash backgrounds         |

### Pencil — Changes (Wada amber C2 M42 Y74 K0)

| Token         | Hex       | Use                              |
|---------------|-----------|----------------------------------|
| pencil        | `#FA9442` | Left border accent               |
| pencil-muted  | `#FBB978` | Secondary change indicators      |
| pencil-wash   | `#FFF5EA` | Row/cell background              |
| pencil-ink    | `#B06218` | Text on wash backgrounds         |

### Stamp — Resolved

| Token      | Hex       | Use                              |
|------------|-----------|----------------------------------|
| stamp      | `#3D7A4F` | Checkmark, resolved indicators   |
| stamp-wash | `#F0F7F2` | Resolved row background          |
| stamp-ink  | `#2D5E3B` | Text on wash backgrounds         |

### Hold

| Token      | Hex       | Use                              |
|------------|-----------|----------------------------------|
| filed      | `#7D7A75` | Hold status, filed-away items    |
| filed-wash | `#F5F4F3` | Held row background              |

### Overlay — Comparison (Klein blue departure)

| Token          | Hex       | Use                              |
|----------------|-----------|----------------------------------|
| overlay        | `#002FA7` | Comparison indicators, directive border |
| overlay-wash   | `#EFF2FB` | Environment tint in compare mode       |
| overlay-border | `#6A7EB5` | Borders in comparison mode, muted counts |

Blue is fundamentally different from the other accent colors. Redline, pencil, and stamp have "tooth" — they feel like pigment on a medium. Overlay blue has "depth" — it's a portal into another dimension (time). This contrast is intentional. Directives use overlay blue for their left border because they are temporal obligations — a conflict projected through time. The amber wash (pencil family) signals "temporal disagreement," the blue border signals "the time dimension."

## Typography

**Families:** Geist Sans (variable, 100–900) + Geist Mono (variable, 100–900).
Font files: `frontend/public/fonts/Geist-Variable.woff2`, `GeistMono-Variable.woff2`.

**Scale (dense, appropriate for data-heavy construction tools):**

| Token | Size   | Line height | Use                              |
|-------|--------|-------------|----------------------------------|
| xs    | 11px   | 16px        | Labels, metadata, mono captions  |
| sm    | 12px   | 18px        | Secondary info, timestamps       |
| base  | 13px   | 20px        | Body text, notes                 |
| md    | 14px   | 22px        | Descriptions, summaries          |
| lg    | 16px   | 24px        | Section headings, item names     |
| xl    | 18px   | 26px        | Scale headings                   |
| 2xl   | 22px   | 28px        | Page titles, project name        |

**Weights:** `font-semibold tracking-tight` for headings. `font-medium` for emphasis. Regular for body. Mono for data values (marks, dimensions, properties).

## Radii

| Token   | Size | Use                           |
|---------|------|-------------------------------|
| sm      | 2px  | Inline badges, small pills    |
| DEFAULT | 3px  | General elements              |
| md      | 4px  | Cards, panels                 |
| lg      | 6px  | Large containers              |

## Shadows

Only `shadow-float` for floating elements: `0 2px 8px rgba(28, 27, 24, 0.08), 0 1px 2px rgba(28, 27, 24, 0.04)`.

## Universal Template

One template for every item at every scale. Reference implementation at `frontend/src/pages/UniversalTemplate.tsx`.

### Anatomy

```
┌─ Breadcrumb bar (bg-vellum) ─────────────────────────────┐
├─ Sibling strip (bg-vellum/60, text-xs) ──────────────────┤
├─ Item header (name · context, milestone right-aligned) ──┤
├─ Exec summary (navigable dock, see below) ───────────────┤
├─ Row group label: "Properties" ──────────────────────────┤
│  PropertyRow — present: inline disagreement display      │
│  PropertyRow — adjacent: pip, hover detail               │
│  PropertyRow — silent: value only, no decoration         │
│  PropertyRow — cairn icon if note at/near this context   │
├─ Row group label: "Connections" ─────────────────────────┤
│  ConnectionRow — navigable links, forward arrow on hover │
│  ConnectionRow (inPath) — snap-back, back arrow on hover │
└──────────────────────────────────────────────────────────┘
```

Properties and connections share the same row language. Both get temporal spectrum treatment. Properties have two navigation axes: property name → cross-instance view, pip → workflow item. Connections are navigable via click (hover state + arrow).

**Click targets:** Property name (120px), row body (1fr, expand), pip (14px × 34px cell). 12px grid gap between value and indicator columns prevents misclicks. Keyboard: Tab through interactive elements, Enter/Space activates, arrows between indicators. Touch targets (44px min) deferred to responsive design.

### There are no "children" — only connections

The architecture is generic: everything is an item, connections define relationships. The template doesn't distinguish parent/child — it shows connections grouped by type. Some happen to be containment (room → door), some are shared references (hardware set → multiple doors), some are sources (schedule → items).

### Property items are just items

Property definitions (`door/fire_rating`, `door/finish`) are first-class items in the graph — see `Cadence_Property_Items_Supplemental_Spec_v2.md`. The UX gives them no special treatment. The universal template renders them like everything else. When viewing `door/fire_rating`:

- **Header:** "Fire Rating" (label from PropertyDef), parent type as context
- **Breadcrumb:** `... › Door 101 › Fire Rating`
- **Sibling strip:** Other properties of Door 101 (finish, material, hardware_set...) — siblings are items connected to the same parent you arrived from
- **Connection rows:** All doors with this property. Door 101 (origin) is in-path (text-trace, back-arrow). Other doors are forward navigation targets (text-ink, forward-arrow). Each door row carries its own indicator lane — pips for conflicts/changes about fire_rating on that specific door
- **Exec summary dock:** Workflow items about this property, grouped by category (conflicts, changes, directives) → instance

The density of annotation across the instance list tells the story: which doors have fire rating conflicts, which have changes, which are silent. No special rendering — the universal template and indicator lane do the work.

## Navigation Model

Graph traversal through a DAG. The breadcrumb records YOUR path, not the data hierarchy.

### X-axis (forward)

Click a connection to navigate forward. Extends the breadcrumb linearly. Even through shared junctions (diamonds), forward always feels like forward.

### Z-axis (lateral)

Jump between siblings — items connected to the same parent you came from. Triggered by clicking a sibling in the sibling strip, or by following a red-string cross-reference. The breadcrumb **forks**: old branch drops below and fades, new branch appears on top. This is the only time the breadcrumb has vertical dimension.

### Snap-back

In-path items are always clickable — in the breadcrumb, sibling strip, and connection rows. Clicking one snaps back to that point, trimming everything after it. No loop: you're retracing, not extending.

Visual treatment: in-path connection names use `text-trace` (vs `text-ink` for forward). Back-arrow (←) on hover instead of forward-arrow (→).

### Breadcrumb fork lifecycle

1. **Fork creation:** Z-axis jump creates a fork. Dead branch drops below in `text-trace`.
2. **Fork persistence:** Forward navigation extends the active branch. Dead branch stays visible.
3. **Branch absorption:** Navigate to an item on the dead branch. Dead branch disappears, item appends to the active path. Fork resolves to a straight line.

### Sibling strip

A minimal `text-xs` horizontal bar below the breadcrumb showing items connected to the parent you arrived from. Active item: `bg-board font-medium text-ink`. Siblings: `text-graphite hover:text-ink`. In-path siblings: `text-trace hover:text-graphite` (clickable, snap-back). Answers "what else is here?" without competing with content.

## Patterns

### Property row — The core unit

Property rows render differently depending on proximity state:

**Present — perspective-dependent rendering:**
```
conflicted: border-l-2 border-l-redline
            YOUR source's value shown inline + filled red pip.
            Expand row → reveals other source (red string) + their value.
            Conflict item view (pip click) shows both sources side by side.

changed:    bg-pencil-wash, border-l-2 border-l-pencil
            Both values shown in columns (comparison mode).
            Prior value in text-trace, current in pencil-ink.

directive:  bg-pencil-wash, border-l-2 border-l-overlay
            Obligation shown inline with source attribution.

resolved (directive pending):
            bg-transparent, cairn in indicator lane.
            Expand → resolution stamp + pending directive sub-row.

resolved (directive fulfilled):
            bg-transparent, no indicator. Full silence.
            Expand → source attribution (standard silent expansion).
```

**Adjacent (pip) — membrane indicator on right edge:**
```
changed:    bg-transparent, no left border, hollow amber pip on right
            Hover → detail line: "DD · paint · changed · Finish Schedule"

conflicted: bg-transparent, no left border, hollow red pip on right
            Hover → detail line: "Door Schedule says 60 min"

directive:  bg-transparent, no left border, hollow blue pip on right
            Hover → detail line: "Spec §08 expects 90 min"
```

Pips in comparison mode (where adjacent items shift to present) become filled — the hollow ring fills in as the change/conflict becomes visible inline.

**Silent — nothing. Clean ink on paper.**

**Empty value vs. assertion = conflict.** When one source maps a property but provides no value (empty/null), and another source asserts a value, that's a conflict (redline). An empty value is a meaningful assertion — "I track this property but have nothing" — not an absence of data. The user can resolve or hold this like any other conflict. Navigation lets them understand the pattern before deciding: view from the instance (one door), from the property at a specific source+time, or from the property across all snapshots of a source.

**Stale value treatment (post-resolution).** On the conflict item view, after resolution, the non-chosen source's value is shown in `redline-muted` instead of neutral `trace`. A whisper of "this value is noted as wrong, it hasn't updated yet." The chosen source's value stays in `trace`. This subtle color difference signals which side was the outlier without reactivating the conflict.

The directive row uses the pencil wash (temporal family) with the overlay blue border (time dimension). This signals "same family as a change, but hasn't happened yet." When a directive is fulfilled, the blue border transitions to amber — the obligation becomes a change.

### Connection row

Same row dimensions as property row. Name in `font-mono text-ink` (or `text-trace` if in-path). Forward-arrow or back-arrow appears on hover (`opacity-0 group-hover:opacity-100`). Optional badge for status. All connections are interactive (`cursor-pointer hover:bg-board/40`).

### Row group labels

Lightweight separators between property and connection sections: `text-xs font-mono text-trace uppercase tracking-wide bg-vellum/50`.

### Status badges

```tsx
<span className="text-xs font-medium px-2 py-0.5 rounded {variant-classes}">
  {label}
</span>
```

Variant classes:
- `redline` → `bg-redline-wash text-redline-ink`
- `pencil` → `bg-pencil-wash text-pencil-ink`
- `directive` → `bg-pencil-wash text-overlay`
- `stamp` → `bg-stamp-wash text-stamp-ink`
- `filed` → `bg-board text-filed`

### Breadcrumb

Linear: segments separated by `>` chevrons. Current segment: `font-medium text-ink`. Ancestors: `text-graphite hover:text-ink`. The "..." segment marks a jump or compaction.

Forked: active branch on top, dead branch below with fork connector line. Dead branch in `text-trace`.

### Exec summary dock (right panel)

The exec summary dock IS the right panel — replacing DS-1's separate "Notes/Reconciliation Panel." Two zones: workflow tree (top) and notes area for current item (bottom). Collapsed kernel shows badge with open workflow item count. Clicking an instance in the tree triggers a page turn to the main area; the dock stays open for context. Notes for the selected workflow item are available in the notes area below the tree.

```
Category (text-sm font-semibold, border-l-2 in category color)
  ▼ Conflicts                                          3
      ▼ Doors                                          2
          Door 101 · finish
          Door 103 · finish
      ▸ Hardware                                       1
  ▼ Changes                                            5
      ▼ Doors                                          3
          Door 101 · material
          Door 102 · width
          + 1 more
      ▼ Hardware                                       2
          HW-3 · closer
          HW-3 · threshold
  ▼ Directives                                         2
      ▼ Spec §08                                       1
          Door 101 · finish
      ▸ Schedule                                       1
  ▸ Resolved                                           4
  ▸ Notes                                              6
```

**Category level:** `text-sm font-semibold tracking-tight` in category ink color (redline-ink, pencil-ink, overlay). Left border in category accent. Count badge right-aligned in category wash+ink. Chevron for expand/collapse.

**Type level:** `text-xs font-medium text-ink`. Indented under category. Chevron for expand/collapse. Count in category muted color. Conflicts/changes group by item type (Doors, Hardware). Directives group by source that needs to update (Spec §08, Schedule) — because the question for a directive is "who needs to act?"

**Instance level:** `text-xs font-mono text-graphite` + `text-trace` for property name. Deepest indent. Clickable to navigate directly to the item.

**Resolved:** Collapsed by default (`text-sm font-medium text-graphite`). Stamp badge count. Doesn't demand attention.

**Notes (tree category):** Collapsed by default (`text-sm font-medium text-graphite`). Count in `text-trace`. Same three-level tree (Notes → by type/location → individual notes). This is the "from afar" access path — you don't need to stumble across a cairn to find notes. Notes are items in the graph and roll up like everything else.

**Notes area (bottom zone):** Below the workflow tree. Tracks the main story panel's current item — a contextual surface for reading and authoring notes. Section header: "NOTES · n" (`font-mono font-size-11 text-trace uppercase`), collapse chevron. Collapsed by default when no notes; auto-expands when navigating to an item with notes. Each note renders: cairn triangle (10px, `text-trace`, filled/hollow per present/adjacent) + content (`font-sans font-size-12 text-ink`) + meta line (`font-mono font-size-11 text-trace`, format: Author · YYYY-MM-DD). Add note input: textarea (`min-height: 48px`) + "Add" button (`background: transparent; color: var(--graphite); border-color: var(--rule-emphasis)`). Height: `flex: 0 1 auto; max-height: 40%; overflow-y: auto`. Empty state at project level: "Navigate to an item to see notes." The Notes tree category (above) is a global rollup; this bottom zone is contextual. Both reference the same cairn items in the graph.

**By-property grouping:** The exec summary supports grouping by property as an alternative axis to grouping by item type. Same three-level tree structure: category (Conflicts, Changes, Directives) → property (Fire Rating, Finish, Material) → affected instance (Door 101, Door 103). Each property in the tree is a navigable item — click to page-turn to the property item. The toggle between "by type" and "by property" grouping is a view option, not a structural change.

### Scale panel accordion

Type groups expand to show instances. Expanded: chevron-down + items list. Collapsed: chevron-right. Items show inline status text when relevant (`text-redline-ink` for conflicts, `text-pencil-ink` for changes). Click navigates (page turn), not just reveals.

### Comparison mode environment

Entire content area transforms:
- Background: `bg-overlay-wash`
- Borders: `border-2 border-overlay-border` (heavier than normal)
- Badge: `text-overlay bg-overlay/10` for "Comparing: X ↔ Y"
- Dividers: `divide-overlay-border/20`
- Column layout: Property | Source A | Source B

## Workflow Statuses

| Status       | Visual variant | Trigger |
|-------------|----------------|---------|
| needs_review | redline        | Auto (import pipeline) |
| in_review    | pencil         | Explicit "Start Review" on workflow item view |
| needs_action | redline        | Implicit (reserved) |
| accepted     | stamp          | Resolve / Acknowledge |
| hold         | filed          | Hold action (any surface, any workflow type including directives) |

## Dashboard as Navigation Surface

Dashboard property rollups are navigable. Each property count in the dashboard breakdown is a real item in the graph. Click `fire_rating (3 conflicts)` → page-turn to `door/fire_rating` → see all affected doors, all workflow items, the full story. The dashboard is an entry point into the graph, not a reporting dead end.

## Review UX

Two action surfaces for workflow items:

**Surface 1 (inline expansion):** Quick triage. Resolve (pick value) or Hold. No notes, no status change.

**Surface 2 (workflow item view):** Deliberate review. Start Review (→ `in_review`), Resolve (value, rationale, decided-by), Hold, Note area for cairn creation. "Start Review" appears only when status is `detected`; disappears once `in_review`.

**Resolution fields:** Value selection (radio: each source's value + custom), rationale (free text — captures reasoning/method/evidence), decided-by (text). Date is auto-captured (system timestamp on resolve). No manual date input.

**Button variants:** Resolve → `stamp`. Hold → `filed`. Acknowledge → `pencil`. Start Review → neutral (`text-ink border-rule-emphasis`, no spectrum color — preliminary signal, not a resolution). Resume Review → `stamp`. Every action button carries the visual weight of what it produces.

**Directive hold:** Directives support hold (→ `filed` treatment in expansion sub-row). Resume restores `pending`. Allows hiding directives that cannot currently be fulfilled.

## Anti-patterns

- No status badges on aligned items (silence = alignment)
- No card-heavy dashboard layouts (this is a document table, not a kanban)
- No saturated sidebar navigation (accordion TOC, not painted sidebar)
- No shadows for depth hierarchy (borders only, except floating elements)
- No hardcoded type-specific rendering (ALL driven by type config)
- No "children" language — only connections (the architecture is a DAG, not a tree)
- No disabled/dead items — in-path items are always clickable (snap-back)
- No feature flags or backward-compat shims
