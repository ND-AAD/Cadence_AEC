# Cadence v6.1 — Technical Onboarding Brief
## "Three Tables and a Triple"

---

## TL;DR

**What we're building:** A data reconciliation tool for construction projects that tracks how things change over time and flags conflicts between sources.

**The entire data model:** Three tables — items, connections, snapshots. Everything else is configuration.

**The snapshot triple:** Every snapshot answers (what, when, who says). Conflict detection and change detection both fall directly out of this structure.

**Core insight:** Construction ignores time AND ignores disagreements between documents. We surface both.

---

## The Architecture in 60 Seconds

Everything in Cadence is an **item** — a door, a room, a milestone, a schedule, a conflict, a decision. Items are connected to other items. Items have **snapshots** that capture what a source says about them at a point in time.

Every snapshot answers three questions:
- **What** is being described? (the item)
- **When?** (the milestone)
- **Who says?** (the source — a schedule, a spec, or the item itself for user-created data)

When you import a document (a door schedule, a specification), the system:
1. Creates source-attributed snapshots for each item
2. Detects **changes** — did this source's values change from last milestone?
3. Detects **conflicts** — does this source disagree with another source?
4. Stores changes and conflicts as items in the graph, with their own snapshots tracking their lifecycle

Users navigate a breadcrumb — click to drill in, back to go up, click a sibling to bounce back and sideways. At any item, you see everything connected to it: rooms, schedules, conflicts, changes. The graph is flat; the navigation feels hierarchical.

That's it. Three tables. Import detects problems. Navigation surfaces them. Decisions resolve them. Everything has a temporal story.

---

## Why Three Tables?

### Previous Architecture (v5.1): 13+ Tables

Scales, ScaleItems, ScaleConnections, ScaleSnapshots, PropertyResolutions, PropertySources, ConflictResolutions, ConflictNotes, PinnedValues, Notes, UserPermissions, Notifications, plus configuration tables.

Two separate subsystems: the data model and the conflict workflow. Two detection algorithms: temporal comparison and source conflict detection.

### Current Architecture (v6.1): 3 Tables

```sql
items       (id, item_type, identifier, properties, ...)
connections (source_item_id, target_item_id, properties, ...)
snapshots   (id, item_id, context_id, source_id, properties, ...)
```

The snapshot triple `(item_id, context_id, source_id)` is the key innovation. Every assertion is fully attributed:
- **Conflict detection:** same (item, context), different source → compare
- **Change detection:** same (item, source), different context → compare

Everything that was a separate table in v5.1 is now just a type of item:
- Conflicts → items of type `conflict` with self-sourced snapshots
- Decisions → items of type `decision` with self-sourced snapshots
- Changes → items of type `change` with self-sourced snapshots
- Notes → items of type `note`

They're connected to the things they relate to, they have snapshots tracking their evolution over time, and they're queryable with the same API as everything else.

### How We Got Here

The simplification came from three insights developed during architectural review:

1. **Time and source conflicts are the same problem.** "Door 101 changed from DD to CD" and "schedule disagrees with spec" are both cases of different contexts providing different values. The snapshot triple handles both: change = same (what, who), different when. Conflict = same (what, when), different who.

2. **The diamond problem IS the product.** When Door 101 is reachable via both the schedule path and the specification path, and those paths provide different values — that's not a bug to work around. That's the conflict we're trying to find.

3. **Navigation solves grouping.** Instead of building a conflict grouping algorithm, the graph structure itself groups things. "100 door changes" → click → "50 finish changes" → click → individual changes. Same breadcrumb navigation as everything else.

---

## Questions You're Probably Asking

### "How does navigation work if the graph is flat?"

The graph has no hierarchy. But the UI does. Users experience a breadcrumb:

```
Project Alpha → Building A → Floor 2 → Room 203 → Door 101
```

At each level, they see connected items grouped by type. Click one to push onto the breadcrumb. Click a breadcrumb segment to pop back. Can't jump forward to an ancestor — you must backtrack.

**Siblings:** Clicking an item that shares an ancestor with the current position auto-pops to the shared ancestor and pushes the new target. From Door 101, clicking Door 102 bounces back to Room 203 and pushes Door 102:

```
Before: Project → Building → Floor → Room 203 → Door 101
After:  Project → Building → Floor → Room 203 → Door 102
```

The key insight: when you're at Door 101, you can see both Schedule Rev C and Spec §08 as connected items — they're one hop away. Click either one. This lets users explore the "diamond" (two paths to the same item) through natural navigation.

### "How are conflicts detected?"

At import time, the system checks: for each item being imported, do snapshots from other sources provide different values for the same property? The snapshot triple makes this a direct comparison — same (item, context), different source.

No scoring. No automatic winner selection. The conflict just shows: "Schedule says stain. Spec says paint." A human decides.

