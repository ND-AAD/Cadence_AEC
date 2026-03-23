"""Tests for Notes/Cairn CRUD endpoints.

Notes are items (type "note") connected to the target item.
They represent human-authored markers in the graph — cairns.
"""

import pytest


@pytest.mark.asyncio
async def test_create_note(client, make_item):
    """POST /items/{id}/notes creates a cairn item connected to target."""
    door = await make_item("door", "Door 101", {"mark": "101"})
    response = await client.post(
        f"/api/v1/items/{door.id}/notes",
        json={"content": "Check field conditions", "author": "Nick"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "Check field conditions"
    assert data["author"] == "Nick"
    assert data["item_id"] == str(door.id)
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_notes(client, make_item):
    """GET /items/{id}/notes returns all cairns for an item."""
    door = await make_item("door", "Door 101", {"mark": "101"})
    await client.post(
        f"/api/v1/items/{door.id}/notes",
        json={"content": "Note 1", "author": "Nick"},
    )
    await client.post(
        f"/api/v1/items/{door.id}/notes",
        json={"content": "Note 2", "author": "Nick"},
    )
    response = await client.get(f"/api/v1/items/{door.id}/notes")
    assert response.status_code == 200
    notes = response.json()["notes"]
    assert len(notes) == 2


@pytest.mark.asyncio
async def test_list_notes_empty(client, make_item):
    """GET /items/{id}/notes returns empty list when no notes."""
    door = await make_item("door", "Door 101", {"mark": "101"})
    response = await client.get(f"/api/v1/items/{door.id}/notes")
    assert response.status_code == 200
    assert response.json()["notes"] == []


@pytest.mark.asyncio
async def test_delete_note(client, make_item):
    """DELETE /items/{note_id} removes the cairn."""
    door = await make_item("door", "Door 101", {"mark": "101"})
    create_resp = await client.post(
        f"/api/v1/items/{door.id}/notes",
        json={"content": "Temporary note", "author": "Nick"},
    )
    note_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/api/v1/items/{note_id}")
    assert del_resp.status_code == 204
    # Verify it's gone from the list
    list_resp = await client.get(f"/api/v1/items/{door.id}/notes")
    assert len(list_resp.json()["notes"]) == 0


@pytest.mark.asyncio
async def test_notes_scoped_to_item(client, make_item):
    """Notes on one item don't appear on another."""
    door1 = await make_item("door", "Door 101")
    door2 = await make_item("door", "Door 102")
    await client.post(
        f"/api/v1/items/{door1.id}/notes",
        json={"content": "Note on door 1", "author": "Nick"},
    )
    resp1 = await client.get(f"/api/v1/items/{door1.id}/notes")
    resp2 = await client.get(f"/api/v1/items/{door2.id}/notes")
    assert len(resp1.json()["notes"]) == 1
    assert len(resp2.json()["notes"]) == 0


@pytest.mark.asyncio
async def test_notes_all_returned(client, make_item):
    """All notes are returned for an item."""
    door = await make_item("door", "Door 101")
    await client.post(
        f"/api/v1/items/{door.id}/notes",
        json={"content": "First note", "author": "Nick"},
    )
    await client.post(
        f"/api/v1/items/{door.id}/notes",
        json={"content": "Second note", "author": "Nick"},
    )
    response = await client.get(f"/api/v1/items/{door.id}/notes")
    notes = response.json()["notes"]
    assert len(notes) == 2
    contents = {n["content"] for n in notes}
    assert contents == {"First note", "Second note"}


@pytest.mark.asyncio
async def test_create_note_missing_content(client, make_item):
    """POST /items/{id}/notes with empty content is rejected."""
    door = await make_item("door", "Door 101")
    response = await client.post(
        f"/api/v1/items/{door.id}/notes",
        json={"content": "", "author": "Nick"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_note_nonexistent_item(client):
    """POST /items/{id}/notes for a nonexistent item returns 404."""
    import uuid

    fake_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/items/{fake_id}/notes",
        json={"content": "Note on nothing", "author": "Nick"},
    )
    assert response.status_code == 404
