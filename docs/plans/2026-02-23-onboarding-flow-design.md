# Onboarding Flow Design

> DS-3: Login, Project List, Empty States, Add Data

## Core Principle

There is no onboarding flow. There are only empty states at each scale of the existing navigation system that guide the user toward their first import. The interface reveals itself as data structure grows.

## Flow Architecture

```
Login → Project List → Project View → Add Data → [Mapping Review] → Navigation UI
```

- **Login** — the only screen outside the navigation system
- **Project List** — root scale of the Powers of Ten model
- **Project View** — universal template, empty state guides to Add Data
- **Add Data** — the snapshot triple as interface (when / who / what)
- **Mapping Review** — conditional, only when auto-mapping confidence < 0.8

## Design Decisions

### D1: Auth is email/password, session-based
Simple MVP auth. No OAuth, no magic links.

### D2: Project creation is container-only
Creating a project does not require milestones or data. You name a container, you're in.

### D3: One import action surface — "Add Data"
A single button that teaches the snapshot triple:
- **When** — milestone (combobox, type-to-create)
- **Who** — source (combobox, type-to-create, typed: schedule/specification/drawing)
- **What** — file picker

### D4: Type-to-create for milestones and sources
Comboboxes double as search and creation. Type a name that doesn't exist → "Create 'DD'" appears as an option. No modals, no separate creation flows.

### D5: Add Data is both persistent and contextual
- Persistent "Add Data" button in breadcrumb bar (right-aligned), visible once inside a project
- Context-sensitive: pre-fills based on current navigation (on a milestone → "when" is pre-filled)
- On project empty state: also appears as the primary CTA in the story panel

### D6: Auto-accept mapping when confidence ≥ 0.8
High-confidence auto-mapping skips the confirmation step entirely. User goes from file → populated view in two clicks. Mapping review only surfaces when auto-mapping is uncertain.

### D7: Chrome reveals progressively
- First-run (no projects): bare — just the Create Project button, no sidebar, no toolbar
- Project list: breadcrumb bar appears
- Project view: scale panel + exec summary dock appear
- Interface unfolds as data structure grows. Never show empty scaffolding.

### D8: Login rhymes with Cadence but isn't the navigation system
Same type family (Geist), same paper warmth (vellum/sheet), centered card composition. Not the universal template.

### D9: Project list always shown (no single-project skip)
Even with one project, show the list. Users may want to create another.

## Screen Specifications

### 1. Login

**Layout:** Centered card on `vellum` background. Card is `sheet` surface, `border-rule`, no shadow. Max-width ~360px.

**Contents:**
- "Cadence" in `text-2xl font-semibold tracking-tight text-ink`
- "Construction data reconciliation" in `text-sm text-graphite`
- Email input
- Password input
- Sign in button: `bg-ink text-sheet` (inverted — the one strong action)
- Error: inline below password, `text-sm text-redline-ink`

**Feel:** Quiet. Paper-and-ink. Card on vellum like a document on a desk.

### 2. Project List

**First-run (no projects):**
- No chrome (no scale panel, breadcrumb bar, exec summary dock)
- `vellum` background, centered composition
- "No projects yet" in `text-lg text-graphite`
- Single "Create Project" button: `bg-ink text-sheet`

**With projects:**
- Breadcrumb bar: "Cadence" as root
- No scale panel (nothing above projects)
- Story panel renders project cards (`render_mode: "cards"`)

**Project card:**
- Name: `text-lg font-semibold text-ink`
- Description: `text-sm text-graphite`, 2-line truncate
- Metadata: milestone count, source count, action items — `text-xs font-mono text-trace`
- Click → page turn to project view

**Create Project action:**
- Card-shaped button at end of list, dashed `border-rule`, `text-graphite`, "+ Create Project"
- Click → card transforms to inline form: name input + description (optional) + "Create" button
- No modal. Type, enter, navigate into the new project.

### 3. Project Empty State

Universal template for a project item with no milestones/sources. The "Add Data" button appears in the breadcrumb bar chrome AND as the primary CTA in the empty story panel.

Empty connection groups show guided messaging:
- Milestones: "No milestones yet. Add data to create your first milestone."
- Sources: "No sources yet."

### 4. Add Data (Snapshot Triple Form)

The import surface. Three fields that map to the snapshot triple (when/who/what). UI labels use natural language — "Milestone", "Source", "File" — not the architectural dimension names.

**Milestone** (the "when"):
- Combobox with existing milestones
- Type a new name → "Create '100% DD'" option appears
- Creating inline assigns next ordinal automatically
- Placeholder examples use standard AEC conventions: "25% DD, 50% CD, 100% CD..."

**Source** (the "who"):
- Combobox with existing sources
- Type a new name → "Create 'Finish Schedule'" option appears
- Source type selector (schedule / specification / drawing) shown on create

**File** (the "what"):
- File picker (drag-and-drop zone + browse button)
- Accepts .xlsx, .csv
- Shows filename + size after selection

**Submit:** "Import" button. Runs analyze → auto-accept if ≥ 0.8 confidence → navigate to populated milestone view. If < 0.8, show mapping review.

**Context pre-fill:** If opened from a milestone view, Milestone is pre-filled. If opened from a source view, Source is pre-filled.

### 5. Mapping Review (Conditional)

Only shown when auto-mapping confidence < 0.8 on any column.