### "What's the difference between a phase and a milestone?"

A **phase** is a temporal container — Design Development, Construction Documents. Phases can span months. A **milestone** is a discrete checkpoint within a phase — 25%DD, 50%DD, DD. Milestones are the "when" in the snapshot triple. A phase connects to its milestones.

Small project: one milestone per phase. Large project: multiple milestones per phase. No special-casing required.

### "What if only one source is submitted at a milestone?"

The last known value IS the current value until superseded. If the schedule was imported at DD and the spec is imported at CD, the schedule's DD snapshot is still the effective value. If the spec disagrees, that's a real conflict — the schedule hasn't changed its mind.

### "Won't there be too many changes and conflicts?"

Changes are tracked at the source level, not the item level. When a spec section changes, that's ONE change item — connected to all 50 affected doors. The dashboard shows "1 spec change affecting 50 doors," not "50 door changes."

Conflicts only exist where sources genuinely disagree. If only one source provides a value for a property, there's nothing to conflict with.

### "What about workflow items — how do they evolve?"

Conflicts, changes, and decisions are items with their own self-sourced snapshots. A conflict's lifecycle is itself a temporal story:

```
Conflict "Door 101 / finish":
  Snapshot at CD (detection): { status: "DETECTED", values: { schedule: "stain", spec: "paint" } }
  Snapshot at CD (resolution): { status: "RESOLVED", chosen_value: "stain", decided_by: "PM" }
```

You can ask: "How many unresolved conflicts did we have at DD vs CD?" — standard temporal comparison on conflict-type items.

### "What about cycles in the graph?"

We allow them. Safety: depth-limited traversal (max 10 hops), visited-node tracking, breadcrumb exclusion. Standard graph traversal, nothing exotic.

### "How does this perform?"

Import-time computation means we don't re-detect conflicts on every page view. Navigation is one indexed query per breadcrumb step. Dashboard rollups are GROUP BY on indexed columns.

Phase 1 targets: 1,000 doors, < 100ms navigation, < 30s import.

PostgreSQL handles this comfortably. We'll optimize based on real usage data, not speculation.

---

## What We've Validated

1. ✅ **Core concept:** Door schedule prototype was well received by architects
2. ✅ **Non-architects liked it too:** The "story" concept has broad appeal
3. ✅ **Import workflow:** Excel → system worked smoothly
4. ✅ **Temporal comparison:** Users understood and valued seeing changes over time
5. ✅ **User need:** Construction industry genuinely ignores time and conflicts

---

## What We're Building Incrementally

**Phase 1 (Weeks 1-4):** Foundation
- Three-table schema with source-attributed snapshots, basic CRUD, breadcrumb navigation with bounce-back
- Import door schedules with mapping configuration, navigate the graph
- Prove: the schema works

**Phase 2 (Weeks 5-7):** Temporal Comparison
- Phases and milestones, snapshots at milestones, compare across time
- Change detection on import, change items with their own snapshots
- Prove: users can see the story

**Phase 3 (Weeks 8-10):** Conflict Detection
- Import multiple sources, detect disagreements via snapshot comparison
- Conflict items with temporal lifecycle, resolved view showing all sources
- Prove: surfacing conflicts is valuable

**Phase 4 (Weeks 11-13):** Resolution Workflow
- Decisions as items with snapshots, conflict lifecycle tracking
- Bulk resolution, dashboard, full detect → review → resolve → track loop
- Prove: the workflow is usable and the resolution is part of the story

Each phase proves a hypothesis. If we're wrong, we learn early.

---

## Red Flags to Watch For

**Over-engineering indicators:**
- ❌ Adding tables beyond the core three (for domain data)
- ❌ Building authority scoring or automatic resolution
- ❌ Connection type taxonomies
- ❌ Performance optimization before measurement
- ❌ Features without a validated use case
- ❌ Hardcoding types that should be configuration

**On-track indicators:**
- ✅ Every feature expressed as items + connections + snapshots
- ✅ New data types added via configuration, not schema changes
- ✅ Every snapshot has a clear (what, when, who says) triple
- ✅ Workflow items have their own temporal story
- ✅ Can demo value at end of each phase
- ✅ Can explain the system to a non-technical PM
- ✅ Import → navigate → identify → resolve workflow works end to end

---

## The Bottom Line

Three tables. Items, connections, snapshots.

Every snapshot answers: what, when, who says.

Changes and conflicts are items with their own temporal stories. Decisions are items. Notes are items. The executive dashboard queries items. Navigation browses items. Import creates items.

The graph is flat. Navigation feels hierarchical with bounce-back for lateral movement. Conflicts are visible. The story is preserved. Resolution is part of the story.

Everything else is configuration.

Welcome aboard.
