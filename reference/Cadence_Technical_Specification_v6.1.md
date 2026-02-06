# Cadence Technical Specification v6.1
## A Unified Graph Architecture for Temporal Data Reconciliation

---

## Changelog from v6

This version incorporates architectural decisions made during technical review. The core three-table model is preserved; the changes sharpen the data model and resolve ambiguities that would have surfaced during implementation.

1. **Source-attributed snapshots.** The snapshot key is now `(item_id, context_id, source_id)` — what, when, who says. Every assertion in the system is fully attributed. This enables direct conflict detection by comparing snapshots from different sources for the same item at the same time context.

2. **Phase vs. milestone distinction.** Phases are temporal containers (Design Development, Construction Documents). Milestones are the discrete temporal anchors that serve as snapshot contexts (25%DD, 50%DD, DD). A phase connects to its milestones. Only milestones serve as `context_id` in snapshots.

3. **Conflict resolution is temporal.** Conflicts, changes, and decisions get snapshots using the same (what, when, who) pattern. The story of a conflict — from detection through acknowledgment through resolution — is tracked as temporal evolution, not status mutation.

4. **Source self-snapshots.** Sources (schedules, specifications) get their own snapshots tracking metadata evolution. "The schedule grew from 100 to 150 doors between DD and CD" is a first-class temporal assertion.

5. **Self-sourced items.** User-created items (rooms, buildings, manually entered data) use `source_id = item_id`. The item is its own authority. No nulls, no special cases.

6. **Bounce-back navigation.** Clicking a sibling item (one that shares an ancestor) auto-pops the breadcrumb to the shared ancestor and pushes the new target, enabling lateral movement without breaking breadcrumb semantics.

7. **Import mapping configuration.** Property mapping is shared responsibility — system normalizes standard patterns (case, whitespace, dimensions), user configures non-obvious column-to-property mappings.

8. **No concurrent imports.** Single-writer model. One import at a time per project.

---

## Executive Summary

Cadence v6.1 is a data reconciliation system for construction projects that tracks how things change over time and surfaces disagreements between data sources. It solves a fundamental problem: **everyone ignores time**. Current tools show end states. Cadence tells the story of how projects evolve — what changed, what disagrees, and what decisions were made along the way.

### The Core Architecture

The entire system is built on three primitives:

- **Items** — everything is an item (doors, rooms, milestones, schedules, conflicts, changes, decisions, notes)
- **Connections** — semantically minimal, directional relationships between items
- **Snapshots** — what an item looks like at a point in time, according to a specific source

Three database tables. No type hierarchies. No separate subsystems for conflicts, provenance, or workflow. Everything is expressed as items in a graph with connections and source-attributed temporal snapshots.

### The Snapshot Triple: What, When, Who Says

Every snapshot answers three questions:

- **What** — which item is being described (`item_id`)
- **When** — at which point in time (`context_id`, always a milestone)
- **Who says** — which source is making this assertion (`source_id`)

This triple is the foundation of the entire system. Conflict detection compares snapshots with matching (what, when) but different (who says). Change detection compares snapshots with matching (what, who says) but different (when). The same structure powers both — one unified model.

### What Changed from v5.1

v5.1 had 13+ tables, two fundamental types (TIME and ENTITY), a property authority scoring system, and a parallel conflict resolution subsystem. v6.1 collapses all of this into three tables and one unified model. The key breakthroughs:

1. **TIME and ENTITY are no longer distinct types.** Time contexts are just items with a temporal configuration flag. The need for a separate type disappeared once we unified temporal changes and source conflicts into the same detection model.

2. **Conflicts, changes, and decisions are items in the graph.** Not a parallel system — the same items, connections, and snapshots that represent doors and rooms also represent the conflicts between them and the decisions that resolved those conflicts.

3. **No automatic authority resolution.** v5.1 tried to pick winners automatically using proximity/specificity scoring. v6.1 shows disagreements directly and lets humans decide. The system doesn't pick sides — it surfaces the truth.

4. **Connections are semantically minimal.** Item types carry the semantic meaning. A door connected to a room and a door connected to a specification are both just connections — the semantic difference is that one endpoint is a room and the other is a specification. Connection `properties` exist for metadata when needed, but connection type is not a query filter.

5. **Navigation is a breadcrumb stack over a flat graph.** The graph has no inherent hierarchy. Navigation imposes a linear, hierarchical experience through the breadcrumb. Users drill in and back out. The graph allows traversal in any direction; the UI constrains it to feel natural.

---

## Core Principles

### 1. Everything Is an Item

There is one kind of thing in the system: an item. Items have a type tag that determines how they render and behave in the UI, but structurally they are all identical.

```
Physical things:   door, room, floor, building
Documents:         schedule, specification, drawing
Time contexts:     milestone, phase, import_batch
Workflow:          conflict, change, decision, note
Organization:      project, portfolio, firm
```

Adding a new category of data (windows, finishes, lighting, cost items) is a configuration change, not a schema change. Types are not hardcoded — the examples above are starting configurations, not architectural constraints.

### 2. Connections Are Semantically Minimal

Two items are either connected or they aren't. The connection has a direction (source → target) that provides a navigation convention.

The semantic meaning of a connection is determined by the types of the items it joins:

- Door → Room: spatial containment
- Schedule → Door: document listing
- Conflict → Door: conflict affecting this door
- Decision → Conflict: resolution of this conflict
- Milestone → Phase: temporal containment

Connection `properties` (JSONB) exist for metadata when needed — when the connection was established, why, any notes about it. But connection type is not a first-class query filter. Navigation and conflict detection operate on item types and snapshot contents, not connection semantics.

This eliminates connection type proliferation. You never need to decide whether a relationship is `contains` vs `specifies` vs `references`. The item types and snapshot contents already tell you.

### 3. Navigation Feels Hierarchical; The Graph Is Flat

Users experience Cadence as a drill-down hierarchy with a breadcrumb trail. They click into a project, then a building, then a floor, then a room, then a door. The breadcrumb tracks their path. "Back" pops the stack. Clicking a breadcrumb segment jumps back to that point.

But the underlying graph is flat. Door 101 is connected to Room 203 (spatial), Schedule Rev C (document), Spec Section 08 (specification), and a conflict item (workflow). When a user is AT Door 101, they can visit any of these connected items by clicking — each click pushes onto the breadcrumb.

The critical constraint: **you cannot reach an ancestor in your breadcrumb without backtracking.** If you navigated Project → Building → Floor → Room → Door, you can't jump to the Project from the Door. You back up through Room, Floor, Building. This makes navigation feel linear even over a non-linear graph.

**Bounce-back navigation for siblings:** When clicking an item that isn't directly reachable as a child of the current item but shares an ancestor in the breadcrumb, the system auto-pops to the shared ancestor and pushes the new target. Example:

```
Before: Project → Building → Floor → Room 203 → Door 101
User clicks Door 102 (connected to Room 203, not to Door 101)
After:  Project → Building → Floor → Room 203 → Door 102
```

The algorithm:
1. User clicks target item
2. Is target directly connected to current item AND not in breadcrumb? → Push (normal navigation)
3. Otherwise, walk backward through breadcrumb ancestors
4. Find the most recent ancestor connected to the target
5. Pop to that ancestor, push target
6. If no ancestor connects to target → handle gracefully (offer search or reset)

This enables lateral movement without breaking the semantic coherence of the breadcrumb.

**The diamond pattern is navigable:**

```
         Project
        /       \
   Schedule    Spec
        \       /
        Door 101
```

From Door 101, both Schedule and Spec are directly connected — one hop away. The user can visit Schedule (push onto breadcrumb), back up to Door 101, then visit Spec (push onto breadcrumb). They've explored both sides of the diamond through linear navigation.

### 4. A Value Is Current Until Superseded

When a schedule is imported at DD saying Door 101's finish is "paint," that value stands as the current truth of the schedule until a newer import replaces it. If no new schedule is imported at CD, the DD value remains active. It is not "stale" — it is the schedule's current position.

This means conflict detection at CD compares the spec's new CD values against the schedule's still-active DD values. If they disagree, that's a genuine conflict. The schedule hasn't changed its mind — it still says "paint."

With source-attributed snapshots, this is explicit: the schedule's snapshot for Door 101 at DD is the most recent snapshot from that source. If no CD snapshot exists from the schedule, the DD snapshot is the effective value.

### 5. Changes and Conflicts Are Peer-Level Action Items

Both are things that need human attention. Both are stored as items in the graph. Both appear in executive summaries. Both are navigable through the same breadcrumb model. Both have their own temporal story told through snapshots.

**Change:** A source's value evolved from one time context to the next. "The schedule changed Door 101 from wood to metal."

**Conflict:** Two sources disagree about a value at the current state. "The schedule says metal, the spec says hollow metal."

