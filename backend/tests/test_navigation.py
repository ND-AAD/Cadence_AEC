"""
Tests for the Navigation API (WP-4).

Tests cover:
- Direct push: target directly connected to current item
- Sibling bounce-back: navigate to sibling connected to parent
- No path found: target unconnected to any breadcrumb ancestor
- Diamond pattern: multiple connection paths
- Target already in breadcrumb: should bounce back to it
- Snapshot-based adjacency: milestone → door via snapshot context_id
- BFS breadcrumb exclusion: BFS cannot route through breadcrumb ancestors
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Item, Snapshot


# ─── Local fixture: snapshot creation ──────────────────────────


@pytest_asyncio.fixture
async def make_snapshot(db_session: AsyncSession):
    """Factory fixture for creating snapshots (the triple)."""

    async def _make(
        item: Item,
        context: Item,
        source: Item,
        properties: dict | None = None,
    ) -> Snapshot:
        snap = Snapshot(
            item_id=item.id,
            context_id=context.id,
            source_id=source.id,
            properties=properties or {},
        )
        db_session.add(snap)
        await db_session.flush()
        await db_session.refresh(snap)
        return snap

    return _make


# ─── Connection-based navigation (existing tests) ─────────────


@pytest.mark.asyncio
async def test_direct_push(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: breadcrumb [project, building], target=floor (floor connected to building)
    Expected: breadcrumb becomes [project, building, floor], action="push"
    """
    project = await make_item(item_type="project", identifier="P1")
    building = await make_item(item_type="building", identifier="B1")
    floor = await make_item(item_type="floor", identifier="F1")

    await make_connection(project, building)
    await make_connection(building, floor)

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(building.id)],
            "target": str(floor.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "push"
    assert data["bounced_from"] is None
    assert data["breadcrumb"] == [str(project.id), str(building.id), str(floor.id)]


@pytest.mark.asyncio
async def test_sibling_bounce_back(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: breadcrumb [project, building, floor, room, door101], target=door102
    door102 is connected to room but not to door101.
    Expected: breadcrumb becomes [project, building, floor, room, door102], action="bounce_back"
    """
    project = await make_item(item_type="project", identifier="P1")
    building = await make_item(item_type="building", identifier="B1")
    floor = await make_item(item_type="floor", identifier="F1")
    room = await make_item(item_type="room", identifier="R1")
    door101 = await make_item(item_type="door", identifier="D101")
    door102 = await make_item(item_type="door", identifier="D102")

    await make_connection(project, building)
    await make_connection(building, floor)
    await make_connection(floor, room)
    await make_connection(room, door101)
    await make_connection(room, door102)

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [
                str(project.id),
                str(building.id),
                str(floor.id),
                str(room.id),
                str(door101.id),
            ],
            "target": str(door102.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "bounce_back"
    assert data["bounced_from"] == str(door101.id)
    assert data["breadcrumb"] == [
        str(project.id),
        str(building.id),
        str(floor.id),
        str(room.id),
        str(door102.id),
    ]


@pytest.mark.asyncio
async def test_no_path_found(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: breadcrumb [project], target=random_unconnected_item
    Expected: action="no_path", breadcrumb unchanged
    """
    project = await make_item(item_type="project", identifier="P1")
    unconnected = await make_item(item_type="building", identifier="B_unconnected")

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id)],
            "target": str(unconnected.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "no_path"
    assert data["bounced_from"] is None
    assert data["breadcrumb"] == [str(project.id)]


@pytest.mark.asyncio
async def test_diamond_pattern(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: diamond pattern where door is connected to both schedule and spec.
    Navigate from door to schedule works.
    Expected: breadcrumb includes schedule, action="push"
    """
    door = await make_item(item_type="door", identifier="D1")
    schedule = await make_item(item_type="schedule", identifier="Sch1")
    spec = await make_item(item_type="specification", identifier="Spec1")
    project = await make_item(item_type="project", identifier="P1")

    await make_connection(project, door)
    await make_connection(project, schedule)
    await make_connection(project, spec)
    await make_connection(door, schedule)

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(door.id)],
            "target": str(schedule.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "push"
    assert data["bounced_from"] is None
    assert data["breadcrumb"] == [str(project.id), str(door.id), str(schedule.id)]


@pytest.mark.asyncio
async def test_target_already_in_breadcrumb(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: breadcrumb [project, building, floor, room], target=building (already in breadcrumb)
    Expected: should bounce back to building, breadcrumb becomes [project, building]
    """
    project = await make_item(item_type="project", identifier="P1")
    building = await make_item(item_type="building", identifier="B1")
    floor = await make_item(item_type="floor", identifier="F1")
    room = await make_item(item_type="room", identifier="R1")

    await make_connection(project, building)
    await make_connection(building, floor)
    await make_connection(floor, room)

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [
                str(project.id),
                str(building.id),
                str(floor.id),
                str(room.id),
            ],
            "target": str(building.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "bounce_back"
    assert data["bounced_from"] is None
    assert data["breadcrumb"] == [str(project.id), str(building.id)]


@pytest.mark.asyncio
async def test_bidirectional_connection(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: connection can be traversed in both directions.
    If A → B exists, navigation should work from B to A.
    """
    project = await make_item(item_type="project", identifier="P1")
    building = await make_item(item_type="building", identifier="B1")

    await make_connection(project, building)

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(building.id)],
            "target": str(project.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "push"
    assert data["breadcrumb"] == [str(building.id), str(project.id)]


@pytest.mark.asyncio
async def test_bounce_back_to_distant_ancestor(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: bounce back skips intermediate ancestors and finds a connected one.
    breadcrumb [project, building, floor, room], target=schedule
    schedule is connected to project (not to room, floor, or building).
    Expected: bounce back to project, breadcrumb [project, schedule].
    """
    project = await make_item(item_type="project", identifier="P1")
    building = await make_item(item_type="building", identifier="B1")
    floor = await make_item(item_type="floor", identifier="F1")
    room = await make_item(item_type="room", identifier="R1")
    schedule = await make_item(item_type="schedule", identifier="Sch1")

    await make_connection(project, building)
    await make_connection(building, floor)
    await make_connection(floor, room)
    await make_connection(project, schedule)

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [
                str(project.id),
                str(building.id),
                str(floor.id),
                str(room.id),
            ],
            "target": str(schedule.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "bounce_back"
    assert data["breadcrumb"] == [str(project.id), str(schedule.id)]
    assert data["bounced_from"] == str(building.id)


@pytest.mark.asyncio
async def test_missing_breadcrumb_item(
    client: AsyncClient,
    make_item,
):
    """
    Test: if a breadcrumb item doesn't exist, return 404.
    """
    import uuid

    project = await make_item(item_type="project", identifier="P1")
    fake_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(fake_id)],
            "target": str(project.id),
        },
    )

    assert response.status_code == 404
    assert "breadcrumb not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_missing_target_item(
    client: AsyncClient,
    make_item,
):
    """
    Test: if target doesn't exist, return 404.
    """
    import uuid

    project = await make_item(item_type="project", identifier="P1")
    fake_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id)],
            "target": str(fake_id),
        },
    )

    assert response.status_code == 404
    assert "target item not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_empty_breadcrumb(
    client: AsyncClient,
    make_item,
):
    """
    Test: empty breadcrumb should return 400.
    """
    project = await make_item(item_type="project", identifier="P1")

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [],
            "target": str(project.id),
        },
    )

    assert response.status_code == 400
    assert "breadcrumb cannot be empty" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_complex_navigation_sequence(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Test: complex navigation sequence with multiple push and bounce-back operations.
    """
    project = await make_item(item_type="project", identifier="P1")
    building1 = await make_item(item_type="building", identifier="B1")
    building2 = await make_item(item_type="building", identifier="B2")
    floor1 = await make_item(item_type="floor", identifier="F1")
    floor2 = await make_item(item_type="floor", identifier="F2")

    await make_connection(project, building1)
    await make_connection(project, building2)
    await make_connection(building1, floor1)
    await make_connection(building2, floor2)

    # Step 1: Push from project to building1
    response1 = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id)],
            "target": str(building1.id),
        },
    )
    assert response1.json()["action"] == "push"

    # Step 2: Push from building1 to floor1
    response2 = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(building1.id)],
            "target": str(floor1.id),
        },
    )
    assert response2.json()["action"] == "push"

    # Step 3: Bounce back to building2 (connected to project)
    response3 = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(building1.id), str(floor1.id)],
            "target": str(building2.id),
        },
    )
    assert response3.json()["action"] == "bounce_back"
    assert response3.json()["breadcrumb"] == [str(project.id), str(building2.id)]


# ─── Snapshot-based adjacency tests ───────────────────────────


@pytest.mark.asyncio
async def test_milestone_to_door_via_snapshot(
    client: AsyncClient,
    make_item,
    make_connection,
    make_snapshot,
):
    """
    The primary navigation path: user stands at a milestone, sees doors
    that have snapshots at that milestone, clicks one.

    Graph:
      Connections: Project → Milestone, Project → Schedule, Schedule → Door
      Snapshots: (Door, Milestone, Schedule) — door described at milestone by schedule

    No Connection between Milestone and Door. The only link is the snapshot's
    context_id. Navigation must treat this as adjacency.

    Breadcrumb: [Project, Milestone], target: Door
    Expected: [Project, Milestone, Door], action="push"
    """
    project = await make_item(item_type="project", identifier="P1")
    milestone = await make_item(
        item_type="milestone", identifier="DD", properties={"ordinal": 300}
    )
    schedule = await make_item(item_type="schedule", identifier="Door Schedule")
    door = await make_item(item_type="door", identifier="Door 101")

    # Structural connections
    await make_connection(project, milestone)
    await make_connection(project, schedule)
    await make_connection(schedule, door)

    # The snapshot triple: door described at milestone by schedule
    await make_snapshot(
        item=door, context=milestone, source=schedule, properties={"finish": "paint"}
    )

    # Navigate from milestone to door
    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(milestone.id)],
            "target": str(door.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "push"
    assert data["breadcrumb"] == [str(project.id), str(milestone.id), str(door.id)]


@pytest.mark.asyncio
async def test_milestone_to_source_via_snapshot(
    client: AsyncClient,
    make_item,
    make_connection,
    make_snapshot,
):
    """
    A source that submitted at a milestone is navigably adjacent to that
    milestone. The connected items endpoint surfaces sources via
    Snapshot.source_id queries; navigate must agree.

    Breadcrumb: [Project, Milestone], target: Schedule
    Expected: push (Schedule is a source at this milestone)
    """
    project = await make_item(item_type="project", identifier="P1")
    milestone = await make_item(
        item_type="milestone", identifier="DD", properties={"ordinal": 300}
    )
    schedule = await make_item(item_type="schedule", identifier="Door Schedule")
    door = await make_item(item_type="door", identifier="Door 101")

    await make_connection(project, milestone)
    await make_connection(project, schedule)
    await make_connection(schedule, door)

    # Schedule submitted data at milestone
    await make_snapshot(
        item=door, context=milestone, source=schedule, properties={"finish": "paint"}
    )

    # Navigate from milestone to schedule
    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(milestone.id)],
            "target": str(schedule.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    # Schedule is also connected to Project (ancestor), but the milestone
    # is checked first (Step 2) via snapshot adjacency, so this is a push.
    assert data["action"] == "push"
    assert data["breadcrumb"] == [str(project.id), str(milestone.id), str(schedule.id)]


@pytest.mark.asyncio
async def test_milestone_to_door_no_snapshot_no_path(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    Without a snapshot linking door to milestone, there should be no
    direct adjacency. Confirms snapshot awareness is conditional, not
    a blanket change.

    No snapshot exists. No Connection between Milestone and Door.
    BFS from Milestone would go Milestone → Project → Schedule → Door,
    but Project is in the breadcrumb and excluded from BFS traversal.

    Expected: no_path (BFS can't route through the project ancestor).
    """
    project = await make_item(item_type="project", identifier="P1")
    milestone = await make_item(
        item_type="milestone", identifier="DD", properties={"ordinal": 300}
    )
    schedule = await make_item(item_type="schedule", identifier="Door Schedule")
    door = await make_item(item_type="door", identifier="Door 101")

    await make_connection(project, milestone)
    await make_connection(project, schedule)
    await make_connection(schedule, door)

    # No snapshot: door is NOT described at this milestone.

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(milestone.id)],
            "target": str(door.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    # Door is reachable through Project, but Project is in the breadcrumb
    # and excluded from BFS. Milestone has no snapshot link to Door.
    # The only path (Milestone → Project → Schedule → Door) is blocked.
    assert data["action"] == "no_path"


@pytest.mark.asyncio
async def test_bfs_excludes_breadcrumb_ancestors(
    client: AsyncClient,
    make_item,
    make_connection,
):
    """
    BFS must not route through items already in the breadcrumb.

    Graph: A → B → C → D, also A → D directly.
    Breadcrumb: [A, B, C], target: D

    Step 2 (direct): C is not connected to D. Fail.
    Step 3 (ancestors): B not connected to D. A IS connected to D.
    Result: bounce_back to A, push D. Breadcrumb: [A, D].

    BFS should never produce [A, B, C, A, D] or route through A
    as an intermediate hop.
    """
    a = await make_item(item_type="project", identifier="A")
    b = await make_item(item_type="building", identifier="B")
    c = await make_item(item_type="floor", identifier="C")
    d = await make_item(item_type="room", identifier="D")

    await make_connection(a, b)
    await make_connection(b, c)
    await make_connection(a, d)

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(a.id), str(b.id), str(c.id)],
            "target": str(d.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    # Ancestor walk finds A connected to D. Bounce back to A, push D.
    assert data["action"] == "bounce_back"
    assert data["breadcrumb"] == [str(a.id), str(d.id)]
    # Breadcrumb never has duplicates.
    assert len(data["breadcrumb"]) == len(set(data["breadcrumb"]))


@pytest.mark.asyncio
async def test_door_to_milestone_reverse_adjacency(
    client: AsyncClient,
    make_item,
    make_connection,
    make_snapshot,
):
    """
    Snapshot adjacency works in reverse: from a door, you can navigate
    to a milestone that describes it.

    Breadcrumb: [Project, Schedule, Door], target: Milestone
    Door has a snapshot at Milestone. Milestone is a context type.
    Expected: bounce_back to Project (ancestor connected to Milestone), push Milestone.
    OR: if _is_connected recognizes Door→Milestone via reverse snapshot, push.

    The reverse check in _is_connected asks: is Milestone a context type
    AND does Door have a snapshot with context_id=Milestone? Yes.
    But we're at Door (not Milestone), so Step 2 checks
    _is_connected(Door, Milestone). The function checks both directions:
    item_b (Milestone) is context type, item_a (Door) has snapshot at it. True.
    """
    project = await make_item(item_type="project", identifier="P1")
    milestone = await make_item(
        item_type="milestone", identifier="DD", properties={"ordinal": 300}
    )
    schedule = await make_item(item_type="schedule", identifier="Door Schedule")
    door = await make_item(item_type="door", identifier="Door 101")

    await make_connection(project, milestone)
    await make_connection(project, schedule)
    await make_connection(schedule, door)

    await make_snapshot(
        item=door, context=milestone, source=schedule, properties={"finish": "paint"}
    )

    response = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(schedule.id), str(door.id)],
            "target": str(milestone.id),
        },
    )

    assert response.status_code == 200
    data = response.json()
    # Door is snapshot-adjacent to Milestone (reverse check). Direct push.
    assert data["action"] == "push"
    assert data["breadcrumb"] == [
        str(project.id),
        str(schedule.id),
        str(door.id),
        str(milestone.id),
    ]


