# Cadence v6.1 — Implementation Workplan (Revised)
## "From Specification to Running System"

---

## Preamble: Architectural Decisions to Lock Before Coding

The technical review surfaced several specification gaps. These must be resolved before any code is written, because they affect the schema and core operations. Each is stated here as a decision, not a discussion.

### Decision 1: Source vs. Operator

`source_id` references the **authority** (the document — schedule, specification, drawing). `created_by` on the snapshot records the **operator** (the person who performed the import or action). These answer different questions:

- "What does the schedule say?" → query by `source_id`
- "Who imported this?" → query by `created_by`

For self-sourced items (user-created rooms, manually entered data), `source_id = item_id` and `created_by = user_id`. The item is its own authority; the user is the operator.

**Implication:** No change to the spec. `created_by` already gives you "go talk to Steve."

### Decision 2: Conflict Lifecycle — Decision as Resolution Source

When a conflict is resolved, the resolution snapshot uses `source_id = decision_item_id` rather than `source_id = conflict_item_id`. This preserves both the detection snapshot and the resolution snapshot under the same `(item_id, context_id)` without violating the UNIQUE constraint.

The conflict's story is told by multiple narrators:
- Detection: `(conflict_id, milestone, conflict_id)` — the conflict describes itself
- Resolution: `(conflict_id, milestone, decision_id)` — the decision describes the conflict's resolution

**Implication:** The `getResolvedView` and conflict lifecycle queries must account for snapshots from both the conflict itself and its decision(s). The same pattern applies to changes: acknowledgment could use the acknowledging user's action as a distinct source, though for Phase 1 we can use upsert on changes since their lifecycle is simpler (DETECTED → ACKNOWLEDGED, no intermediate states lost).

### Decision 3: Milestone Ordering

Milestones carry an `ordinal` property that determines temporal sequence. A project ships with a default milestone template based on standard AEC phases:

```
Concept (ordinal: 100)
SD — Schematic Design (ordinal: 200)
DD — Design Development (ordinal: 300)
CD — Construction Documents (ordinal: 400)
Bidding (ordinal: 500)
CA — Construction Administration (ordinal: 600)
Closeout / Post-Occupancy (ordinal: 700)
```

Ordinals use gaps (100, 200, ...) to allow insertion of sub-milestones (25%DD = 250, 50%DD = 275, DD = 300). Users can create custom orderings. Effective value resolution uses milestone ordinal, not `created_at` timestamp.

**Implication:** The `getEffectiveSnapshots` query orders by milestone ordinal via a JOIN to the context item's properties. The schema itself doesn't change — ordinal lives in `items.properties` for milestone-type items.

### Decision 4: Connection Direction Convention

Connections follow **container/authority → contained/described** direction:

- Room → Door (room contains door)
- Schedule → Door (schedule describes door)
- Phase → Milestone (phase contains milestone)
- Project → Phase (project contains phase)
- Project → Building (project contains building)

Workflow items reverse this — they point TO what they reference:

- Conflict → Door (conflict affects door)
- Conflict → Schedule (conflict involves this source)
- Decision → Conflict (decision resolves this conflict)
- Change → Door (change affects this door)

Navigation queries default to **both** directions, filtered by item type. The direction convention is for human readability and import logic consistency, not for query filtering.

**Implication:** Navigation queries always use `direction=both` unless explicitly filtered. The API default changes from `outgoing` to `both`.

### Decision 5: One Conflict Per Property Per Item

`getOrCreateConflict` creates one conflict item per (affected_item, property_path) pair. If Door 101 has conflicts on both `finish` and `material`, those are two separate conflict items. This keeps conflicts atomic and independently resolvable.

**Implication:** Conflict identifier format is `"{item_identifier} / {property_path}"`. Bulk resolution operates on multiple conflict items, not multiple properties within one conflict.

### Decision 6: The Index Fix

The `idx_items_active_action` index in the spec references `properties->>'status'`, but status lives in snapshot properties, not item properties. This index should be removed from the items table. Action item status queries go through the snapshots table. No special index needed for Phase 1. Add if query performance demands it.

---

## Operating Model

### Roles

- **Nick (CEO/Architect):** 15 hours/week. Architectural decisions, UX design leadership, specification clarification, review, acceptance testing.
- **AI Agents:** Parallel backend and frontend implementation. Each work package is a self-contained unit with clear inputs, outputs, and acceptance criteria.
- **Design Sessions (Nick + Claude):** Collaborative work sessions that produce UX specifications before any frontend implementation begins. These are where the original Cadence UX gets translated into the v6.1 architecture.

### The Design/Implementation Split

AI agents build good backends and execute established design patterns well. They do not design good user experiences. The original Cadence prototype was well-received specifically because Nick designed the UX with an architect's sensibility for how construction professionals think and navigate data. That design intelligence must drive v6.1's interface.

Every frontend milestone follows a two-stage process:

1. **Design Session (DS-X):** Nick and Claude collaborate to produce a UX specification. This includes: information architecture, interaction patterns, layout decisions, component inventory, and reference to the original Cadence UX where applicable. The output is a design document detailed enough for an agent to implement without making UX decisions.

2. **Frontend Implementation (FE-X):** An agent implements the design specification. The agent makes zero UX decisions — layout, interaction flow, information hierarchy, what's visible vs. hidden, what's emphasized vs. muted are all dictated by the design doc.

Backend work packages (WP-X) proceed independently and do not wait for design sessions. The backend API is shaped by the data model and the spec, not by UI layout. Design sessions can reference the API to understand what data is available, but they don't block backend progress.

---

## Workplan Structure

### Dependency Graph