A change can cause a conflict. A conflict requires a decision. A decision can cause a new conflict if stakeholders disagree. The system handles all of these with the same three primitives.

### 6. Nothing Is Deleted, Only the Story Grows

No hard deletes. Removing a connection creates a record of the disconnection. Resolving a conflict creates a decision item and a new snapshot on the conflict. Superseding a value creates a new snapshot. The complete history is always available.

The story of a conflict — detection, discussion, acknowledgment, resolution — is itself a temporal narrative told through snapshots on the conflict item using the same (what, when, who) pattern as everything else.

### 7. Rollup Through Navigation

Executive summaries don't require a separate aggregation system. The graph structure IS the grouping:

```
Project Alpha — CD Import Summary:
  Doors:           100 changes, 30 conflicts
  Specifications:    3 changes, 30 conflicts

Click "Doors — 100 changes":
  Hardware changes:  32
  Finish changes:    50
  Frame changes:     18

Click "Finish changes — 50":
  Door 101: paint → stain
  Door 102: paint → stain
  Door 103: paint → stain (with conflict)
  ...
```

This is breadcrumb navigation filtered to change and conflict items. Same UX as navigating anything else. Counts are GROUP BY queries on connected item types.

### 8. Source-Level Change Tracking

When a specification section changes, that's one change — not 50 changes to 50 doors. The change item is created at the source (the spec section) and connected to all affected items (the doors). The executive summary reports "1 specification change affecting 50 doors" not "50 door changes."

This means the import logic distinguishes:
- **Where the value actually changed** → create change item at that source
- **What the change affects** → connect to affected items, count them
- **Whether the change creates disagreements** → create conflict items only where other sources disagree

### 9. Phases Contain Milestones; Milestones Anchor Snapshots

A **phase** is a temporal container: Design Development, Construction Documents, Construction Administration. Phases can span months. A phase is an item of type `phase`.

A **milestone** is a discrete temporal anchor within a phase: 25%DD, 50%DD, DD. Each milestone represents a specific submission or checkpoint. Milestones are the `context_id` in snapshots — the "when" of every assertion.

A phase connects to its milestones. A project connects to its phases. This gives the timeline a natural two-level structure:

```
Project Alpha
  └→ Design Development (phase)
       └→ 25%DD (milestone)
       └→ 50%DD (milestone)
       └→ DD (milestone)
  └→ Construction Documents (phase)
       └→ 50%CD (milestone)
       └→ CD (milestone)
```

Small projects with a single submission per phase have one milestone per phase. Large projects with progressive submissions have many. The system accommodates both without special-casing.

**Milestone identity:** A milestone's identifier must be unique within a project. If a user imports at a milestone name that already exists, they receive a confirmation dialog: overwrite (upsert the snapshot), rename (create a new milestone), or cancel.

---

## Data Model

### Schema

```sql
-- ============================================================
-- ITEMS: Everything is an item
-- ============================================================
CREATE TABLE items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_type VARCHAR(50) NOT NULL,
    identifier VARCHAR(200) NOT NULL,
    properties JSONB DEFAULT '{}',

    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Primary query patterns
CREATE INDEX idx_items_type ON items(item_type);
CREATE INDEX idx_items_identifier ON items(identifier);
CREATE INDEX idx_items_type_identifier ON items(item_type, identifier);

-- Full-text search on properties
CREATE INDEX idx_items_properties ON items USING gin(properties);

-- Normalized identifier for fuzzy matching
CREATE INDEX idx_items_normalized_id ON items(
    lower(regexp_replace(identifier, '[^a-zA-Z0-9]', '', 'g'))
);

-- ============================================================
-- CONNECTIONS: Semantically minimal, directional relationships
-- ============================================================
CREATE TABLE connections (
    source_item_id UUID NOT NULL REFERENCES items(id),
    target_item_id UUID NOT NULL REFERENCES items(id),
    properties JSONB DEFAULT '{}',

    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (source_item_id, target_item_id),
    CHECK (source_item_id != target_item_id)
);

-- Navigation in both directions
CREATE INDEX idx_connections_source ON connections(source_item_id);
CREATE INDEX idx_connections_target ON connections(target_item_id);

-- ============================================================
-- SNAPSHOTS: What, When, Who Says
-- ============================================================
-- Every snapshot answers three questions:
--   item_id    = WHAT is being described
--   context_id = WHEN (which milestone)
--   source_id  = WHO SAYS (which source is making this assertion)
--
-- Conflict detection: same (item_id, context_id), different source_id
-- Change detection:   same (item_id, source_id), different context_id
-- ============================================================
CREATE TABLE snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES items(id),
    context_id UUID NOT NULL REFERENCES items(id),
    source_id UUID NOT NULL REFERENCES items(id),
    properties JSONB NOT NULL,

    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(item_id, context_id, source_id)
);

CREATE INDEX idx_snapshots_item ON snapshots(item_id);
CREATE INDEX idx_snapshots_context ON snapshots(context_id);
CREATE INDEX idx_snapshots_source ON snapshots(source_id);
CREATE INDEX idx_snapshots_item_context ON snapshots(item_id, context_id);
CREATE INDEX idx_snapshots_item_source ON snapshots(item_id, source_id);
CREATE INDEX idx_snapshots_item_created ON snapshots(item_id, created_at DESC);
```

Three tables. That is the entire data model.

### The Snapshot Triple in Practice

**Import a door schedule at DD:**
```
For each door in the schedule:
  snapshot.item_id    = Door 101          (WHAT)
  snapshot.context_id = DD milestone      (WHEN)
  snapshot.source_id  = Finish Schedule   (WHO SAYS)
  snapshot.properties = { finish: "paint", material: "wood", hardware: "HW-1" }
```

**Import a specification at DD:**
```
For Door 101 referenced by the spec:
  snapshot.item_id    = Door 101          (WHAT)
  snapshot.context_id = DD milestone      (WHEN)
  snapshot.source_id  = Spec §08          (WHO SAYS)
  snapshot.properties = { finish: "stain", material: "wood" }
```

**Conflict detection:** Two snapshots exist for Door 101 at DD. Schedule says `finish: "paint"`. Spec says `finish: "stain"`. Different sources, same item, same time context → conflict.

**Change detection:** Later, the schedule is imported at CD with `finish: "stain"`. Compare snapshot (Door 101, DD, Schedule) with snapshot (Door 101, CD, Schedule). Same item, same source, different time context → change detected.

**Source self-snapshot:** The schedule itself gets a snapshot tracking its own metadata:
```
  snapshot.item_id    = Finish Schedule   (WHAT — the schedule itself)
  snapshot.context_id = DD milestone      (WHEN)
  snapshot.source_id  = Finish Schedule   (WHO SAYS — self-sourced)
  snapshot.properties = { row_count: 150, revision: "Rev C", columns: [...] }
```

**User-created items:** A room created manually by a user:
```
  snapshot.item_id    = Room 203          (WHAT)
  snapshot.context_id = DD milestone      (WHEN)
  snapshot.source_id  = Room 203          (WHO SAYS — self-sourced)
  snapshot.properties = { default_finish: "paint", area_sqft: 240 }
```

Self-sourced items have `source_id = item_id`. The item is its own authority. Since there's only one source, there's nothing to conflict with. The `created_by` field on the snapshot records which user made the entry.

### What Lives Where

**Item `properties`** — static or slowly-changing attributes that define the item's identity. A door's mark number, a project's name, a milestone's target date. Things that don't typically vary across time contexts or sources.

**Snapshot `properties`** — time-varying, source-attributed assertions. A door's finish at DD according to the schedule. A conflict's status at the time it was detected. A specification section's content at each revision.

**Connection `properties`** — metadata about the relationship itself. When the connection was established, why, any notes about it. Used sparingly.

### What About Users and Permissions?

Users and authentication live outside the three-table model. They're infrastructure, not domain data:

```sql
-- ============================================================
-- USERS: Authentication and identity (infrastructure)
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- PERMISSIONS: Access control (infrastructure)
-- ============================================================
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    scope_item_id UUID NOT NULL REFERENCES items(id),
    role VARCHAR(50) NOT NULL,
    can_resolve_conflicts BOOLEAN DEFAULT false,
    can_import BOOLEAN DEFAULT false,
    can_edit BOOLEAN DEFAULT false,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, scope_item_id)
);

CREATE INDEX idx_permissions_user ON permissions(user_id);
CREATE INDEX idx_permissions_scope ON permissions(scope_item_id);
```

Permissions scope to an item (typically a project). Users reference items through `created_by` fields but aren't items themselves — they're actors, not domain objects.

### Notifications

