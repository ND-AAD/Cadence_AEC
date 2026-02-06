"""Tests for Connections API — WP-2 acceptance criteria."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_create_connection(client):
    """Can connect two items."""
    room = (await client.post("/api/v1/items/", json={
        "item_type": "room", "identifier": "Room 203",
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D101",
    })).json()

    response = await client.post("/api/v1/connections/", json={
        "source_item_id": room["id"],
        "target_item_id": door["id"],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["source_item_id"] == room["id"]
    assert data["target_item_id"] == door["id"]


@pytest.mark.asyncio
async def test_self_connection_returns_400(client):
    """Self-connection returns 422 (Pydantic validation error)."""
    item = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D101",
    })).json()

    response = await client.post("/api/v1/connections/", json={
        "source_item_id": item["id"],
        "target_item_id": item["id"],
    })
    assert response.status_code == 422  # Pydantic validator catches this


@pytest.mark.asyncio
async def test_duplicate_connection_returns_409(client):
    """Duplicate connection returns 409."""
    room = (await client.post("/api/v1/items/", json={
        "item_type": "room", "identifier": "Room 203",
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D101",
    })).json()

    # First connection succeeds
    response = await client.post("/api/v1/connections/", json={
        "source_item_id": room["id"],
        "target_item_id": door["id"],
    })
    assert response.status_code == 201

    # Same connection again returns 409
    response = await client.post("/api/v1/connections/", json={
        "source_item_id": room["id"],
        "target_item_id": door["id"],
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_connection_missing_item_returns_404(client):
    """Connection to nonexistent item returns 404."""
    item = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D101",
    })).json()

    response = await client.post("/api/v1/connections/", json={
        "source_item_id": item["id"],
        "target_item_id": str(uuid.uuid4()),
    })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_connections_both_directions(client):
    """Querying by item_id returns connections in both directions."""
    room = (await client.post("/api/v1/items/", json={
        "item_type": "room", "identifier": "Room 203",
    })).json()
    floor = (await client.post("/api/v1/items/", json={
        "item_type": "floor", "identifier": "Floor 1",
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D101",
    })).json()

    # floor → room
    await client.post("/api/v1/connections/", json={
        "source_item_id": floor["id"], "target_item_id": room["id"],
    })
    # room → door
    await client.post("/api/v1/connections/", json={
        "source_item_id": room["id"], "target_item_id": door["id"],
    })

    # Query both directions for room
    response = await client.get(f"/api/v1/connections/?item_id={room['id']}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_soft_disconnect(client):
    """Soft disconnect records reason and sets disconnected flag."""
    room = (await client.post("/api/v1/items/", json={
        "item_type": "room", "identifier": "Room 203",
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D101",
    })).json()

    await client.post("/api/v1/connections/", json={
        "source_item_id": room["id"], "target_item_id": door["id"],
    })

    response = await client.post("/api/v1/connections/disconnect", json={
        "source_item_id": room["id"],
        "target_item_id": door["id"],
        "reason": "Door relocated to Room 204",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["properties"]["disconnected"] is True
    assert data["properties"]["disconnect_reason"] == "Door relocated to Room 204"
    assert "disconnected_at" in data["properties"]


@pytest.mark.asyncio
async def test_disconnect_nonexistent_returns_404(client):
    """Disconnect between unconnected items returns 404."""
    room = (await client.post("/api/v1/items/", json={
        "item_type": "room", "identifier": "Room 203",
    })).json()
    door = (await client.post("/api/v1/items/", json={
        "item_type": "door", "identifier": "D101",
    })).json()

    response = await client.post("/api/v1/connections/disconnect", json={
        "source_item_id": room["id"],
        "target_item_id": door["id"],
    })
    assert response.status_code == 404