@pytest.mark.asyncio
async def test_multiple_milestones_correct_adjacency(
    client: AsyncClient,
    make_item,
    make_connection,
    make_snapshot,
):
    """
    A door described at DD but not at CD. Navigating from DD to door
    should work. Navigating from CD to door should fail (no snapshot).
    """
    project = await make_item(item_type="project", identifier="P1")
    dd = await make_item(
        item_type="milestone", identifier="DD", properties={"ordinal": 300}
    )
    cd = await make_item(
        item_type="milestone", identifier="CD", properties={"ordinal": 400}
    )
    schedule = await make_item(item_type="schedule", identifier="Door Schedule")
    door = await make_item(item_type="door", identifier="Door 101")

    await make_connection(project, dd)
    await make_connection(project, cd)
    await make_connection(project, schedule)
    await make_connection(schedule, door)

    # Door described at DD only.
    await make_snapshot(
        item=door, context=dd, source=schedule, properties={"finish": "paint"}
    )

    # DD → Door: should work (snapshot adjacency).
    resp_dd = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(dd.id)],
            "target": str(door.id),
        },
    )
    assert resp_dd.status_code == 200
    assert resp_dd.json()["action"] == "push"
    assert resp_dd.json()["breadcrumb"] == [str(project.id), str(dd.id), str(door.id)]

    # CD → Door: should fail (no snapshot at CD, BFS blocked by project in breadcrumb).
    resp_cd = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id), str(cd.id)],
            "target": str(door.id),
        },
    )
    assert resp_cd.status_code == 200
    assert resp_cd.json()["action"] == "no_path"