Notifications are transient system events, not part of the project story:

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    related_item_id UUID REFERENCES items(id),
    title VARCHAR(200) NOT NULL,
    message TEXT,
    is_read BOOLEAN DEFAULT false,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_unread
    ON notifications(user_id) WHERE is_read = false;
```

---

## Type Configuration

Item types are application configuration, not database schema. Adding a new type requires no migration. Types listed here are starting configurations, not architectural constraints — they can be added, renamed, or reorganized without schema changes.

```typescript
interface TypeConfig {
    icon: string;
    label: string;
    pluralLabel: string;
    renderMode: 'table' | 'cards' | 'list' | 'timeline';
    defaultSort?: string;
    searchFields?: string[];

    // Behavioral flags
    isTemporal?: boolean;            // Can serve as snapshot context_id
    isTemporalContainer?: boolean;   // Contains temporal items (rendered as timeline grouping)
    isActionItem?: boolean;          // Appears in executive summaries
    excludeFromConflicts?: boolean;  // Don't run conflict detection against this type
}

const TYPE_CONFIG: Record<string, TypeConfig> = {

    // --- Physical / spatial ---
    'project': {
        icon: 'folder',
        label: 'Project',
        pluralLabel: 'Projects',
        renderMode: 'cards',
        defaultSort: 'identifier',
        searchFields: ['identifier', 'properties.name'],
    },
    'building': {
        icon: 'building',
        label: 'Building',
        pluralLabel: 'Buildings',
        renderMode: 'cards',
        defaultSort: 'identifier',
    },
    'floor': {
        icon: 'layers',
        label: 'Floor',
        pluralLabel: 'Floors',
        renderMode: 'list',
        defaultSort: 'properties.level',
    },
    'room': {
        icon: 'layout',
        label: 'Room',
        pluralLabel: 'Rooms',
        renderMode: 'cards',
        defaultSort: 'identifier',
    },
    'door': {
        icon: 'door-open',
        label: 'Door',
        pluralLabel: 'Doors',
        renderMode: 'table',
        defaultSort: 'identifier',
        searchFields: [
            'identifier',
            'properties.finish',
            'properties.material',
            'properties.hardware',
        ],
    },

    // --- Documents ---
    'schedule': {
        icon: 'file-spreadsheet',
        label: 'Schedule',
        pluralLabel: 'Schedules',
        renderMode: 'table',
        defaultSort: 'identifier',
    },
    'specification': {
        icon: 'file-text',
        label: 'Specification',
        pluralLabel: 'Specifications',
        renderMode: 'list',
        defaultSort: 'identifier',
    },
    'drawing': {
        icon: 'file-image',
        label: 'Drawing',
        pluralLabel: 'Drawings',
        renderMode: 'cards',
        defaultSort: 'identifier',
    },

    // --- Temporal ---
    'milestone': {
        icon: 'calendar',
        label: 'Milestone',
        pluralLabel: 'Milestones',
        renderMode: 'timeline',
        defaultSort: 'properties.date',
        isTemporal: true,
    },
    'phase': {
        icon: 'clock',
        label: 'Phase',
        pluralLabel: 'Phases',
        renderMode: 'timeline',
        defaultSort: 'properties.start_date',
        isTemporalContainer: true,
    },
    'import_batch': {
        icon: 'upload',
        label: 'Import',
        pluralLabel: 'Imports',
        renderMode: 'list',
        defaultSort: 'created_at',
        isTemporal: true,
    },

    // --- Workflow / action items ---
    'change': {
        icon: 'arrow-right-left',
        label: 'Change',
        pluralLabel: 'Changes',
        renderMode: 'list',
        isActionItem: true,
        excludeFromConflicts: true,
    },
    'conflict': {
        icon: 'alert-triangle',
        label: 'Conflict',
        pluralLabel: 'Conflicts',
        renderMode: 'list',
        isActionItem: true,
        excludeFromConflicts: true,
    },
    'decision': {
        icon: 'check-circle',
        label: 'Decision',
        pluralLabel: 'Decisions',
        renderMode: 'list',
        isActionItem: true,
        excludeFromConflicts: true,
    },
    'note': {
        icon: 'message-square',
        label: 'Note',
        pluralLabel: 'Notes',
        renderMode: 'list',
        excludeFromConflicts: true,
    },
};
```

### Adding New Types

To support windows in addition to doors:

```typescript
'window': {
    icon: 'square',
    label: 'Window',
    pluralLabel: 'Windows',
    renderMode: 'table',
    defaultSort: 'identifier',
    searchFields: [
        'identifier',
        'properties.glazing_type',
        'properties.frame_material',
        'properties.dimensions',
    ],
},
```

No migration. No deployment. Create items with `item_type = 'window'` and they work.

---

## Core Operations

### Navigation

Navigation is a breadcrumb stack maintained on the client:

```typescript
interface NavigationState {
    breadcrumb: UUID[];

    currentItem(): UUID {
        return this.breadcrumb[this.breadcrumb.length - 1];
    }

    push(itemId: UUID): void {
        this.breadcrumb.push(itemId);
    }

    pop(): void {
        this.breadcrumb.pop();
    }

    popTo(index: number): void {
        this.breadcrumb = this.breadcrumb.slice(0, index + 1);
    }

    reset(itemId: UUID): void {
        this.breadcrumb = [itemId];
    }

    /**
     * Navigate to a target item. If the target is directly connected
     * to the current item and not already in the breadcrumb, push it.
     * Otherwise, find the nearest shared ancestor and bounce back.
     */
    async navigateTo(targetId: UUID, graph: GraphAPI): Promise<void> {
        // Don't navigate to self
        if (targetId === this.currentItem()) return;

        // Check if target is in breadcrumb (would create a cycle)
        const ancestorIndex = this.breadcrumb.indexOf(targetId);
        if (ancestorIndex >= 0) {
            // Target IS an ancestor — pop to it
            this.popTo(ancestorIndex);
            return;
        }

        // Check if target is directly connected to current item
        const directlyConnected = await graph.areConnected(
            this.currentItem(), targetId
        );

        if (directlyConnected) {
            this.push(targetId);
            return;
        }

        // Bounce-back: find nearest ancestor connected to target
        for (let i = this.breadcrumb.length - 2; i >= 0; i--) {
            const ancestorConnected = await graph.areConnected(
                this.breadcrumb[i], targetId
            );
            if (ancestorConnected) {
                this.popTo(i);
                this.push(targetId);
                return;
            }
        }

        // No ancestor connects to target — reset with target as root
        // (This shouldn't happen in normal navigation)
        this.reset(targetId);
    }
}
```

At each navigation step, the client requests connected items:

```
GET /api/items/:id/connected
    ?direction=outgoing
    &exclude=uuid1,uuid2,uuid3    // Breadcrumb ancestors
```

Response returns connected items grouped by `item_type`:

```json
{
    "item": {
        "id": "...",
        "item_type": "room",
        "identifier": "Room 203",
        "properties": { "default_finish": "paint" }
    },
    "connected": {
        "door": [
            { "id": "...", "identifier": "Door 101", "action_item_count": 2 },
            { "id": "...", "identifier": "Door 102", "action_item_count": 0 }
        ],
        "schedule": [
            { "id": "...", "identifier": "Finish Schedule Rev C" }
        ],
        "conflict": [
            { "id": "...", "identifier": "Door 101 / finish" }
        ],
        "change": [
            { "id": "...", "identifier": "Door 101 / material / DD→CD" }
        ]
    },
    "snapshots": [
        {
            "context": "DD",
            "source": "Finish Schedule",
            "properties": { "default_finish": "paint" }
        },
        {
            "context": "DD",
            "source": "Specification §09",
            "properties": { "default_finish": "stain" }
        },
        {
            "context": "CD",
            "source": "Finish Schedule",
            "properties": { "default_finish": "stain" }
        }
    ]
}
```

The UI groups connected items by type, using the type configuration for icons and rendering. Action items (changes, conflicts) can be shown as badges, counts, or inline — that's a design decision, not an architectural one.

Snapshots are now grouped by context AND source, reflecting the full (what, when, who) triple. The UI can display these as a matrix: rows = properties, columns = (context, source) pairs.

### Resolved View

With source-attributed snapshots, there's no single canonical snapshot per item per context. Instead, the UI computes a **resolved view** for display:

```typescript
interface ResolvedProperty {
    property: string;
    value: any;
    status: 'agreed' | 'resolved' | 'conflicted' | 'single_source';
    sources: Record<UUID, any>;     // source_id → value
    decision?: Item;                // If resolved, the decision item
}