```
BACKEND (agent-executable, no design dependency):

WP-1 (Schema + DB Setup)
  ├── WP-2 (Items + Connections CRUD API)
  │     ├── WP-4 (Navigation API + Bounce-back)
  │     └── WP-5 (Snapshot CRUD API)
  │           ├── WP-6 (Import Pipeline)
  │           │     ├── WP-9 (Change Detection)
  │           │     │     └── WP-11 (Conflict Detection)
  │           │     │           └── WP-12 (Resolution Workflow API)
  │           │     │                 └── WP-13a (Dashboard API)
  │           │     └── WP-8 (Temporal Comparison API)
  └── WP-3 (Type Configuration + Seed Data)


DESIGN SESSIONS (collaborative, Nick + Claude):

DS-1 (Core Navigation + Item Views)
  └── DS-2 (Temporal Comparison + Change Views)
        └── DS-3 (Conflict Views + Source Attribution)
              └── DS-4 (Resolution Workflow + Dashboard)


FRONTEND IMPLEMENTATION (agent-executable, requires design + API):

DS-1 + WP-4 + WP-5 → FE-1 (Navigation UI)
DS-2 + WP-8 + WP-9 → FE-2 (Comparison UI)
DS-3 + WP-11      → FE-3 (Conflict + Attribution UI)
DS-4 + WP-12 + WP-13a → FE-4 (Resolution UI + Dashboard)
```

**Key insight:** Backend work runs continuously. Design sessions happen when Nick has time and ideally slightly ahead of when the corresponding frontend implementation would start. If backend gets ahead of design, that's fine — the API is ready and waiting. If design gets ahead of backend, the design doc is ready for the agent the moment the API ships.

---

## Phase 1: Foundation (Weeks 1–4)

### WP-1: Database Schema and Project Setup

**Goal:** Running PostgreSQL with the complete schema, Docker Compose environment, and project scaffolding.

**Scope:**
- Docker Compose configuration: PostgreSQL 16 (with pg_trgm), FastAPI backend, React frontend
- Database schema: `items`, `connections`, `snapshots` (exactly as spec, with the index fix from Decision 6)
- Infrastructure tables: `users`, `permissions`, `notifications`
- Database migration setup (Alembic)
- Basic health check endpoint
- `.env` configuration for local development
- Code conventions: linting (ruff), formatting (black), TypeScript strict mode, ESLint + Prettier

**Outputs:**
- `docker-compose.yml` — one command (`docker compose up`) brings up the full stack
- `backend/` — FastAPI project structure with SQLAlchemy async models
- `frontend/` — React + TypeScript + Tailwind project structure (Vite)
- `alembic/` — initial migration that creates all tables and indexes
- Seed SQL that creates a test user

**Acceptance Criteria:**
- `docker compose up` starts all services without errors
- `GET /api/health` returns 200 with database connection confirmation
- Tables exist with correct constraints (verify UNIQUE on snapshots, CHECK on connections)
- `pg_trgm` extension is enabled

**Estimated Effort:** 1 agent, 2–3 days

---

### WP-2: Items and Connections CRUD API

**Goal:** Full CRUD for items and connections with validation.

**Scope:**
- Items: Create, Read, Update (properties merge), List (with type filter, search, pagination)
- Connections: Create, Read, Disconnect (soft — record reason), List connections for an item
- Input validation: item_type against known types, self-connection prevention, duplicate connection prevention
- Identifier normalization utility (for later use in import matching)
- Error handling: proper HTTP status codes, meaningful error messages

**Inputs:** WP-1 (running database, SQLAlchemy models)

**Outputs:**
- `POST /api/items` — create item
- `GET /api/items/:id` — get item
- `GET /api/items` — list/search items (with `?type=`, `?search=`, `?project=`, pagination)
- `PATCH /api/items/:id` — update properties (merge semantics)
- `POST /api/connections` — create connection
- `POST /api/connections/disconnect` — soft disconnect
- `GET /api/items/:id/connections` — list connections (both directions)
- Unit tests for all endpoints
- Pydantic schemas for all request/response models