@pytest.mark.asyncio
async def test_full_powers_of_ten_sequence(
    client: AsyncClient,
    make_item,
    make_connection,
    make_snapshot,
):
    """
    End-to-end: the full navigation sequence a user walks.

    1. Project → Milestone (connection push)
    2. Milestone → Door (snapshot adjacency push)
    3. Door → back to Milestone (breadcrumb pop)
    4. Milestone → Door 102 (snapshot adjacency push, sibling case)

    Every step should produce a clean, non-duplicated breadcrumb.
    """
    project = await make_item(item_type="project", identifier="P1")
    milestone = await make_item(
        item_type="milestone", identifier="DD", properties={"ordinal": 300}
    )
    schedule = await make_item(item_type="schedule", identifier="Door Schedule")
    door101 = await make_item(item_type="door", identifier="Door 101")
    door102 = await make_item(item_type="door", identifier="Door 102")

    await make_connection(project, milestone)
    await make_connection(project, schedule)
    await make_connection(schedule, door101)
    await make_connection(schedule, door102)

    # Both doors described at this milestone
    await make_snapshot(
        item=door101, context=milestone, source=schedule, properties={"finish": "paint"}
    )
    await make_snapshot(
        item=door102, context=milestone, source=schedule, properties={"finish": "stain"}
    )

    # Step 1: Project → Milestone (connection-based push)
    r1 = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": [str(project.id)],
            "target": str(milestone.id),
        },
    )
    assert r1.json()["action"] == "push"
    bc1 = r1.json()["breadcrumb"]
    assert bc1 == [str(project.id), str(milestone.id)]

    # Step 2: Milestone → Door 101 (snapshot adjacency push)
    r2 = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": bc1,
            "target": str(door101.id),
        },
    )
    assert r2.json()["action"] == "push"
    bc2 = r2.json()["breadcrumb"]
    assert bc2 == [str(project.id), str(milestone.id), str(door101.id)]

    # Step 3: Navigate to Door 102 (sibling, both described at milestone)
    # Door 102 is not connected to Door 101, but both are snapshot-adjacent
    # to Milestone. Ancestor walk: Milestone is connected to Door 102 via
    # snapshot. Bounce back to Milestone, push Door 102.
    r3 = await client.post(
        "/api/v1/navigate",
        json={
            "breadcrumb": bc2,
            "target": str(door102.id),
        },
    )
    assert r3.json()["action"] == "bounce_back"
    bc3 = r3.json()["breadcrumb"]
    assert bc3 == [str(project.id), str(milestone.id), str(door102.id)]

    # Every breadcrumb is clean: no duplicates.
    for bc in [bc1, bc2, bc3]:
        assert len(bc) == len(set(bc)), f"Duplicate in breadcrumb: {bc}"