async function getResolvedView(
    itemId: UUID,
    contextId: UUID
): Promise<ResolvedProperty[]> {

    // Get all snapshots for this item at this context
    const snapshots = await db.query(`
        SELECT s.source_id, s.properties,
               src.identifier as source_name, src.item_type as source_type
        FROM snapshots s
        JOIN items src ON src.id = s.source_id
        WHERE s.item_id = $1 AND s.context_id = $2
        AND src.item_type NOT IN ('change', 'conflict', 'decision', 'note')
    `, [itemId, contextId]);

    // Also check for effective values from prior contexts
    // (sources that haven't submitted at this context yet)
    const effectiveSnapshots = await getEffectiveSnapshots(itemId, contextId);

    // Merge all snapshots, collect all property paths
    const allProperties = collectAllPropertyPaths(snapshots, effectiveSnapshots);
    const results: ResolvedProperty[] = [];

    for (const prop of allProperties) {
        const sourceValues: Record<UUID, any> = {};

        for (const snap of [...snapshots, ...effectiveSnapshots]) {
            const val = extractProperty(snap.properties, prop);
            if (val !== undefined) {
                sourceValues[snap.source_id] = val;
            }
        }

        const uniqueValues = new Set(
            Object.values(sourceValues).map(v => canonicalize(v))
        );

        if (Object.keys(sourceValues).length === 1) {
            results.push({
                property: prop,
                value: Object.values(sourceValues)[0],
                status: 'single_source',
                sources: sourceValues,
            });
        } else if (uniqueValues.size === 1) {
            results.push({
                property: prop,
                value: Object.values(sourceValues)[0],
                status: 'agreed',
                sources: sourceValues,
            });
        } else {
            // Check for existing decision
            const decision = await getDecisionForConflict(itemId, prop);

            results.push({
                property: prop,
                value: decision ? decision.properties.chosen_value : null,
                status: decision ? 'resolved' : 'conflicted',
                sources: sourceValues,
                decision: decision || undefined,
            });
        }
    }

    return results;
}
```

For Phase 1 with bounded data sizes, this computes on every page load. Future optimization: a materialized effective-state cache updated on import and decision creation. Navigation reads from the cache; cache staleness is bounded by import frequency.

### Temporal Comparison

Comparison happens when a user selects multiple milestones as comparison anchors. With source-attributed snapshots, comparison can be filtered by source or aggregated across sources:

```typescript
async function compareAcrossTime(
    targetItemIds: UUID[],
    timeContextIds: UUID[],
    sourceFilter?: UUID         // Optional: compare a specific source's evolution
): Promise<ComparisonResult[]> {

    // Fetch all relevant snapshots in one query
    const snapshots = await db.query(`
        SELECT s.item_id, s.context_id, s.source_id, s.properties,
               ctx.identifier as context_name,
               ctx.properties->>'date' as context_date,
               src.identifier as source_name
        FROM snapshots s
        JOIN items ctx ON ctx.id = s.context_id
        JOIN items src ON src.id = s.source_id
        WHERE s.item_id = ANY($1)
        AND s.context_id = ANY($2)
        ${sourceFilter ? 'AND s.source_id = $3' : ''}
        ORDER BY ctx.properties->>'date' ASC
    `, sourceFilter
        ? [targetItemIds, timeContextIds, sourceFilter]
        : [targetItemIds, timeContextIds]
    );

    // Group by item, compare across contexts
    const byItem = groupBy(snapshots, 'item_id');
    const results: ComparisonResult[] = [];

    for (const [itemId, itemSnapshots] of byItem) {
        const changes = detectPropertyChanges(itemSnapshots, timeContextIds);

        results.push({
            itemId,
            category: categorize(itemSnapshots, timeContextIds),
            changes
        });
    }

    return results;
}

interface ComparisonResult {
    itemId: UUID;
    category: 'added' | 'removed' | 'modified' | 'unchanged';
    changes: PropertyChange[];
}

interface PropertyChange {
    property: string;
    oldValue: any;
    newValue: any;
    fromContext: UUID;
    toContext: UUID;
    source: UUID;           // Which source's value changed
}
```

The comparison is paginated at the database level — request items in batches, stream results to the UI.

### Import Flow

Import is the primary write operation. It creates source-attributed snapshots, detects changes, and detects conflicts. **Imports are single-writer per project** — no concurrent imports.

```typescript
interface ImportResult {
    dataSnapshots: number;
    sourceSnapshot: Item;
    changeItems: ChangeItem[];
    conflictItems: ConflictItem[];
    resolvedConflicts: number;
    summary: ImportSummary;
}

interface ImportSummary {
    itemsImported: number;
    sourceChanges: number;
    affectedItems: number;
    newConflicts: number;
    resolvedConflicts: number;
}

async function importFile(
    file: File,
    sourceItem: Item,        // e.g., Finish Schedule
    timeContext: Item,        // e.g., DD milestone (must have isTemporal: true)
    mappingConfig: ImportMappingConfig,
    importedBy: UUID
): Promise<ImportResult> {

    // Validate: timeContext must be a milestone (isTemporal), not a phase
    if (!TYPE_CONFIG[timeContext.item_type]?.isTemporal) {
        throw new Error('Time context must be a temporal item (milestone)');
    }

    const parsed = await parseAndMatch(file, sourceItem, mappingConfig);
    const changeItems: ChangeItem[] = [];
    const conflictItems: ConflictItem[] = [];
    let resolvedConflicts = 0;

    // Step 1: Create source-attributed snapshots for each target item
    for (const row of parsed.rows) {
        const targetItem = await getOrCreateItem(row);

        // Ensure connection exists: source → target
        await ensureConnection(sourceItem.id, targetItem.id, importedBy);

        // Create snapshot: (what=target, when=milestone, who=source)
        await upsertSnapshot(
            targetItem.id,    // what
            timeContext.id,    // when
            sourceItem.id,     // who says
            row.properties,
            importedBy
        );
    }

    // Step 2: Create source self-snapshot (the source's own metadata)
    await upsertSnapshot(
        sourceItem.id,         // what (the source itself)
        timeContext.id,         // when
        sourceItem.id,          // who says (self-sourced)
        {
            row_count: parsed.rows.length,
            columns_mapped: Object.keys(mappingConfig.property_mapping),
            import_date: new Date().toISOString(),
            file_name: file.name,
        },
        importedBy
    );

    // Step 3: Detect changes (this source's values at this milestone
    //         vs this source's values at its most recent prior milestone)
    const priorContext = await getMostRecentPriorContext(sourceItem.id, timeContext.id);

    if (priorContext) {
        for (const row of parsed.rows) {
            const targetItem = await getItemByIdentifier(row.identifier);

            // Get this source's prior snapshot for this item
            const priorSnapshot = await db.query(`
                SELECT properties FROM snapshots
                WHERE item_id = $1 AND context_id = $2 AND source_id = $3
            `, [targetItem.id, priorContext.id, sourceItem.id]);

            if (!priorSnapshot) continue;  // New item, no prior to compare

            const changes = diffProperties(priorSnapshot.properties, row.properties);
            if (Object.keys(changes).length > 0) {
                // Create change item with its own snapshot
                const changeItem = await createItem({
                    item_type: 'change',
                    identifier: `${sourceItem.identifier} / ${targetItem.identifier} / ${priorContext.identifier}→${timeContext.identifier}`,
                });

                // Snapshot on the change item: (what=change, when=milestone, who=change itself)
                await upsertSnapshot(
                    changeItem.id,      // what
                    timeContext.id,      // when
                    changeItem.id,       // who says (self-sourced)
                    {
                        status: 'DETECTED',
                        changes: changes,
                        from_context: priorContext.id,
                        to_context: timeContext.id,
                        source: sourceItem.id,
                        affected_item: targetItem.id,
                    },
                    importedBy
                );

                // Connect change to source, time contexts, and affected item
                await createConnection(changeItem.id, sourceItem.id, importedBy);
                await createConnection(changeItem.id, timeContext.id, importedBy);
                await createConnection(changeItem.id, priorContext.id, importedBy);
                await createConnection(changeItem.id, targetItem.id, importedBy);

                changeItems.push(changeItem);
            }
        }
    }

    // Step 4: Detect conflicts (this source vs other sources for same items)
    for (const row of parsed.rows) {
        const targetItem = await getItemByIdentifier(row.identifier);

        // Find all other source snapshots for this item
        // Use effective values: most recent snapshot per source
        const otherSnapshots = await db.query(`
            SELECT DISTINCT ON (s.source_id)
                s.source_id, s.properties, s.context_id,
                src.identifier as source_name, src.item_type as source_type
            FROM snapshots s
            JOIN items src ON src.id = s.source_id
            WHERE s.item_id = $1
            AND s.source_id != $2
            AND src.item_type NOT IN ('change', 'conflict', 'decision', 'note')
            ORDER BY s.source_id, s.created_at DESC
        `, [targetItem.id, sourceItem.id]);

        for (const otherSnap of otherSnapshots) {
            for (const [propPath, newValue] of Object.entries(row.properties)) {
                const otherValue = otherSnap.properties[propPath];

                if (otherValue === undefined) continue;  // Other source doesn't address this property

                if (!valuesEqual(newValue, otherValue)) {
                    // Disagreement — create conflict item with snapshot
                    const conflictItem = await getOrCreateConflict(
                        targetItem, propPath
                    );

                    // Snapshot on the conflict: (what=conflict, when=milestone, who=conflict itself)
                    await upsertSnapshot(
                        conflictItem.id,     // what
                        timeContext.id,       // when
                        conflictItem.id,      // who says (self-sourced)
                        {
                            status: 'DETECTED',
                            property_path: propPath,
                            values: {
                                [sourceItem.id]: newValue,
                                [otherSnap.source_id]: otherValue,
                            },
                            affected_item: targetItem.id,
                        },
                        importedBy
                    );

                    // Connect conflict to affected item, both sources, and milestone
                    await ensureConnection(conflictItem.id, targetItem.id, importedBy);
                    await ensureConnection(conflictItem.id, sourceItem.id, importedBy);
                    await ensureConnection(conflictItem.id, otherSnap.source_id, importedBy);
                    await ensureConnection(conflictItem.id, timeContext.id, importedBy);

                    conflictItems.push(conflictItem);

                } else {
                    // Agreement — check if this resolves an existing conflict
                    const existing = await getExistingConflict(targetItem.id, propPath);
                    if (existing) {
                        // Create resolution snapshot on the conflict
                        await upsertSnapshot(
                            existing.id,
                            timeContext.id,
                            existing.id,
                            {
                                status: 'RESOLVED_BY_AGREEMENT',
                                property_path: propPath,
                                agreed_value: newValue,
                                resolved_at: new Date().toISOString(),
                            },
                            importedBy
                        );
                        resolvedConflicts++;
                    }
                }
            }
        }
    }

    return {
        dataSnapshots: parsed.rows.length,
        sourceSnapshot: sourceItem,
        changeItems,
        conflictItems,
        resolvedConflicts,
        summary: {
            itemsImported: parsed.rows.length,
            sourceChanges: changeItems.length,
            affectedItems: new Set(changeItems.map(c => c.properties.affected_item)).size,
            newConflicts: conflictItems.length,
            resolvedConflicts,
        }
    };
}
```

### Import Mapping Configuration

Property mapping is shared responsibility. The system normalizes standard patterns; the user configures non-obvious mappings. The mapping is stored as a property on the source item and reused across imports:

```typescript
interface ImportMappingConfig {
    file_type: 'excel' | 'csv';
    identifier_column: string;          // Column containing item identifiers
    target_item_type: string;           // Type of items being imported (e.g., 'door')
    header_row?: number;                // Row number containing headers (default: 1)
    property_mapping: Record<string, string>;  // column_name → property_name
    normalizations?: Record<string, string>;   // property_name → normalization_type
}