Renders the analyze endpoint's `ProposedMappingResponse` as a confirmation surface:
- Each column → property mapping shown as a row
- High-confidence mappings: shown but not highlighted
- Low-confidence mappings: highlighted with `pencil-wash` background, dropdown to correct
- Unmapped columns: shown with empty target, dropdown to assign or skip

"Confirm" button applies corrections and triggers the actual import.

---

## Amendments (CTO Review — 2026-02-25)

### A1: First import from a new source always shows mapping review

Amends **D6**. The ≥ 0.8 auto-accept threshold applies only to *repeat imports from an existing source* (where the stored mapping has already been validated by the user). For the first import from any new source, always show the mapping review — but present it as a **confirmation**, not a correction. High-confidence mappings render as pre-checked rows. The user scans, sees that Cadence understood their columns, and hits "Confirm." This takes five seconds, builds trust, and teaches the user that the system understands their data. On subsequent imports from the same source, the stored mapping skips review entirely.

**Rationale:** The first import is the moment where trust is established or lost. A black box that silently maps columns — even correctly — feels like a system that didn't show its work. Showing the mapping and having the user confirm creates shared understanding. Once trust is established, speed takes over.

### A2: Milestone ordinal assignment uses AEC pattern matching

Amends **D4** ("assigns next ordinal automatically"). When a new milestone name is created via type-to-create, the system matches against the standard AEC milestone template (`GET /v1/config/milestone-template`) to assign the correct ordinal. Pattern matching is case-insensitive and handles common variants:

- "SD", "100SD" → SD range (ordinal 200)
- "50DD", "DD" → DD range (ordinals 250, 300)
- "50CD", "CD" → CD range (ordinals 350, 400)
- "Bid", "Bid Set" → Bidding range (ordinal 500)
- "CA" → CA range (ordinal 600)

Sub-milestone ordinals (e.g., 50DD → 250, 25DD → 225) are interpolated within the phase range. If the name doesn't match any known AEC pattern, the milestone is appended after the highest existing ordinal.

**Rationale:** Ordinal determines effective value resolution ordering. "50DD" must always sort before "50CD" regardless of upload order. The hundreds system with gaps for sub-milestones solves the out-of-order upload problem for the 90% case (standard AEC milestones) and falls back gracefully for non-standard names. A future reorder UI can handle corrections for edge cases.

### A3: Post-import navigates to project dashboard, not milestone

Amends **Screen 4 Submit** ("navigate to populated milestone view"). After a successful import, navigate to the **project view** (dashboard), which now shows real counts — "50 doors, 10 rooms, 1 source, 0 conflicts." This gives the user the aerial view first and lets the Powers of Ten model work from the top down. They see the executive summary, then drill into the scale panel to explore items. Dropping them directly at the milestone level puts them one scale too deep without context.

**Rationale:** The post-import moment is where the user first experiences the navigation system with their own data. The project dashboard is the natural starting point — it's the scale that tells the broadest story and connects to everything below. The user learns the drill-down grammar by starting wide and going narrow, which is the DS-1 design intent.

### A4: Source type defaults to "schedule"

Amends **Screen 4 Who — Source**. When a user types a new source name and "Create" appears, the source type selector defaults to `schedule`. The selector is visible and changeable but doesn't require an explicit choice for the most common case. Specification and drawing are available but not the default.

**Rationale:** The first import is almost always a schedule. Requiring the user to explicitly choose "schedule" when it's the obvious answer adds friction to the critical path. Defaulting correctly removes one decision point from the flow. Users importing specs or drawings are making a deliberate choice and can change the default.

### A5: Import progress feedback

Addition to **Screen 4**. After the user hits "Import" (or "Confirm" from mapping review), the UI shows a stepped progress indicator — not a spinner, but named stages that communicate what the system is doing:

- "Creating milestone…" (if new)
- "Creating source…" (if new)
- "Importing 50 doors…"
- "Detecting changes…" (if prior milestone exists)
- "Checking for conflicts…" (if other sources exist)
- ✓ "Import complete — 50 items, 3 changes detected"

Each step appears as it completes, building a quick narrative. The final summary line stays visible for 2–3 seconds before navigating to the project dashboard (per A3).

**Rationale:** The import pipeline does significant graph mutation in one gesture — creating items, connections, snapshots, change items, conflict items. Showing the user what happened builds trust and teaches them the system's capabilities. "3 changes detected" is a hook that makes them want to explore. The progress also covers the latency of the actual import operation (up to 30s for large schedules).

### A6: "Add Data" button shifts to quiet styling when data exists

Amends **D5**. The "Add Data" button in the breadcrumb bar has two visual states:

- **Empty project (no milestones):** Primary styling — `bg-ink text-sheet`. This is the CTA. The story panel empty state also shows it as the central action.
- **Active project (milestones exist):** Quiet styling — `text-graphite border-rule`, blending with the breadcrumb bar. Still discoverable, but the visual emphasis shifts from "add data" to the navigation system and the data that's already there.

The story panel CTA disappears once any milestone exists. The breadcrumb bar button is the permanent home.

**Rationale:** After the first import, the user's primary action shifts from "add data" to "explore and understand." The interface should reflect this shift. A persistent primary-styled CTA in the breadcrumb bar creates a subtle pressure to add more data when the user should be experiencing what's already there.