**Acceptance Criteria:**
- Can create items of any configured type
- Can connect two items and query connections in both directions
- Self-connection returns 400
- Duplicate connection returns 409 (or idempotent 200)
- Search by identifier works (exact and partial)
- Properties merge correctly (PATCH updates keys, doesn't replace entire object)

**Estimated Effort:** 1 agent, 2–3 days

---

### WP-3: Type Configuration and Seed Data

**Goal:** Type configuration registry accessible to both backend and frontend, plus realistic seed data for a door schedule project.

**Scope:**
- Type configuration as defined in spec (TypeConfig interface)
- Shared type config accessible via API endpoint (`GET /api/config/types`)
- Seed data script that creates a realistic project structure:
  - 1 Project ("Project Alpha")
  - 1 Building ("Building A")
  - 3 Floors
  - 10 Rooms (distributed across floors)
  - 50 Doors (distributed across rooms)
  - 2 Phases (DD, CD) with milestones (DD milestone at ordinal 300, CD milestone at ordinal 400)
  - 1 Schedule source ("Finish Schedule")
  - 1 Specification source ("Spec §08 — Openings")
  - All connections wired up
- Milestone template with standard AEC ordinals (per Decision 3)

**Inputs:** WP-1, WP-2

**Outputs:**
- `backend/config/types.py` — type configuration registry
- `GET /api/config/types` — returns full type config
- `scripts/seed_data.py` — creates the complete test project
- Seed data creates realistic door properties (finish, material, hardware_set, frame_type, dimensions, fire_rating)

**Acceptance Criteria:**
- After running seed script, `GET /api/items?type=door` returns 50 doors
- Each door is connected to a room, each room to a floor, each floor to a building, building to project
- Phases exist with connected milestones at correct ordinals
- Schedule and spec sources exist and are connected to the project
- Type config endpoint returns all configured types with their properties

**Estimated Effort:** 1 agent, 1–2 days

---

### WP-4: Navigation API

**Goal:** The connected-items endpoint that powers breadcrumb navigation, including bounce-back logic.

**Scope:**
- `GET /api/items/:id/connected` — returns item detail + connected items grouped by type
  - Direction parameter (default: both, per Decision 4)
  - Exclude parameter (breadcrumb ancestor UUIDs)
  - Type filter parameter
  - Include action item counts (changes, conflicts connected to each item)
- Connected items sorted per type configuration (`defaultSort`)
- Response shape matches spec (item + connected grouped by type + snapshots if available)
- Bounce-back algorithm: given a breadcrumb (array of UUIDs) and a target UUID, compute the new breadcrumb

**Inputs:** WP-2 (CRUD API), WP-3 (type config for sorting/grouping)

**Outputs:**
- `GET /api/items/:id/connected` endpoint with full parameter support
- `POST /api/navigate` — given `{ breadcrumb: UUID[], target: UUID }`, returns new breadcrumb
  - Handles: direct child push, ancestor pop, sibling bounce-back, no-path-found
- Unit tests covering: direct navigation, backtracking, sibling bounce-back, diamond pattern traversal

**Acceptance Criteria:**
- From a room, connected items include doors (outgoing), floor (incoming), schedule (incoming)
- Breadcrumb ancestors are excluded from connected items
- Sibling bounce-back works: breadcrumb `[project, building, floor, room, door101]` + target `door102` → `[project, building, floor, room, door102]`
- Action item counts appear on items that have connected changes/conflicts
- Diamond pattern: from a door, both schedule and spec appear as connected items

**Estimated Effort:** 1 agent, 2–3 days

---

### WP-5: Snapshot CRUD API

**Goal:** Create, read, and query snapshots with the full (what, when, who) triple.

**Scope:**
- `POST /api/items/:id/snapshots` — create snapshot (validates context_id is temporal, source_id exists)
- `GET /api/items/:id/snapshots` — get all snapshots for an item (filterable by context, source)
- `GET /api/items/:id/resolved` — resolved view for an item at a context (per spec's `getResolvedView`)
- `GET /api/items/:id/effective` — effective value from a specific source (most recent by milestone ordinal)
- Effective value resolution: ordered by milestone ordinal (JOIN to context item's properties), not by `created_at`
- Upsert semantics on UNIQUE(item_id, context_id, source_id)

**Inputs:** WP-2, WP-3 (need milestones with ordinals)

**Outputs:**
- Snapshot endpoints as listed above
- Resolved view computation (agreed / single_source / conflicted / resolved statuses)
- Effective value query with milestone-ordinal ordering
- Unit tests for: snapshot creation, uniqueness constraint, resolved view with 2 agreeing sources, resolved view with 2 disagreeing sources, effective value carry-forward from prior milestone

**Acceptance Criteria:**
- Can create two snapshots for the same door at DD from different sources
- Resolved view correctly identifies agreement (same value) and conflict (different values)
- Effective value for a source that only submitted at DD correctly returns the DD value when queried at CD
- Effective value ordering uses milestone ordinal, not created_at (test by creating DD snapshot after CD snapshot — DD value should NOT be "effective")

**Estimated Effort:** 1 agent, 3–4 days

---

### WP-6: Import Pipeline

**Goal:** Parse Excel/CSV door schedules, create source-attributed snapshots, match items by identifier.

**Scope:**
- File parsing: Excel (.xlsx) and CSV support
- Import mapping configuration (stored on source item as property)
- `PUT /api/items/:source_id/import-mapping` — store/update mapping config
- `GET /api/items/:source_id/import-mapping` — retrieve mapping config
- Identifier matching: exact → normalized → fuzzy (with pg_trgm)
- Item creation for unmatched identifiers (with user confirmation flow for fuzzy matches)
- Snapshot creation for each matched/created item: `(item_id=door, context_id=milestone, source_id=schedule)`
- Source self-snapshot: `(item_id=schedule, context_id=milestone, source_id=schedule)` with metadata
- Connection creation: source → target for each imported item
- Milestone validation: context must have `isTemporal: true`
- Single-writer enforcement: lock check at project level (advisory lock or simple flag)
- `POST /api/import` — the main import endpoint
- `GET /api/import/:batch_id/unmatched` — items that need user confirmation
- `POST /api/import/:batch_id/confirm-match` — confirm a fuzzy match
- System-provided normalizations: `lowercase_trim`, `imperial_door_dimensions`, `numeric`

**Inputs:** WP-2, WP-3 (seed data with schedule source, milestones), WP-5 (snapshot creation)

**Outputs:**
- Import endpoint with full mapping, matching, and snapshot creation
- Import mapping CRUD on source items
- Batch tracking (import_batch item created per import)
- ImportResult response with summary counts
- Unit tests with sample Excel file (50 doors)
- Normalization functions with tests (dimension parsing, case/whitespace handling)

**Acceptance Criteria:**
- Import a 50-row door schedule Excel file at DD milestone → 50 door snapshots created, all attributed to the schedule source
- Source self-snapshot created with row_count, columns, file_name
- Connections created between schedule and each door
- Re-import same file at same milestone → upserts (no duplicates)
- Normalized matching: "Door 101", "DOOR 101", "DR-101" all match the same item
- Import mapping stored on source item and reused on second import
- Second import with different milestone → new snapshots at new context, old ones preserved

**Estimated Effort:** 1 agent, 4–5 days

---

### DS-1: Core Navigation and Item View Design ⬤ DESIGN SESSION

**Goal:** Establish the complete UX language for Cadence v6.1 — navigation model, item rendering, information hierarchy, visual identity. This is the foundational design session; everything else builds on it.

**Participants:** Nick + Claude (collaborative session, not agent work)

**Reference Material:**
- Original Cadence prototype UX (Nick to share screenshots, walkthrough, or description)
- v6.1 technical spec (navigation, type configuration, resolved view)
- WP-4 API response shapes (what data is available at each navigation step)
- WP-5 snapshot response shapes (how source-attributed data looks)

**Agenda / Questions to Resolve:**

1. **What worked in the original Cadence UX?**
   - Which patterns, layouts, and interaction models should carry forward?
   - What felt right to architects who tested it? What felt right to non-architects?
   - What would you change if you could?

2. **Navigation experience:**
   - Breadcrumb appearance, behavior, and visual weight
   - How does "drill in" feel? Click a row? Click a card? Expand inline?
   - How does bounce-back manifest? Animation? Breadcrumb update? Transition?
   - How prominent is the breadcrumb vs. the content area?
   - What does the "home" state look like (project list, or something else)?

3. **Item rendering by type:**
   - Door table view: which columns, what density, how do you scan 50 doors?
   - Room/building card view: what's on the card? How much data at a glance?
   - Timeline view for milestones/phases: horizontal? Vertical? Compact?
   - How do connected items of different types coexist on screen? Tabs? Sections? Sidebar?

4. **Snapshot and source display:**
   - How do you show "Schedule says X, Spec says Y" without overwhelming?
   - Is the resolved view a matrix? A list? Inline annotations?
   - How do you indicate single_source vs. agreed vs. conflicted at a glance?
   - Where does temporal context (which milestone are you looking at) live in the UI?

5. **Visual identity:**
   - Color palette, typography, density preferences
   - How "architectural" should it feel vs. generic SaaS?
   - Icon set and visual language for item types
   - Light/dark mode considerations

6. **Responsive behavior:**
   - Desktop-first? Or mobile-relevant from the start?
   - Minimum viable viewport

**Outputs:**
- **UX Specification Document (DS-1-spec):** Detailed enough for an agent to implement without making design decisions. Includes:
  - Component inventory with layout descriptions
  - Interaction patterns (click behaviors, transitions, state changes)
  - Information hierarchy per view (what's primary, secondary, tertiary)
  - Wireframes or annotated sketches (can be rough — agents need structure, not polish)
  - Design tokens: colors, spacing scale, typography scale, border radii
  - Responsive breakpoints and behavior
- **Component naming convention** (so agents produce consistent code)
- **Explicit "do not" list** — things agents should avoid (e.g., no floating action buttons, no hamburger menus, no modal overuse, etc.)

**Timing:** Should happen during Weeks 2–3, while WP-4/WP-5/WP-6 are being built. FE-1 starts after DS-1 is complete and WP-4 + WP-5 APIs are ready.

---

### FE-1: Navigation UI Implementation

**Goal:** Implement the navigation interface exactly as specified in DS-1.

**Inputs:**
- DS-1 UX specification (the design document — this is the primary authority)
- WP-3 type configuration (drives rendering behavior)
- WP-4 navigation API (connected items, bounce-back)
- WP-5 snapshot API (source-attributed data display)

**Scope:**
- React application shell, routing, layout structure per DS-1
- Breadcrumb component per DS-1 spec
- Navigation state management (client-side breadcrumb stack)
- Item detail view with connected items grouped by type — layout per DS-1
- Type-driven rendering using TypeConfig — render modes per DS-1
- Snapshot display per DS-1 (source attribution, resolved view indicators)
- Bounce-back navigation wired to `POST /api/navigate`
- Entry point per DS-1 (project list or other starting point)

**Agent Instructions:**
- Implement DS-1-spec exactly. Do not invent layout, spacing, color, or interaction patterns.
- If the design spec is ambiguous on a point, flag it for review — do not make a judgment call.
- All rendering must be driven by type configuration — no hardcoded item types in frontend code.

**Acceptance Criteria:**
- Navigation matches DS-1 specification in layout, interaction, and information hierarchy
- Starting from entry point, can drill into Project Alpha → Building A → Floor 1 → Room 101 → Door 101
- At Door 101, connected items display per DS-1 (schedule, spec, room, etc.)
- Breadcrumb renders and responds to clicks per DS-1
- Sibling bounce-back works per DS-1
- Snapshot/source display matches DS-1

**Estimated Effort:** 1 agent, 5–7 days

---

## Phase 2: Temporal Comparison (Weeks 5–7)

### WP-8: Temporal Comparison API

**Goal:** Compare items across milestones, with source filtering.

**Scope:**
- `POST /api/compare` — compare item snapshots across time contexts
  - Support: specific item IDs or all children of a parent item
  - Support: source filter (compare only one source's evolution)
  - Categorization: added, removed, modified, unchanged
  - Property-level diff for modified items
- Pagination for large result sets
- Summary counts in response (added/removed/modified/unchanged)

**Inputs:** WP-5 (snapshot queries), WP-6 (need data at multiple milestones to test)

**Outputs:**
- `POST /api/compare` endpoint with full spec behavior
- ComparisonResult and PropertyChange response models
- Unit tests: compare 50 doors between DD and CD where 10 changed, 5 added, 2 removed

**Acceptance Criteria:**
- Comparison correctly identifies doors that changed between DD and CD
- Property-level changes show old value and new value with correct context attribution
- Source filter works: comparing only the schedule's evolution ignores spec snapshots
- Pagination returns consistent results across pages
- Added/removed detection works (door exists at CD but not DD = added)

**Estimated Effort:** 1 agent, 3–4 days

---

### WP-9: Change Detection on Import

**Goal:** When importing at a new milestone, detect what changed from the prior milestone for the same source.

**Scope:**
- Extend import pipeline (WP-6) to include change detection
- `getMostRecentPriorContext`: find this source's most recent prior milestone (by ordinal)
- Property diff: compare new snapshot properties against prior snapshot for same (item, source)
- Create change items with self-sourced snapshots (per spec pattern)
- Create connections: change → source, change → prior context, change → new context, change → affected item
- Source-level change tracking: one change item per (source, affected_item, property_path) per import

**Inputs:** WP-6 (import pipeline), WP-5 (snapshot queries)

**Outputs:**
- Extended import flow that creates change items
- Change items have correct identifiers: `"{source} / {item} / {from_context}→{to_context}"`
- Change snapshots contain: status, changes dict, from/to context, source, affected_item
- Import result includes changeItems array and summary.sourceChanges count

**Test Scenario:**
1. Import schedule at DD: 50 doors with properties
2. Import schedule at CD: 50 doors, 10 with changed `finish`, 5 with changed `material`
3. Verify: 15 change items created, each connected to the correct door, both milestones, and the schedule
4. Verify: change snapshots contain correct old/new values

**Acceptance Criteria:**
- Import at DD creates zero change items (no prior context)
- Import at CD creates change items for every property that differs from DD
- Change items are connected to all relevant items (source, both milestones, affected item)
- No false changes: properties that didn't change don't generate change items
- Value comparison uses normalized comparison (case-insensitive strings, numeric parsing)

**Estimated Effort:** 1 agent, 3–4 days

---

### DS-2: Temporal Comparison and Change View Design ⬤ DESIGN SESSION

**Goal:** Design how users experience time in Cadence — milestone selection, comparison views, change narratives.

**Participants:** Nick + Claude

**Reference Material:**
- DS-1 outputs (established visual language, navigation patterns)
- Original Cadence temporal comparison UX
- WP-8 comparison API response shape
- WP-9 change item structure

**Agenda / Questions to Resolve:**

1. **Milestone selection:**
   - How does a user "activate" temporal comparison? Always visible? Toggle? Mode switch?
   - How do you select which milestones to compare? Dropdown? Timeline click? Multi-select?
   - Is there a concept of "current milestone context" that's always active (like a global filter)?

2. **Comparison display:**
   - Side-by-side vs. unified diff vs. inline annotations?
   - How do you show 50 doors where 10 changed? List with highlights? Filtered table?
   - Categorization badges (added/removed/modified/unchanged) — where and how?
   - Property-level diffs: inline old→new? Color-coded? Strikethrough?
   - The "past → present" direction — how is this reinforced visually?

3. **Change items as narrative:**
   - Are changes items you navigate to, or annotations on affected items, or both?
   - How does a change item display its story? ("Schedule changed Door 101 finish from paint to stain between DD and CD")
   - Do changes appear in the connected items list? As badges? In a sidebar?

4. **Source-filtered comparison:**
   - How does a user say "show me only what the schedule changed" vs. "show me everything"?
   - Is source filtering a global toggle or per-comparison?

**Outputs:**
- **UX Specification Document (DS-2-spec):** Extends DS-1 patterns for temporal views. Includes:
  - Milestone selection interaction
  - Comparison view layout and information hierarchy
  - Change item rendering (both standalone and as connected items)
  - Property diff visual treatment
  - Source filter interaction
- **Updated component inventory** with new temporal comparison components

**Timing:** Should happen during Weeks 5–6, while WP-8/WP-9 are being built.

---

### FE-2: Temporal Comparison UI Implementation

**Goal:** Implement comparison and change views exactly as specified in DS-2.

**Inputs:**
- DS-2 UX specification
- DS-1 UX specification (for consistency with established patterns)
- WP-8 comparison API
- WP-9 change items (via navigation API)

**Scope:**
- Milestone selection UI per DS-2
- Comparison results view with categorization per DS-2
- Property diff display per DS-2
- Change items visible as connected items on affected doors per DS-2
- Source filter toggle per DS-2
- Filters for type, property, status per DS-2

**Agent Instructions:**
- DS-2-spec is the primary authority. DS-1-spec governs overall visual language.
- Maintain consistency with FE-1 patterns (navigation, breadcrumb, type rendering).
- Flag any ambiguities rather than improvising.

**Acceptance Criteria:**
- Milestone selection works per DS-2
- Comparison view matches DS-2 layout and information hierarchy
- Property diffs render per DS-2 visual treatment
- Change items display per DS-2 (as connected items, as standalone views, or both)
- Source filter works per DS-2

**Estimated Effort:** 1 agent, 4–5 days

---

## Phase 3: Conflict Detection (Weeks 8–10)

### WP-11: Conflict Detection on Import

**Goal:** When importing, detect disagreements with other sources' effective values.

**Scope:**
- Extend import pipeline to include conflict detection
- For each imported item, query other sources' effective snapshots (most recent by milestone ordinal)
- Property-by-property comparison using normalized value comparison
- Create conflict items with self-sourced snapshots (per Decision 5: one per property per item)
- Connections: conflict → affected item, conflict → both sources, conflict → detection milestone
- Auto-resolution: if sources now agree on a previously conflicted property, upsert conflict snapshot to RESOLVED_BY_AGREEMENT
- Exclude workflow item types from conflict comparison (per `excludeFromConflicts` flag)

**Inputs:** WP-6 (import pipeline), WP-5 (effective value queries), WP-9 (change detection — both run during import)

**Outputs:**
- Extended import flow that creates conflict items after change detection
- Conflict items with correct identifiers: `"{item} / {property}"`
- Conflict snapshots contain: status, property_path, values dict (source_id → value), affected_item
- Auto-resolution for previously conflicted properties that now agree
- Import result includes conflictItems array, resolvedConflicts count

**Test Scenario:**
1. Import schedule at DD: 50 doors with properties
2. Import spec at DD: 50 doors, 30 with different `finish` values, 20 agreeing
3. Verify: 30 conflict items created, one per disagreeing door's finish property
4. Import schedule at CD: 10 doors' finish changed to match spec
5. Verify: 10 conflicts auto-resolved (RESOLVED_BY_AGREEMENT), 20 remain DETECTED

**Acceptance Criteria:**
- Conflict detection only fires where both sources provide a value for the same property
- Properties only reported by one source → no conflict (single_source)
- Normalized comparison prevents false conflicts ("Paint" vs "paint" → no conflict)
- Auto-resolution works when sources come into agreement
- Conflict items are properly connected to both sources and the affected item
- Import summary accurately counts new conflicts and resolved conflicts

**Estimated Effort:** 1 agent, 4–5 days

---

### DS-3: Conflict and Source Attribution Design ⬤ DESIGN SESSION

**Goal:** Design how conflicts surface, how source attribution is displayed, and how users understand disagreements.

**Participants:** Nick + Claude

**Reference Material:**
- DS-1 + DS-2 outputs (established patterns)
- Original Cadence conflict handling UX (if any existed in the prototype)
- WP-11 conflict item structure
- WP-5 resolved view API response

**Agenda / Questions to Resolve:**

1. **Conflict visibility — the "attention" problem:**
   - How do conflicts announce themselves without overwhelming? Badge counts? Color? Icon overlay?
   - At what navigation level do you first see conflicts? Project rollup? Room level? Door level?
   - Is there a "conflict mode" or are conflicts always visible?
   - What's the information scent? How does a user following a trail of conflict indicators end up at the specific disagreement?

2. **Resolved view — the "truth table":**
   - This is the core of conflict display: for an item at a milestone, show what each source says.
   - Matrix? (rows = properties, columns = sources) Or list with inline source tags?
   - How do you handle the asymmetry where Source A has 6 properties and Source B has 3?
   - Color/icon treatment for: agreed, single_source, conflicted, resolved
   - Where does the "effective value" (the thing you'd actually use) appear relative to source values?

3. **Conflict detail view:**
   - When you navigate into a conflict item, what do you see?
   - The specific values? The sources? The affected item? The timeline of detection?
   - How much context should be on the conflict vs. requiring navigation back to the affected item?

4. **Scale and density:**
   - "30 conflicts" is a lot. How does the UI help you triage?
   - Grouping by property? By source pair? By affected item type?
   - Is there a "conflict list" view distinct from navigation, or is it the same action items list filtered to conflicts?

**Outputs:**
- **UX Specification Document (DS-3-spec):** Includes:
  - Conflict indicator design (badges, colors, icons at each navigation level)
  - Resolved view layout and visual treatment
  - Conflict detail view layout
  - Conflict list/triage view layout
  - Source attribution visual language (consistent across navigation and conflict views)

**Timing:** Should happen during Weeks 8–9, while WP-11 is being built.

---

### FE-3: Conflict and Source Attribution UI Implementation

**Goal:** Implement conflict surfaces and source attribution exactly as specified in DS-3.

**Inputs:**
- DS-3 UX specification
- DS-1 + DS-2 specifications (consistency)
- WP-11 conflict data (via navigation API and action items endpoint)
- WP-5 resolved view API

**Scope:**
- Conflict indicators at all navigation levels per DS-3
- Resolved view for any item at any milestone per DS-3
- Conflict detail view per DS-3
- Conflict list/triage view per DS-3
- Navigation from door → conflict → back to door, per existing navigation patterns

**Agent Instructions:**
- DS-3-spec is primary authority for conflict-specific UI.
- Maintain consistency with FE-1 and FE-2.
- Conflict indicators must work within the existing navigation components from FE-1.

**Acceptance Criteria:**
- Conflict indicators appear at correct navigation levels per DS-3
- Resolved view renders per DS-3 layout
- Conflict detail view matches DS-3
- Can navigate from door to its conflict items and back
- Conflict list shows correct grouping/filtering per DS-3

**Estimated Effort:** 1 agent, 3–4 days

---

## Phase 4: Resolution Workflow (Weeks 11–13)

### WP-12: Resolution and Acknowledgment Workflow API

**Goal:** Humans can resolve conflicts and acknowledge changes, creating decision items and updating lifecycle snapshots.

**Scope:**
- `POST /api/items/:conflict_id/resolve` — create decision item, create resolution snapshot on conflict (per Decision 2: source_id = decision_id)
- `POST /api/items/:change_id/acknowledge` — upsert change snapshot with ACKNOWLEDGED status
- `POST /api/action-items/bulk-resolve` — resolve multiple conflicts at once
- Decision items with self-sourced snapshots (chosen_value, chosen_source, rationale, method, decided_by)
- Conflict snapshot lifecycle: DETECTED → RESOLVED (via decision as source)
- Change snapshot lifecycle: DETECTED → ACKNOWLEDGED (upsert is fine here — simpler lifecycle)
- Notifications on resolution/acknowledgment

**Inputs:** WP-11 (conflict items), WP-9 (change items), WP-5 (snapshot CRUD)

**Outputs:**
- Resolve endpoint: creates decision item + snapshot, creates resolution snapshot on conflict with `source_id = decision_id`
- Acknowledge endpoint: upserts change snapshot to ACKNOWLEDGED
- Bulk resolve endpoint: handles batch operations with partial failure reporting
- Notification creation on resolution (connected to relevant items)

**Test Scenario:**
1. Conflict "Door 101 / finish" exists (schedule says "stain", spec says "paint")
2. User resolves: chosen_value = "stain", chosen_source = schedule, rationale = "per architect's email"
3. Verify: decision item created with snapshot, conflict has NEW snapshot with source_id = decision_id and status = RESOLVED
4. Verify: ORIGINAL conflict snapshot (status = DETECTED) still exists (not overwritten)
5. Verify: resolved view for Door 101's finish now shows status = "resolved"

**Acceptance Criteria:**
- Resolution creates decision item with proper connections (decision → conflict, decision → affected item, decision → chosen source)
- Conflict now has TWO snapshots at the same context: detection (source=self) and resolution (source=decision)
- Resolved view correctly picks up the decision and shows "resolved" status
- Bulk resolve handles 20+ conflicts in a single operation
- Acknowledged changes show updated status in their snapshot

**Estimated Effort:** 1 agent, 3–4 days

---

### WP-13a: Dashboard and Rollup API

**Goal:** Backend endpoints for project health, import summaries, and action item rollups.

**Scope:**
- `GET /api/dashboard/import-summary` — most recent import's results
- `GET /api/dashboard/health` — project-level summary (total items by type, action item counts, breakdowns)
- `GET /api/action-items` — list with rollup (by_type, by_affected_type, by_property, by_source_pair)
- Temporal trend query: conflict/change counts at each milestone

**Inputs:** WP-12 (resolution data for status counts), WP-4 (navigation for drill-down links)

**Outputs:**
- Dashboard API endpoints
- Rollup response models
- Unit tests with realistic data

**Acceptance Criteria:**
- Health endpoint returns correct counts for all item types and action item statuses
- Rollup breakdowns are accurate (by_type, by_affected_type, by_property, by_source_pair)
- Import summary reflects the most recent import accurately
- Temporal trend returns correct conflict counts at each milestone

**Estimated Effort:** 1 agent, 2–3 days

---

### DS-4: Resolution Workflow and Dashboard Design ⬤ DESIGN SESSION

**Goal:** Design the resolution interaction and the executive dashboard.

**Participants:** Nick + Claude

**Reference Material:**
- DS-1 through DS-3 outputs
- WP-12 resolution API (what data the resolution flow needs)
- WP-13a dashboard API (what rollups are available)

**Agenda / Questions to Resolve:**

1. **Resolution interaction:**
   - What does the moment of decision look like? Dialog? Inline? Dedicated view?
   - How do you present the choice? "Pick Source A or Source B" vs. "Enter the correct value"?
   - Rationale entry: required or optional? Free text or structured?
   - What feedback does the user get after resolving? (Conflict disappears? Status change? Animation?)
   - How does bulk resolution work? Select multiple from a list? "Resolve all like this"?

2. **Change acknowledgment:**
   - Is this a one-click action or does it require confirmation?
   - Where does it appear? On the change item? On the affected item's resolved view?

3. **Dashboard — the executive view:**
   - What does a PM or principal see when they open Cadence?
   - Is the dashboard the entry point, or is navigation the entry point with dashboard as a tab/view?
   - What are the "cards" or "widgets"? Total counts? Trend charts? Recent activity?
   - How does drill-down work from dashboard to specific items? (Clicking "30 conflicts" → where does it go?)
   - Is the dashboard per-project or cross-project?

4. **Decision history:**
   - Where does the decision audit trail live? On the conflict? On the affected item? Separate view?
   - How important is the "story of resolution" vs. just the outcome?

**Outputs:**
- **UX Specification Document (DS-4-spec):** Includes:
  - Resolution dialog/interaction layout
  - Bulk resolution interaction
  - Change acknowledgment interaction
  - Dashboard layout, card/widget inventory, drill-down behavior
  - Decision history display

**Timing:** Should happen during Weeks 11–12, while WP-12 and WP-13a are being built.

---

### FE-4: Resolution UI and Dashboard Implementation

**Goal:** Implement resolution workflow and dashboard exactly as specified in DS-4.

**Inputs:**
- DS-4 UX specification
- DS-1 through DS-3 specifications (consistency)
- WP-12 resolution API
- WP-13a dashboard API

**Scope:**
- Resolution dialog per DS-4
- Bulk resolution interaction per DS-4
- Change acknowledgment per DS-4
- Dashboard page per DS-4 (summary statistics, rollup breakdowns, drill-down)
- Decision history display per DS-4
- Click-through from dashboard to filtered action item views per DS-4

**Agent Instructions:**
- DS-4-spec is primary authority.
- Dashboard drill-down must integrate with the navigation system from FE-1.
- Resolution flow must update the conflict display from FE-3 (status change visible immediately).

**Acceptance Criteria:**
- Resolution interaction matches DS-4 layout and flow
- After resolution, conflict status updates immediately in navigation
- Bulk resolution works per DS-4
- Dashboard displays correct data per DS-4 layout
- Dashboard drill-down navigates to filtered views per DS-4
- Decision history visible per DS-4

**Estimated Effort:** 1 agent, 4–5 days

---

## Phase 5: Polish and Hardening (Weeks 14–18)

### WP-14: Search, Permissions, and Error Handling

- Full-text search across item properties (GIN index already exists)
- Permission checking on API endpoints (scoped to project items)
- Comprehensive error handling: graceful failures, meaningful messages, no stack traces to client
- Input sanitization and validation tightening
- API rate limiting (basic)

### WP-15: Multi-Project Support and User Management

- Project list with creation
- User invitation and role assignment
- Per-project permissions enforcement
- Project switching in the UI

### WP-16: Advanced Import Features

- Fuzzy matching UI: when import finds no exact/normalized match, show candidates with similarity scores
- Dimension normalization: parse all common door dimension formats
- Import history: view past imports for a source, compare what changed between imports
- Import preview: dry-run mode that shows what will happen without committing

### WP-17: Performance Measurement and Optimization

- Instrument all API endpoints with timing
- Load test with Phase 1 targets (10K items, 50K connections, 100K snapshots)
- Identify bottlenecks from real query patterns
- Add indexes or materialized views only where measured data demands it
- Effective value caching if resolved view computation exceeds 200ms

---

## Timeline Summary

| Week | Backend Work | Design Session | Frontend Work | Key Deliverable |
|------|-------------|----------------|---------------|-----------------|
| 1 | WP-1, WP-2, WP-3 | — | — | Schema, CRUD, seed data |
| 2 | WP-4, WP-5 | **DS-1 begins** | — | Navigation API, snapshots |
| 3 | WP-6 | **DS-1 completes** | — | Import pipeline, design spec ready |
| 4 | WP-6 (continued) | — | **FE-1** | Import pipeline + navigation UI |
| 5 | WP-8, WP-9 | **DS-2 begins** | FE-1 (continued) | Comparison API, change detection |
| 6 | WP-9 (continued) | **DS-2 completes** | — | Change detection complete, design spec ready |
| 7 | — | — | **FE-2** | Comparison UI |
| 8 | WP-11 | **DS-3 begins** | — | Conflict detection |
| 9 | WP-11 (continued) | **DS-3 completes** | — | Conflict detection complete, design spec ready |
| 10 | (buffer) | — | **FE-3** | Conflict UI |
| 11 | WP-12 | **DS-4 begins** | — | Resolution API |
| 12 | WP-13a | **DS-4 completes** | — | Dashboard API, design spec ready |
| 13 | — | — | **FE-4** | Resolution UI + dashboard |
| 14–18 | WP-14–17 | — | Polish | Search, permissions, performance |

### Parallel Tracks

```
Backend:    ████████████████████░░░░░░░░ (Weeks 1–13, then polish)
Design:     ░░██░░░░██░░░░██░░░░██░░░░░░ (4 sessions, Weeks 2–3, 5–6, 8–9, 11–12)
Frontend:   ░░░░████░░████░░████░░░░████ (4 builds, each follows its design session)
```

**The backend never waits for design. The frontend never starts without design. Design sessions are the bridge.**

---

## Design Session Logistics

Each design session (DS-1 through DS-4) follows this structure:

1. **Prep (before session):** Claude reviews the relevant API outputs and spec sections. Nick gathers reference material from the original Cadence prototype (screenshots, notes, memories of what worked).

2. **Session (collaborative):** Working discussion to resolve the agenda questions. Output is captured in real-time as a design document. Expect 2–3 hours of focused work per session, potentially split across days.

3. **Refinement:** Design document is cleaned up and made specific enough for agent implementation. Any "TBD" items are resolved before the corresponding FE-X work package begins.

4. **Handoff:** Design spec is finalized. FE-X work package references it as the primary authority. Agent is instructed to implement it literally, not interpretively.

### What Makes a Good Design Spec for Agent Implementation

The output of each DS session needs to be prescriptive, not aspirational. Agents execute well when told exactly what to build. They fail when given vibes. Specifically:

- **Layout:** "The breadcrumb is a horizontal bar at the top of the content area, 48px tall, with 8px padding. Each segment is a clickable text link in 14px medium weight, separated by a chevron icon." NOT "The breadcrumb should be clean and minimal."

- **Interaction:** "Clicking a door row in the table pushes the door onto the breadcrumb and transitions to the door detail view with a 150ms slide-left animation." NOT "Navigation should feel smooth."

- **Information hierarchy:** "The property name is left-aligned in 14px regular weight. The value is right-aligned in 14px medium weight. Conflicted properties have a 2px left border in amber-500." NOT "Conflicts should be visually distinct."

- **What NOT to build:** "Do not add tooltips to property values. Do not use modals for navigation. Do not add a sidebar on mobile." Agents need negative constraints as much as positive ones.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Schema needs revision after real data | Medium | Low | Three tables are simple to migrate. Alembic handles it. |
| Change detection creates too much noise | Medium | Medium | Source-level tracking with affected counts. DS-2 addresses display. |
| False conflicts from normalization gaps | High | Medium | Aggressive normalization. Iterate in WP-16. |
| Design sessions take longer than expected | Medium | Medium | Backend continues regardless. Design sessions can split across multiple sittings. |
| Agent UI output doesn't match design spec | High | Medium | Prescriptive specs reduce ambiguity. Review catches drift. Iterate. |
| Nick's 15 hrs/week split between review + design | High | High | Design sessions are highest-value use of Nick's time. Backend review is lower-touch with clear acceptance criteria. |
| Original Cadence UX patterns don't map to v6.1 data model | Low | Medium | Design sessions address this explicitly. Some patterns may need rethinking. |

---

## Critical Paths

**Backend critical path:** WP-1 → WP-2 → WP-5 → WP-6 → WP-9 → WP-11 → WP-12 → WP-13a

**Frontend critical path:** DS-1 → FE-1 → DS-2 → FE-2 → DS-3 → FE-3 → DS-4 → FE-4

**The frontend path is longer** because design sessions are sequential (each builds on the last). This is intentional — you can't design the conflict UI without the navigation language established in DS-1. But the backend doesn't wait, so by the time DS-3 happens, the conflict detection API is already built and tested.

---

## What Success Looks Like at Each Phase

**Phase 1 (Week 4):** "I imported a door schedule and navigated from project to door. The navigation feels like the original Cadence but works on the new architecture. I can see what the schedule says about each door, attributed to the source."

**Phase 2 (Week 7):** "I imported the schedule again at a new milestone and can see exactly what changed. The comparison view tells the story clearly. Changes are tracked as items with their own narrative."

**Phase 3 (Week 10):** "I imported the spec and the system found 30 disagreements with the schedule. I can see both sources' values for every door. Conflicts surface naturally through navigation."

**Phase 4 (Week 13):** "I resolved the conflicts, and the decisions are part of the story. The dashboard gives me the executive view. The full loop works, and it feels like Cadence."

**Phase 5 (Week 18):** "Multiple projects, multiple users, handles real data volumes, ready for external feedback."