// Example: Door schedule import mapping
const doorScheduleMapping: ImportMappingConfig = {
    file_type: 'excel',
    identifier_column: 'DOOR NO.',
    target_item_type: 'door',
    header_row: 1,
    property_mapping: {
        'FINISH': 'finish',
        'MATERIAL': 'material',
        'HW SET': 'hardware_set',
        'FRAME TYPE': 'frame_type',
        'SIZE': 'dimensions',
        'FIRE RATING': 'fire_rating',
    },
    normalizations: {
        'dimensions': 'imperial_door_dimensions',
        'finish': 'lowercase_trim',
        'material': 'lowercase_trim',
    },
};
```

The mapping lives as a property on the source item. Once configured for the first import, subsequent imports from the same source reuse it. The user can adjust if column names change.

**System-provided normalizations:**
- `lowercase_trim` — case-insensitive, whitespace-normalized
- `imperial_door_dimensions` — parse "3'-0\" x 7'-0\"" and similar formats
- `numeric` — handle string-encoded numbers

Non-obvious mappings (schedule calls it "FINISH", spec calls it "surface_treatment") are the user's responsibility to configure. The system will flag unmapped columns during import setup.

### Import Matching

Identifier matching uses aggressive normalization:

```typescript
function normalizeIdentifier(raw: string): string {
    return raw
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '')  // Strip all non-alphanumeric
        .trim();
}

// "Door 101" → "door101"
// "DR-101"   → "dr101"
// "DOOR 101" → "door101"
// "Dr. 101"  → "dr101"

async function matchItem(
    rawIdentifier: string,
    itemType: string
): Promise<{ item: Item; confidence: 'exact' | 'normalized' | 'fuzzy' } | null> {

    // Try exact match
    const exact = await db.query(
        'SELECT * FROM items WHERE identifier = $1 AND item_type = $2',
        [rawIdentifier, itemType]
    );
    if (exact) return { item: exact, confidence: 'exact' };

    // Try normalized match
    const normalized = normalizeIdentifier(rawIdentifier);
    const normMatch = await db.query(`
        SELECT * FROM items
        WHERE lower(regexp_replace(identifier, '[^a-zA-Z0-9]', '', 'g')) = $1
        AND item_type = $2
    `, [normalized, itemType]);
    if (normMatch) return { item: normMatch, confidence: 'normalized' };

    // Fuzzy match — return candidates for user confirmation
    const fuzzy = await db.query(`
        SELECT *, similarity(
            lower(regexp_replace(identifier, '[^a-zA-Z0-9]', '', 'g')),
            $1
        ) as sim
        FROM items
        WHERE item_type = $2
        AND similarity(
            lower(regexp_replace(identifier, '[^a-zA-Z0-9]', '', 'g')),
            $1
        ) > 0.7
        ORDER BY sim DESC
        LIMIT 5
    `, [normalized, itemType]);

    // Return null — caller should prompt user for confirmation
    return null;
}
```

Dimension reconciliation handles construction-specific formats:

```typescript
// "3'-0" x 7'-0""  → { width: 36, height: 84, unit: "inches" }
// "36" x 84""      → { width: 36, height: 84, unit: "inches" }
// "915 x 2134"     → { width: 915, height: 2134, unit: "mm" }

function normalizeDimension(raw: string): NormalizedDimension | null {
    // Try feet-inches pattern: 3'-0" x 7'-0"
    // Try inches pattern: 36" x 84"
    // Try metric pattern: 915 x 2134
    // Normalize to a canonical form for comparison
    // ... (domain-specific parsing logic)
}
```

### Value Comparison

Property comparison uses canonical normalization to avoid false conflicts:

```typescript
function valuesEqual(a: any, b: any): boolean {
    // Null handling
    if (a === null && b === null) return true;
    if (a === null || b === null) return false;

    // String comparison: case-insensitive, whitespace-normalized
    if (typeof a === 'string' && typeof b === 'string') {
        return a.trim().toLowerCase() === b.trim().toLowerCase();
    }

    // Numeric comparison: handle string-encoded numbers
    if (isNumeric(a) && isNumeric(b)) {
        return parseFloat(a) === parseFloat(b);
    }

    // Dimension comparison: normalize units
    const dimA = normalizeDimension(a);
    const dimB = normalizeDimension(b);
    if (dimA && dimB) {
        return dimensionsEqual(dimA, dimB);
    }

    // Object/array: deep equality with sorted keys
    return JSON.stringify(canonicalize(a)) === JSON.stringify(canonicalize(b));
}

