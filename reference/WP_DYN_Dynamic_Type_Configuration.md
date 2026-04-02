# WP-DYN: Dynamic Type Configuration

## Problem

Type configuration is hardcoded in `backend/app/core/type_config.py`. Alpha testers importing construction data for item types not in the registry (hardware sets, glazing, curtain walls, windows, etc.) hit a dead end: auto-mapping scores poorly, all columns default to "skip," and there's no way to create a new type without changing Python code and restarting the backend.

The architecture was designed for this — `item_type` is a string tag, the three-table model works for any type, and `type_config` is the single extension point. The gap is that the extension point isn't user-accessible.

## Design Principles

1. **Two layers: Cadence OS + firm vocabulary.** The built-in types in `type_config.py` are the operating system — project, milestone, phase, conflict, change, decision, directive, note, import_batch, and other types that Cadence needs to function. These are immutable system types that deploy with every release. Everything domain-specific (doors, windows, rooms, hardware sets, curtain walls) is firm vocabulary: user-defined, user-editable, user-deletable.

2. **Firm-scoped, not project-scoped.** Type definitions belong to the firm (organization). A firm's standards apply across all their projects. If a firm defines "hardware_set" with specific properties, every project under that firm inherits it. This matches how construction firms operate — they have standardized deliverable types across projects.

3. **Alpha simplification: one account = one firm.** For alpha, each user account implicitly has its own firm. The firm item is auto-created on account setup — users never see or manage it. The API resolves the current user's firm automatically, so endpoints are just `POST /v1/types`, `GET /v1/types`, etc. — no firm ID in the URL. The firm-scoped architecture is correct internally (future-proof for collaboration), but invisible to alpha users.

4. **Pre-seeded but mutable.** New accounts get a useful starter vocabulary (door, window, frame, floor, room, building) with standard AEC properties and aliases. These are identical in structure to any user-created type — editable, deletable, not special. The seed data is a convenience, not a constraint.

5. **No new tables.** Type definitions are items in the graph (`item_type = "type_definition"`, `category = "definition"`), connected to the firm. Property definitions are stored in the item's properties as a JSON array. This follows "everything is an item."

6. **Sensible defaults.** A user creating a new type shouldn't need to understand categories, render modes, or conflict exclusion. New domain types default to: `category="spatial"`, `navigable=true`, `render_mode="table"`, `exclude_from_conflicts=false`, `is_source_type=false`, `is_context_type=false`. These are the right defaults for "a thing you import data about."

7. **Auto-mapping works immediately.** Once a type is created with properties, the next import attempt against that type should score correctly in `detect_target_type()` and `build_property_mapping()`.

## Architecture

### Two-Layer Type System

**Layer 1 — Cadence OS (immutable, in code):**

These types are required for the platform to function. They remain in `type_config.py`, deploy with every release, and update automatically. Users cannot create, edit, or delete OS types. The test for "is this OS?" is: **does Cadence have special behavior that depends on this type?**

| Category | Types | Why OS |
|----------|-------|--------|
| Organization | project, portfolio, firm | Project/firm scoping, permissions |
| Temporal | milestone, phase, import_batch, preprocess_batch, extraction_batch | `is_context_type` (milestone), import pipeline metadata |
| Workflow | change, conflict, decision, directive, note | Conflict/change detection, resolution workflow, `is_source_type` (decision) |
| Document | schedule, specification, drawing, spec_section | `is_source_type` (schedule, specification, drawing), MasterFormat classification (spec_section) |
| Definition | property, type_definition | System metadata, type registry itself |

Note: document types are OS because they have `is_source_type=true` — they drive the snapshot attribution engine. A firm can't delete "schedule" without breaking imports. `spec_section` drives MasterFormat classification (WP-15). These types update with Cadence releases like any OS type.

**Layer 2 — Firm vocabulary (mutable, in database):**

Domain-specific types representing things a firm tracks across projects. Stored as `type_definition` items connected to the firm. Pre-seeded on account creation from a starter catalog, but fully editable afterward. Firms own their vocabulary — Cadence doesn't push updates to it.

Starter catalog (ships with Cadence, applied once on account creation):
- **Spatial:** door, window, frame, floor, room, building

Each starter type ships with standard AEC properties and aliases (extracted from the current `type_config.py` definitions). Additional types (hardware_set, curtain_wall, glazing, etc.) can be added by the user at any time through the UI.

### Storage: Type Definitions as Items

A type definition is an item in the graph:

```
Item:
  item_type: "type_definition"
  identifier: "hardware_set"       ← the type name
  properties:
    label: "Hardware Set"
    plural_label: "Hardware Sets"
    category: "spatial"
    render_mode: "table"
    is_source_type: false
    is_context_type: false
    navigable: true
    exclude_from_conflicts: false
    search_fields: ["mark", "manufacturer"]
    property_defs:
      - name: "mark"
        label: "Mark"
        data_type: "string"
        aliases: ["hardware_mark", "hw_mark"]
      - name: "manufacturer"
        label: "Manufacturer"
        data_type: "string"
        aliases: ["mfr", "mfg"]
      - name: "series"
        label: "Series"
        data_type: "string"
```

Connected to the firm: `Firm → type_definition` (standard connection pattern).

### Registry Merge

When resolving the type registry for a project, the backend:
1. Resolves the user's firm (auto-created, one per account for alpha)
2. Loads firm-scoped type definitions from `type_definition` items connected to the firm
3. Merges with Cadence OS types from `ITEM_TYPES`

OS types always win on name collision (a user can't create a type named "conflict"). Firm types are the full domain vocabulary — there's no separate "built-in spatial" layer.

### Migration from Current State

The current hardcoded spatial types in `type_config.py` (door, room, frame, floor, building) move out of the code and into the starter catalog. Document types (schedule, specification, drawing, spec_section) remain in code as OS types.

On account creation (or for existing accounts, on first login after migration), the starter catalog creates `type_definition` items for each spatial type, preserving all existing property definitions, aliases, and normalizations. Existing items in the database with these types continue to work — `item_type` is a string, and the type definition items provide the same config the code used to.

### API

For alpha, all type endpoints resolve the current user's firm automatically. No firm ID in URLs.

**Type CRUD (resolves user's firm implicitly):**

- `POST /v1/types` — Create a new type definition
- `GET /v1/types` — List all types (OS + firm, merged)
- `GET /v1/types/{type_name}` — Get single type config
- `PATCH /v1/types/{type_name}` — Update a type definition (reject for OS types)
- `DELETE /v1/types/{type_name}` — Delete a type (reject for OS types, reject if items of this type exist)

The existing `GET /v1/config/types` endpoint is replaced by `GET /v1/types` which returns the merged view. The frontend switches to this endpoint.

**Internally**, the service layer still takes `firm_id` as a parameter — the route handler resolves it from the authenticated user. When collaboration ships later, endpoints can accept explicit firm IDs without changing the service layer.

### Frontend Entry Points

**During import (primary):** When auto-mapping returns low confidence or the detected type is wrong, the MappingReview screen offers a "Create New Type" option. The user provides a type name, and the system pre-populates property definitions from the unmatched columns. User confirms → type is created → mapping re-runs against the new type.

**Type management (secondary):** A lightweight settings surface accessible from the project level for viewing/editing the type vocabulary. Edit properties, aliases, labels. Delete unused types. Not a priority for alpha — the import-time flow covers the critical path.

## Implementation Steps (TDD)

### DYN-0: Register `type_definition` as OS Type + Starter Catalog

Add the `type_definition` type to the Cadence OS registry. Extract spatial types into a starter catalog module.

**Tests:**
- `test_type_definition_registered`: `get_type_config("type_definition")` returns a valid config
- `test_type_definition_excluded_from_conflicts`: config has `exclude_from_conflicts=True`
- `test_type_definition_not_importable`: does not appear in `get_importable_types()`
- `test_os_types_are_system_only`: All types remaining in `ITEM_TYPES` are organization, temporal, workflow, document, or definition category — no spatial types
- `test_document_types_remain_os`: schedule, specification, drawing, spec_section still in `ITEM_TYPES` (they have `is_source_type=True` or platform pipeline behavior)
- `test_starter_catalog_has_spatial_types`: Starter catalog contains door, window, frame, floor, room, building with full property definitions
- `test_starter_catalog_preserves_aliases`: All aliases from current hardcoded types are preserved in catalog entries

**Implementation:**
- Add `register_type(TypeConfig(name="type_definition", category="definition", ...))` to `type_config.py`
- Remove spatial types (door, room, frame, floor, building) from `type_config.py` — these become firm vocabulary
- Document types (schedule, specification, drawing, spec_section) STAY in `type_config.py` — they're OS
- Extract removed spatial types into `backend/app/core/type_starter_catalog.py` — a list of TypeConfig objects for firm seeding
- Add `window` to the starter catalog (not currently in type_config.py — new starter type with standard properties)

### DYN-1: Firm Auto-Creation + Runtime Type Service

Auto-create a firm item on account creation. Backend service that loads type definitions from the database and merges them with OS types.

**Tests (backend/tests/test_dynamic_types.py):**
- `test_user_has_firm`: After account creation, user has a firm item connected via permissions or connection
- `test_resolve_user_firm`: Service function resolves the firm for a given user
- `test_create_type_definition`: Creates a `type_definition` item connected to firm, returns TypeConfig
- `test_create_type_with_properties`: Property definitions stored correctly, round-trip through service
- `test_create_type_rejects_os_collision`: Creating a type named "conflict" or "milestone" returns error
- `test_create_type_rejects_duplicate`: Creating same type name twice under same firm returns error
- `test_get_firm_types`: Returns all type_definition items connected to firm
- `test_get_merged_registry`: Returns OS types + firm types in one dict
- `test_update_type_definition`: Update label, add property, verify round-trip
- `test_update_rejects_os_type`: Attempt to update "milestone" → error
- `test_delete_type_definition`: Deletes type_definition item + connection
- `test_delete_rejects_if_items_exist`: Delete when items of this type exist → error
- `test_type_defaults`: Created type gets correct defaults (spatial, navigable, table, etc.)
- `test_type_def_to_config_conversion`: Internal converter produces valid TypeConfig with PropertyDefs
- `test_seed_firm_types`: Seeding creates all starter catalog types as type_definition items
- `test_seed_idempotent`: Seeding twice doesn't duplicate types

**Implementation:**
- Auto-create firm item during user registration (or on first login if not present)
- `backend/app/services/dynamic_types.py`:
  - `resolve_user_firm(db, user_id)` → firm item (auto-creates if missing)
  - `get_firm_types(db, firm_id)` → dict of TypeConfig (firm types only)
  - `get_merged_registry(db, firm_id)` → dict of TypeConfig (OS + firm)
  - `create_type_definition(db, firm_id, type_def)` → TypeConfig
  - `update_type_definition(db, firm_id, type_name, updates)` → TypeConfig
  - `delete_type_definition(db, firm_id, type_name)` → None
  - `seed_firm_types(db, firm_id)` → list[TypeConfig] (creates from starter catalog, skips existing)

### DYN-2: Type API Routes

API endpoints for type CRUD. Firm resolved implicitly from authenticated user.

**Tests (extend test_dynamic_types.py):**
- `test_api_create_type`: POST `/v1/types` → 201
- `test_api_create_type_validation`: Missing required fields → 422
- `test_api_list_types_merged`: GET `/v1/types` returns OS + firm types
- `test_api_get_single_type`: GET `/v1/types/hardware_set` → full config
- `test_api_update_type`: PATCH `/v1/types/hardware_set` → updated config
- `test_api_update_os_type_rejected`: PATCH `/v1/types/milestone` → 403
- `test_api_delete_type`: DELETE → 204
- `test_api_delete_os_type_rejected`: DELETE `/v1/types/milestone` → 403
- `test_api_auth_required`: All endpoints require authentication

**Implementation:**
- `backend/app/api/routes/types.py`: Type CRUD (replaces config.py types endpoint)
- Request schemas: `TypeDefinitionCreate`, `TypeDefinitionUpdate` (Pydantic)
- Route handler resolves `firm_id` from `current_user` via `resolve_user_firm()`
- Wire into router, deprecate `GET /v1/config/types`

### DYN-3: Auto-Mapping Integration

Make auto-mapping aware of firm-defined types.

**Tests:**
- `test_importable_types_includes_firm_types`: After seeding, importable types for the user includes door, room, etc. from firm definitions
- `test_detect_target_type_matches_firm_type`: File with door columns → detects "door" from firm types
- `test_detect_target_type_matches_custom_type`: File with hardware columns → detects "hardware_set" after creating that type
- `test_build_property_mapping_uses_firm_properties`: Columns matching firm-type properties map correctly
- `test_firm_type_aliases_work`: Column matching a firm-type property alias → correct mapping

**Implementation:**
- Update `propose_mapping()` signature to accept a type list parameter
- `detect_target_type()` and `build_property_mapping()` receive the merged importable types instead of calling `get_importable_types()` directly
- Update the analyze endpoint to resolve the user's firm, get the merged registry, filter to importable types, and pass them through
- `get_importable_types()` remains as a convenience for OS-only contexts (tests, CLI tools)

### DYN-4: Item Creation with Firm Types

Allow creating items with firm-defined type names.

**Tests:**
- `test_create_item_with_firm_type`: After seeding firm types, `POST /v1/items/` with `item_type="door"` succeeds (door is now a firm type, not in ITEM_TYPES)
- `test_create_item_with_custom_type`: After creating "hardware_set" definition, creating items with that type succeeds
- `test_create_item_with_unknown_type_rejected`: Random type name → 400

**Implementation:**
- Update item creation validation in `items.py` to check both OS types (`ITEM_TYPES`) and the user's firm types
- Import endpoint already passes `mapping.target_item_type` — ensure it checks the merged registry
- Resolve firm from the authenticated user (same pattern as type routes)

### DYN-5: Frontend — Type Creation During Import

The primary user-facing surface: create a new type from within the import flow when auto-mapping fails.

**Tests:** TypeScript compilation + manual walkthrough.

**Implementation:**
- `frontend/src/api/types.ts`: Update to point at `GET /v1/types` (merged view). Add `createType()`, `updateType()`, `deleteType()`.
- `frontend/src/components/import/CreateTypeInline.tsx`: Inline type creation form
  - Type name input (auto-generates identifier from label)
  - Property list pre-populated from the file's unmatched columns (user can rename, remove, add, set data types)
  - Confirm → POST creates type → re-run analyze
- Update `MappingReview.tsx`: Show "Create New Type" when confidence is low or type is wrong. Also allow changing the target type dropdown to any existing type.
- Update `useTypeRegistry.ts`: Add `refresh()` method to invalidate cache after type creation.

### DYN-6: Account Setup Seeding

Ensure new accounts get starter vocabulary automatically.

**Tests:**
- `test_new_account_has_firm`: After registration, user has a firm item
- `test_new_account_has_seed_types`: After registration + seeding, all starter types exist as type_definition items
- `test_seed_preserves_all_properties`: Seed types have same properties, aliases, normalizations as current hardcoded types
- `test_existing_accounts_get_firm_on_login`: Existing users without a firm get one auto-created on next API call

**Implementation:**
- Wire `seed_firm_types()` into account creation flow (registration endpoint or first-login middleware)
- For existing databases: `resolve_user_firm()` auto-creates if missing, then seeds if no type_definitions exist
- Verify backward compatibility: existing items with `item_type="door"` work against firm-defined "door" type

### DYN-7: Frontend — Type Management Surface (Defer for Alpha)

Secondary surface for managing type vocabulary outside the import flow.

**Tests:** TypeScript compilation + manual walkthrough.

**Implementation:**
- Accessible from project-level settings
- List all types (OS types marked as system, non-editable)
- Edit firm types: rename, add/remove properties, manage aliases
- Delete unused firm types
- Low priority — DYN-5 covers the critical path for alpha

## Dependency Order

```
DYN-0 (type_definition OS type + starter catalog extraction)
  ↓
DYN-1 (firm auto-creation + runtime type service)
  ↓
DYN-2 (API routes)  ←─ can parallel with DYN-3
  ↓
DYN-3 (auto-mapping integration)
  ↓
DYN-4 (item creation validation)
  ↓
DYN-5 (frontend: type creation during import)
  ↓
DYN-6 (account setup seeding)
  ↓
DYN-7 (frontend: type management — defer if needed)
```

DYN-0 through DYN-4 are backend. DYN-5 is the critical frontend piece. DYN-6 handles setup/migration. DYN-7 is nice-to-have.

## What This Does NOT Change

- The three-table model (items, connections, snapshots)
- The snapshot triple semantics
- Conflict detection, change detection, or directive fulfillment logic
- Navigation or rendering logic (already type-config-driven and generic)
- The item_type field on existing items (string tag, works with any type name)

## What This DOES Change

- `type_config.py` shrinks to OS types only (organization, temporal, workflow, document, definition)
- Spatial types move from code to database (firm-scoped type_definition items); document types stay OS
- Auto-mapping functions accept a type list parameter instead of calling the global `get_importable_types()`
- Item creation validation checks the merged registry instead of just `ITEM_TYPES`
- Frontend type registry fetches from `/v1/types` (merged view) instead of `/v1/config/types`
- New accounts auto-get a firm + pre-seeded vocabulary
- Existing accounts get firm auto-created on next login, seeded if empty
