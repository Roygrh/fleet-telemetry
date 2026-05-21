"""
Tests for GET /api/fleet/state — aggregate status counts.
"""

from httpx import AsyncClient
from sqlalchemy import text


async def _seed_vehicles(db, statuses: list[str]) -> None:
    async with db() as session:
        for i, status in enumerate(statuses, start=1):
            await session.execute(
                text("INSERT INTO vehicles (vehicle_id, current_status) VALUES (:vid, :s)"),
                {"vid": f"v-{i:02d}", "s": status},
            )
        await session.commit()


async def test_fleet_state_empty_database(client: AsyncClient) -> None:
    response = await client.get("/api/fleet/state")
    assert response.status_code == 200
    data = response.json()
    assert data == {"idle": 0, "moving": 0, "charging": 0, "fault": 0, "total": 0}


async def test_fleet_state_all_idle(client: AsyncClient, db) -> None:
    await _seed_vehicles(db, ["idle", "idle", "idle"])

    data = (await client.get("/api/fleet/state")).json()
    assert data["idle"] == 3
    assert data["total"] == 3
    assert data["moving"] == 0
    assert data["fault"] == 0


async def test_fleet_state_mixed_statuses(client: AsyncClient, db) -> None:
    await _seed_vehicles(db, ["idle", "idle", "moving", "charging", "fault", "fault"])

    data = (await client.get("/api/fleet/state")).json()
    assert data["idle"] == 2
    assert data["moving"] == 1
    assert data["charging"] == 1
    assert data["fault"] == 2
    assert data["total"] == 6


async def test_fleet_state_reflects_status_update(
    client: AsyncClient, db
) -> None:
    """After a PATCH changes a vehicle's status, GET /fleet/state must reflect it."""
    await _seed_vehicles(db, ["idle"])

    before = (await client.get("/api/fleet/state")).json()
    assert before["idle"] == 1
    assert before["fault"] == 0

    await client.patch("/api/vehicles/v-01/status", json={"status": "fault"})

    after = (await client.get("/api/fleet/state")).json()
    assert after["idle"] == 0
    assert after["fault"] == 1
    assert after["total"] == 1