function canonicalize(obj: any): any {
    if (typeof obj !== 'object' || obj === null) return obj;
    if (Array.isArray(obj)) return obj.map(canonicalize);

    // Sort keys for consistent comparison
    return Object.keys(obj).sort().reduce((acc, key) => {
        acc[key] = canonicalize(obj[key]);
        return acc;
    }, {} as Record<string, any>);
}
```

### Effective Value Resolution

A source's effective value for a property is its most recent snapshot for a given item. With source-attributed snapshots, this is a direct query:

```typescript
async function getEffectivePropertyValue(
    sourceId: UUID,
    itemId: UUID,
    propertyPath: string
): Promise<{ value: any; contextId: UUID } | null> {

    // Get the most recent snapshot from this source for this item
    const snapshot = await db.query(`
        SELECT s.properties, s.context_id
        FROM snapshots s
        WHERE s.item_id = $1
        AND s.source_id = $2
        ORDER BY s.created_at DESC
        LIMIT 1
    `, [itemId, sourceId]);

    if (!snapshot) return null;

    const value = snapshot.properties[propertyPath];
    if (value === undefined) return null;

    return { value, contextId: snapshot.context_id };
}
```

No ambiguity, no `extractPropertyForTarget` hand-wave. The snapshot directly associates a source's assertion about an item's properties. The query is a single indexed lookup.

---

## Item Patterns

### Change Items

Created when a source's value evolves between time contexts. The change item gets its own snapshot tracking its lifecycle:

```json
{
    "item_type": "change",
    "identifier": "Finish Schedule / Door 101 / DD→CD"
}
```

**Snapshot at CD (detection):**
```json
{
    "item_id": "<change UUID>",
    "context_id": "<CD milestone UUID>",
    "source_id": "<change UUID>",
    "properties": {
        "status": "DETECTED",
        "property_path": "finish",
        "old_value": "paint",
        "new_value": "stain",
        "from_context": "<DD milestone UUID>",
        "to_context": "<CD milestone UUID>",
        "source": "<schedule UUID>",
        "affected_item": "<Door 101 UUID>"
    }
}
```

**Snapshot at CD (after acknowledgment):**
```json
{
    "item_id": "<change UUID>",
    "context_id": "<CD milestone UUID>",
    "source_id": "<change UUID>",
    "properties": {
        "status": "ACKNOWLEDGED",
        "acknowledged_by": "<user UUID>",
        "acknowledged_at": "2024-02-01T10:30:00Z",
        "note": "Expected change per design review"
    }
}
```

**Connections:**
```
change → Finish Schedule    (source of the change)
change → DD milestone       (prior context)
change → CD milestone       (new context)
change → Door 101           (affected item)
```

### Conflict Items

Created when two sources disagree about a value. The conflict item's temporal story is told through snapshots:

```json
{
    "item_type": "conflict",
    "identifier": "Door 101 / finish"
}
```

**Snapshot at CD (detection):**
```json
{
    "item_id": "<conflict UUID>",
    "context_id": "<CD milestone UUID>",
    "source_id": "<conflict UUID>",
    "properties": {
        "status": "DETECTED",
        "property_path": "finish",
        "values": {
            "<schedule UUID>": "stain",
            "<spec UUID>": "paint"
        },
        "affected_item": "<Door 101 UUID>"
    }
}
```

**Snapshot at CD (after decision):**
```json
{
    "item_id": "<conflict UUID>",
    "context_id": "<CD milestone UUID>",
    "source_id": "<conflict UUID>",
    "properties": {
        "status": "RESOLVED",
        "property_path": "finish",
        "chosen_value": "stain",
        "chosen_source": "<schedule UUID>",
        "decision": "<decision UUID>",
        "resolved_by": "<user UUID>",
        "resolved_at": "2024-02-15T14:00:00Z"
    }
}
```

**Connections:**
```
conflict → Door 101         (affected item)
conflict → Finish Schedule  (source A)
conflict → Spec §08         (source B)
conflict → CD milestone     (detection context)
```

Note: the conflict's snapshot is upserted at the same context (CD) when it transitions from DETECTED to RESOLVED. This is an intentional design choice — we capture the conflict's state at the milestone, and the `created_at` timestamp on the snapshot distinguishes the original detection from the resolution. For richer history, an audit log (future enhancement) could capture every state transition.

### Decision Items

Created when a human resolves a conflict. The decision is also an item with its own snapshot:

```json
{
    "item_type": "decision",
    "identifier": "Door 101 / finish resolution"
}
```

**Snapshot at CD (creation):**
```json
{
    "item_id": "<decision UUID>",
    "context_id": "<CD milestone UUID>",
    "source_id": "<decision UUID>",
    "properties": {
        "chosen_value": "stain",
        "chosen_source": "<schedule UUID>",
        "rationale": "Per architect's email 2024-01-15, schedule takes precedence",
        "method": "MANUAL",
        "decided_by": "<user UUID>"
    }
}
```

**Connections:**
```
decision → conflict item    (what was resolved)
decision → Door 101         (affected item)
decision → Finish Schedule  (chosen source)
```

When a decision is created, the related conflict item's snapshot is upserted with `status: "RESOLVED"` and a reference to the decision. The decision itself is permanent — it's part of the story.

### Note Items

Annotations attached to anything:

```json
{
    "item_type": "note",
    "identifier": "Note on Door 101 finish"
}
```

**Snapshot (self-sourced):**
```json
{
    "item_id": "<note UUID>",
    "context_id": "<CD milestone UUID>",
    "source_id": "<note UUID>",
    "properties": {
        "content": "Architect confirmed stain finish in meeting 2024-01-20",
        "note_type": "DECISION"
    }
}
```

**Connections:**
```
note → Door 101            (subject)
note → conflict item       (related conflict, if any)
```

### Temporal Queries on Workflow Items

Because workflow items (changes, conflicts, decisions) use the same snapshot triple as everything else, temporal queries work uniformly:

```sql
-- "How many unresolved conflicts did we have at DD vs CD?"
SELECT
    s.context_id,
    ctx.identifier as milestone,
    COUNT(*) FILTER (WHERE s.properties->>'status' = 'DETECTED') as unresolved,
    COUNT(*) FILTER (WHERE s.properties->>'status' = 'RESOLVED') as resolved
FROM snapshots s
JOIN items i ON i.id = s.item_id
JOIN items ctx ON ctx.id = s.context_id
WHERE i.item_type = 'conflict'
AND s.source_id = s.item_id  -- self-sourced (the conflict's own snapshots)
AND s.context_id IN ($1, $2)  -- DD and CD milestone IDs
GROUP BY s.context_id, ctx.identifier;
```

```sql
-- "Show me the complete story of the Door 101 / finish conflict"
SELECT
    s.context_id,
    ctx.identifier as milestone,
    s.properties,
    s.created_at
FROM snapshots s
JOIN items ctx ON ctx.id = s.context_id
WHERE s.item_id = $1  -- conflict item ID
AND s.source_id = s.item_id
ORDER BY s.created_at ASC;
```

---

## API Design

### Navigation

```
# Get item detail with connected items
GET /api/items/:id/connected
    ?direction=outgoing|incoming|both
    &exclude=uuid1,uuid2,...         # Breadcrumb ancestors to exclude
    &types=door,schedule,...         # Filter by connected item types
    &include_action_counts=true      # Include change/conflict counts

# Search items
GET /api/items/search
    ?q=Door+101
    &type=door
    &project=uuid
```

### Import

```
# Import a file
POST /api/import
Body: {
    file: File,
    source_item_id: UUID,            # Schedule, spec, etc.
    time_context_id: UUID,           # Milestone (must be isTemporal)
    mapping_config?: ImportMappingConfig  # Optional: use stored config if omitted
}
Response: ImportResult

# Get/set import mapping for a source
GET /api/items/:source_id/import-mapping
PUT /api/items/:source_id/import-mapping
Body: ImportMappingConfig

# Get unmatched items from import (for user confirmation)
GET /api/import/:batch_id/unmatched
Response: Array<{
    raw_identifier: string,
    candidates: Array<{ item: Item, similarity: number }>
}>

# Confirm match
POST /api/import/:batch_id/confirm-match
Body: {
    raw_identifier: string,
    matched_item_id: UUID
}
```

### Temporal Comparison

```
# Compare items across time contexts
POST /api/compare
Body: {
    item_ids: UUID[],               # Items to compare (or connected to a parent)
    time_context_ids: UUID[],       # Milestones to compare across
    source_filter?: UUID,           # Optional: compare only this source's evolution
    parent_item_id?: UUID           # Alternative: compare all children of this item
}
Response: {
    results: ComparisonResult[],
    summary: {
        added: number,
        removed: number,
        modified: number,
        unchanged: number
    }
}
```

### Action Items (Changes, Conflicts, Decisions)

```
# List action items with filtering and rollup
GET /api/action-items
    ?project=uuid
    &types=change,conflict            # Filter by action item type
    &status=DETECTED,ACKNOWLEDGED     # Filter by status (from snapshots)
    &affected_type=door               # Filter by type of affected items
    &property_path=finish             # Filter by property
    &time_context=uuid                # Filter by detection context

Response: {
    items: ActionItem[],
    rollup: {
        by_type: { change: 100, conflict: 30 },
        by_affected_type: { door: 85, window: 15, room: 30 },
        by_property: { finish: 50, material: 32, hardware: 18 },
        by_source_pair: {
            "schedule+specification": 18,
            "schedule+drawing": 12
        }
    }
}

# Resolve a conflict (creates decision item + updates conflict snapshot)
POST /api/items/:conflict_id/resolve
Body: {
    chosen_value: any,
    chosen_source_id?: UUID,
    rationale?: string,
    time_context_id: UUID            # Milestone at which resolution occurs
}
Response: {
    decision: Item,
    conflict: Item,
    conflict_snapshot: Snapshot       # Updated snapshot showing resolution
}

# Acknowledge a change
POST /api/items/:change_id/acknowledge
Body: {
    note?: string,
    time_context_id: UUID
}
Response: {
    change: Item,
    change_snapshot: Snapshot         # Updated snapshot showing acknowledgment
}

# Bulk resolve
POST /api/action-items/bulk-resolve
Body: {
    item_ids: UUID[],
    chosen_value?: any,
    chosen_source_id?: UUID,
    rationale?: string,
    time_context_id: UUID
}
Response: {
    resolved: Item[],
    decisions: Item[],
    snapshots: Snapshot[],
    failed: Array<{ id: UUID, error: string }>
}
```

### Snapshots

```
# Get snapshots for an item (all sources)
GET /api/items/:id/snapshots
    ?contexts=uuid1,uuid2,...        # Specific time contexts
    &sources=uuid1,uuid2,...         # Specific sources

# Get resolved view for an item at a context
GET /api/items/:id/resolved
    ?context=uuid

# Create snapshot (manual)
POST /api/items/:id/snapshots
Body: {
    context_id: UUID,
    source_id: UUID,                 # Typically item_id for self-sourced
    properties: object
}

# Get effective value from a specific source
GET /api/items/:id/effective
    ?source=uuid
Response: {
    properties: object,
    as_of_context: Item,
    snapshot_created_at: Date
}
```

### Dashboard / Executive Summary

```
# Import summary
GET /api/dashboard/import-summary
    ?project=uuid
    &time_context=uuid

Response: {
    source_changes: number,
    affected_items: number,
    new_conflicts: number,
    resolved_conflicts: number,
    by_source: Array<{
        source: Item,
        changes: number,
        affected: number,
        conflicts: number
    }>
}

# Project health
GET /api/dashboard/health
    ?project=uuid

Response: {
    total_items: number,
    by_type: { [type: string]: number },
    action_items: {
        unresolved_changes: number,
        unresolved_conflicts: number,
        decisions_made: number,
    },
    by_property: { [property: string]: { changes: number, conflicts: number } },
    by_source_pair: { [pair: string]: { conflicts: number } }
}
```

### Items CRUD

```
# List items
GET /api/items
    ?type=door
    &project=uuid
    &search=Door+101

# Create item
POST /api/items
Body: {
    item_type: string,
    identifier: string,
    properties?: object
}

# Get item
GET /api/items/:id

# Update item properties
PATCH /api/items/:id
Body: {
    properties: object        # Merged with existing
}

# Connect two items
POST /api/connections
Body: {
    source_item_id: UUID,
    target_item_id: UUID,
    properties?: object
}

# Disconnect (soft — creates record)
POST /api/connections/disconnect
Body: {
    source_item_id: UUID,
    target_item_id: UUID,
    reason?: string
}
```

---

## Performance Characteristics

### Complexity Analysis

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Navigation (connected items) | O(C) | C = connections from current item |
| Resolved view | O(S × P) | S = sources for this item, P = properties |
| Temporal comparison | O(T × S × P) | T = time contexts, S = sources, P = properties |
| Import (per row) | O(S) | S = other sources connected to target |
| Conflict detection (per property) | O(S) | S = connected source count |
| Dashboard rollup | O(A) | A = action items (indexed query) |
| Search | O(log N) | N = total items (indexed) |
| Breadcrumb navigation step | O(C) | Single hop, one query |

### Why This Scales

**Bounded connectivity.** Construction items have low average degree. A door connects to perhaps 5-10 things (room, schedule, spec, a few milestones, a few action items). A specification section might connect to 50-200 items. These are small numbers for graph traversal.

**Bounded source count.** An item is rarely described by more than 3-5 sources (schedule, spec, drawing, plus maybe a submittal or two). The S factor in resolved view and conflict detection is small.

**Import-time computation.** Conflict and change detection runs once at import, not on every page view. After import, action items are stored and queryable without recomputation.

**Indexed queries for rollups.** Executive summaries use indexed GROUP BY queries on `item_type`, snapshot properties, etc. No graph traversal needed for counts.

**Paginated comparison.** Temporal comparison fetches snapshots in batches from the database, not all at once. The database does the heavy lifting with indexed lookups on `(item_id, context_id)`.

**Depth-bounded navigation.** The breadcrumb constrains traversal depth. Users rarely go deeper than 6-8 levels. Each step is a single indexed query for connected items.

### Database Indexes

The schema includes indexes for all primary query patterns:

```sql
-- Navigation: find connected items
CREATE INDEX idx_connections_source ON connections(source_item_id);
CREATE INDEX idx_connections_target ON connections(target_item_id);

-- Filtering: find items by type
CREATE INDEX idx_items_type ON items(item_type);

-- Snapshots: the three query patterns
CREATE INDEX idx_snapshots_item ON snapshots(item_id);
CREATE INDEX idx_snapshots_context ON snapshots(context_id);
CREATE INDEX idx_snapshots_source ON snapshots(source_id);

-- Conflict detection: find all source snapshots for an item
CREATE INDEX idx_snapshots_item_context ON snapshots(item_id, context_id);

-- Change detection: find a source's snapshots for an item over time
CREATE INDEX idx_snapshots_item_source ON snapshots(item_id, source_id);

-- Effective value: most recent snapshot from a source for an item
CREATE INDEX idx_snapshots_item_created ON snapshots(item_id, created_at DESC);

-- Search
CREATE INDEX idx_items_properties ON items USING gin(properties);
CREATE INDEX idx_items_normalized_id ON items(
    lower(regexp_replace(identifier, '[^a-zA-Z0-9]', '', 'g'))
);

-- Dashboard queries (action items by status via snapshots)
CREATE INDEX idx_items_active_action ON items(item_type, (properties->>'status'))
    WHERE item_type IN ('change', 'conflict', 'decision');
```

Additional indexes can be added based on observed query patterns once real usage data exists.

### Scalability Targets (Phase 1)

- **Items:** 10,000 (1,000 doors + rooms, schedules, milestones, action items)
- **Connections:** 50,000
- **Snapshots:** 100,000 (more than v6 due to source attribution — items × contexts × sources)
- **Sources per item:** 2-5 (bounded by document types)
- **Time Contexts:** 10-20 milestones
- **Query Response:**
  - Navigation: < 100ms
  - Resolved view: < 200ms
  - Simple comparison (2-3 time contexts): < 500ms
  - Import (1,000 items): < 30s
  - Dashboard: < 200ms

These are achievable with PostgreSQL on modest hardware without optimization. Scaling beyond this will be guided by real usage data, not speculation.

---

## Cycle Handling

The graph allows cycles. They are not prevented at the schema level (beyond the self-connection CHECK constraint). Cycles are semantically valid — a door is in a room, the room is on a floor, the floor is in a building, the building contains the schedule that lists the door. Following all connections without filtering produces a cycle, but that reflects reality.

Safety mechanisms:

**Depth-limited traversal.** All graph traversals use a maximum depth (default: 10). Sufficient for any real navigation path; prevents runaway recursion.

**Visited-node tracking.** Every traversal maintains a `visited` set. Encountering an already-visited node terminates that branch. Standard BFS/DFS with O(1) per check.

**Breadcrumb exclusion.** Navigation queries exclude breadcrumb ancestors from results. This prevents cycles from appearing in the UI — you can't "navigate forward" to somewhere you've already been.

```typescript
async function getConnectedItems(
    itemId: UUID,
    direction: 'outgoing' | 'incoming' | 'both',
    exclude: UUID[] = [],
    maxDepth: number = 1
): Promise<Item[]> {

    const visited = new Set(exclude);
    visited.add(itemId);

    const query = direction === 'outgoing'
        ? 'SELECT target_item_id FROM connections WHERE source_item_id = $1'
        : direction === 'incoming'
        ? 'SELECT source_item_id FROM connections WHERE target_item_id = $1'
        : `SELECT target_item_id as id FROM connections WHERE source_item_id = $1
           UNION
           SELECT source_item_id as id FROM connections WHERE target_item_id = $1`;

    const rows = await db.query(query, [itemId]);

    return rows
        .map(r => r.target_item_id || r.source_item_id || r.id)
        .filter(id => !visited.has(id));
}
```

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-4)
**Goal:** Prove the three-table schema works with real door schedule data.

- Database schema (items, connections, snapshots with source attribution + users, permissions, notifications)
- Basic CRUD API for items and connections
- Breadcrumb navigation with bounce-back (push, pop, sibling detection, connected items grouped by type)
- Import mapping configuration (user maps columns to properties)
- Import: parse Excel/CSV door schedules, create source-attributed snapshots
- Source self-snapshots on import
- Identifier matching (exact + normalized)
- **Deliverable:** Import a door schedule, navigate through Project → Building → Floor → Room → Door. See properties attributed to source. Navigate the breadcrumb with bounce-back.
- **Risk:** Schema needs revision. (Mitigation: three tables are simple to migrate.)

### Phase 2: Temporal Comparison (Weeks 5-7)
**Goal:** Prove snapshot comparison works and users can see changes over time.

- Phase and milestone items (phases contain milestones)
- Import at specific milestones (milestone as context_id)
- Temporal comparison API (compare a source's snapshots across 2-3 milestones)
- Change detection on import: create change items with self-sourced snapshots
- Comparison UI: side-by-side or diff view for an item across milestones
- **Deliverable:** Import Schedule at DD, import updated Schedule at CD, see what changed. Change items appear connected to affected doors. Changes have their own temporal snapshots.
- **Risk:** Change detection creates too much noise. (Mitigation: source-level tracking with affected counts.)

### Phase 3: Conflict Detection (Weeks 8-10)
**Goal:** Prove that surfacing source disagreements is valuable.

- Import from multiple sources (schedule + spec for same doors)
- Conflict detection on import: compare snapshots from different sources for same (item, context)
- Conflict items stored with self-sourced snapshots tracking their lifecycle
- Value comparison with normalization (case, whitespace, dimensions)
- Resolved view: display per-item properties with source attribution and conflict status
- Conflict visibility in navigation (badges/counts on affected items)
- **Deliverable:** Import schedule and spec for same project. Conflicts flagged where they disagree. Navigate to conflicts from affected doors. Each conflict shows which sources say what.
- **Risk:** Too many false conflicts from normalization issues. (Mitigation: aggressive normalization, fuzzy matching prompts for user confirmation.)

### Phase 4: Resolution Workflow (Weeks 11-13)
**Goal:** Prove the full loop of detect → review → resolve → track.

- Decision items created on conflict resolution (with self-sourced snapshots)
- Conflict snapshots updated on resolution (DETECTED → ACKNOWLEDGED → RESOLVED)
- Change acknowledgment workflow (change snapshots updated: DETECTED → ACKNOWLEDGED)
- Bulk resolution (resolve multiple conflicts at once)
- Executive dashboard: rollup by type, property, source pair
- Temporal queries on workflow items ("how did conflicts trend from DD to CD?")
- Notifications on conflict detection and resolution
- **Deliverable:** Full workflow from import through resolution. Dashboard shows project health. Every step in the workflow is part of the temporal story. Decisions are items with snapshots.
- **Risk:** Workflow is too cumbersome. (Mitigation: bulk operations, rollup navigation reduces noise.)

### Phase 5: Polish & Scale (Weeks 14-18)
**Goal:** Handle real-world complexity and prepare for multi-project use.

- Multi-project support
- Advanced search (full-text on properties)
- Fuzzy import matching with user confirmation UI
- Dimension normalization
- Permission model refinement
- Performance optimization based on real usage data
- Effective value caching (materialized resolved view)
- **Deliverable:** System handles multiple concurrent projects with different teams.

### Phase 6: Integration (Weeks 19-24)
**Goal:** Connect to external tools.

- Revit API integration (push resolved values)
- Export to Excel/CSV
- Webhook notifications
- API for third-party integrations
- **Deliverable:** Cadence as source of truth, connected to DCC tools.

---

## Future Enhancements

### Pattern Detection
- Identify recurring conflicts across projects ("the architect always forgets to update the spec for stained finishes")
- Track resolution patterns ("PM always sides with the schedule for finish properties")
- Surface anomalies in temporal evolution (near-reversions, oscillations)

### MasterFormat as Graph Organization

CSI MasterFormat is the industry-standard taxonomy that every architect, spec writer, and contractor already uses. Division 08 is Openings. 08 11 00 is Metal Doors and Frames. 08 71 00 is Door Hardware. The entire AEC industry already thinks in these numbers.

MasterFormat sections map naturally to items in the graph:

```
Specification (item)
  └→ Division 08 - Openings (item, identifier: "08")
       └→ 08 11 00 - Metal Doors and Frames (item, identifier: "081100")
       └→ 08 71 00 - Door Hardware (item, identifier: "087100")
       └→ 09 91 00 - Painting (item, identifier: "099100")
```

Each section connects to the physical items it specifies. Door 101 connects to 08 11 00 (the door itself), 08 71 00 (its hardware), and 09 91 00 (its finish). Those connections are the paths through which conflicts surface — when a spec section's values disagree with a schedule's values for the same door, the MasterFormat number identifies exactly which part of the spec is relevant.

This requires no schema changes. MasterFormat sections are items with a MasterFormat identifier. Navigation follows the existing breadcrumb model. The hierarchical numbering (08 → 08 71 → 08 71 00) provides a natural drill-down that every construction professional already knows.

The organizational principle extends beyond specifications. Submittals, RFIs, and change orders can all reference MasterFormat numbers, creating cross-document traceability through the graph. A change to Spec Section 08 71 00 is automatically connected to the submittal for that hardware, the doors it affects, and any RFIs that referenced it.

### ML-Assisted Specification Extraction

Specifications follow a predictable 3-part structure: Part 1 (General), Part 2 (Products), Part 3 (Execution). Property values that conflict with schedules and drawings almost always live in Part 2 — material types, finishes, dimensions, hardware specifications, fire ratings. This makes value extraction a bounded search problem, not an open-ended comprehension task.

An ML agent can:
- Given a MasterFormat section number and a property name (finish, material, hardware), locate the relevant value in Part 2 of that section
- Map extracted values to existing items in the graph via MasterFormat connections
- Flag spec revisions and predict which items and properties are affected before anyone imports the new version ("Spec Section 08 71 00 was revised — this likely affects hardware for 47 doors")

The feedback loop is built into the product. When the system extracts a value and creates a conflict, the human resolving that conflict implicitly validates or corrects the extraction. Every resolution is training data. The agent improves with use.

This layers cleanly on top of the core architecture. Phases 1-4 handle structured data (schedules as Excel/CSV). ML-assisted extraction extends the same import pipeline to semi-structured data (specifications as documents). The conflict detection infrastructure is identical regardless of whether values came from a human importing a spreadsheet or an agent parsing a specification.

### ML-Assisted Import (Structured Data)
- Learn column mappings from past imports
- Auto-detect identifier formats
- Suggest matches for fuzzy identifiers
- Flag likely errors (spelling, unit confusion, transposition)

### ML-Assisted Resolution
- Predict likely resolution based on historical decisions
- Suggest: "In 85% of similar conflicts, the schedule value was chosen"
- Reduce cognitive load without removing human judgment

### Advanced Temporal Features
- Branching timelines ("what if we went with the spec's values?")
- Timeline visualization across multiple sources
- Trend analysis ("finish changes are increasing — possible scope creep")

### Audit Log
- Append-only event log alongside the snapshot model
- Every state transition recorded: import, detection, acknowledgment, resolution
- Makes the "story" fully replayable without relying on snapshot upsert timestamps
- Low priority — snapshots provide sufficient history for Phase 1-4

---

## Technology Stack

- **Database:** PostgreSQL (with pg_trgm extension for fuzzy matching)
- **Backend:** FastAPI + SQLAlchemy (async)
- **Frontend:** React + TypeScript + Tailwind CSS
- **Deployment:** Docker Compose
- **Authentication:** TBD (JWT-based, standard approach)

### Why PostgreSQL

- Handles bounded graph traversal well via recursive CTEs
- JSONB provides flexible property storage with indexing
- pg_trgm extension enables fuzzy text matching for import
- GIN indexes enable full-text search on properties
- `UNIQUE(item_id, context_id, source_id)` enforces the snapshot triple at the database level
- Mature, boring, reliable — the family car engine
- Can add Apache AGE later for advanced graph queries if needed (without migration)

---

## Summary

Cadence v6.1 is three tables and a principle:

**Tables:** Items, Connections, Snapshots.

**Principle:** Everything is an item in a graph. Every assertion is a snapshot answering (what, when, who says). Changes and conflicts are detected at import and stored as items with their own temporal story. The graph is flat; navigation imposes hierarchy through a breadcrumb with bounce-back for lateral movement. Nothing is deleted; the story only grows.

The system surfaces two kinds of information that the construction industry currently ignores:

1. **How things change over time** — the story of a project's evolution, visible through temporal comparison of source-attributed snapshots.

2. **Where sources disagree** — conflicts between documents, specifications, and schedules, detected by comparing snapshots with matching (what, when) but different (who says).

Both are stored as items in the graph, with their own snapshots telling their own temporal stories. An executive sees rollup counts. A PM drills into specific conflicts. An architect navigates to a door and sees every source's assertion at every milestone, with conflicts and resolutions woven into the narrative. Same data, different paths, same breadcrumb.

Three tables. No type hierarchies. No authority scoring. No separate conflict subsystem. The snapshot triple — what, when, who says — unifies temporal tracking, conflict detection, and resolution workflow into a single model.
