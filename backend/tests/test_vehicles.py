"""
Tests for PATCH /api/vehicles/{vehicle_id}/status — fault transition atomicity.
"""

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text


@pytest_asyncio.fixture
async def vehicle(db) -> str:
    """Seed vehicle v-05 with status=moving and return its vehicle_id."""
    async with db() as session:
        await session.execute(
            text("INSERT INTO vehicles (vehicle_id, current_status) VALUES ('v-05', 'moving')")
        )
        await session.commit()
    return "v-05"


@pytest_asyncio.fixture
async def vehicle_with_mission(db) -> str:
    """Seed vehicle v-05 with one active mission."""
    async with db() as session:
        await session.execute(
            text("INSERT INTO vehicles (vehicle_id, current_status) VALUES ('v-05', 'moving')")
        )
        await session.execute(
            text(
                "INSERT INTO missions (vehicle_id, status, started_at) "
                "VALUES ('v-05', 'active', now() AT TIME ZONE 'UTC')"
            )
        )
        await session.commit()
    return "v-05"


# ------------------------------------------------------------------ #
# Non-fault transitions                                                #
# ------------------------------------------------------------------ #

async def test_status_update_to_idle(
    client: AsyncClient, vehicle: str
) -> None:
    response = await client.patch(f"/api/vehicles/{vehicle}/status", json={"status": "idle"})
    assert response.status_code == 200
    assert response.json()["current_status"] == "idle"


async def test_non_fault_patch_creates_no_maintenance_record(
    client: AsyncClient, db, vehicle: str
) -> None:
    await client.patch(f"/api/vehicles/{vehicle}/status", json={"status": "charging"})

    async with db() as session:
        count = (
            await session.execute(
                text("SELECT count(*) FROM maintenance_records WHERE vehicle_id = :vid"),
                {"vid": vehicle},
            )
        ).scalar()
    assert count == 0


async def test_unknown_vehicle_returns_404(client: AsyncClient) -> None:
    # v-01 was never seeded, so it does not exist in this test's clean DB.
    response = await client.patch("/api/vehicles/v-01/status", json={"status": "idle"})
    assert response.status_code == 404


# ------------------------------------------------------------------ #
# Fault transition                                                     #
# ------------------------------------------------------------------ #

async def test_fault_transition_updates_vehicle_status(
    client: AsyncClient, db, vehicle_with_mission: str
) -> None:
    vid = vehicle_with_mission
    response = await client.patch(f"/api/vehicles/{vid}/status", json={"status": "fault"})

    assert response.status_code == 200
    assert response.json()["current_status"] == "fault"

    async with db() as session:
        row = (
            await session.execute(
                text("SELECT current_status FROM vehicles WHERE vehicle_id = :vid"), {"vid": vid}
            )
        ).scalar()
    assert row == "fault"


async def test_fault_transition_cancels_active_mission(
    client: AsyncClient, db, vehicle_with_mission: str
) -> None:
    vid = vehicle_with_mission
    await client.patch(f"/api/vehicles/{vid}/status", json={"status": "fault"})

    async with db() as session:
        row = (
            await session.execute(
                text("SELECT status FROM missions WHERE vehicle_id = :vid"), {"vid": vid}
            )
        ).scalar()
    assert row == "cancelled"


async def test_fault_transition_creates_maintenance_record(
    client: AsyncClient, db, vehicle_with_mission: str
) -> None:
    vid = vehicle_with_mission
    await client.patch(f"/api/vehicles/{vid}/status", json={"status": "fault"})

    async with db() as session:
        count = (
            await session.execute(
                text("SELECT count(*) FROM maintenance_records WHERE vehicle_id = :vid"),
                {"vid": vid},
            )
        ).scalar()
        reason = (
            await session.execute(
                text("SELECT reason FROM maintenance_records WHERE vehicle_id = :vid"),
                {"vid": vid},
            )
        ).scalar()
    assert count == 1
    assert "fault" in reason.lower()


async def test_fault_transition_cancels_all_active_missions(
    client: AsyncClient, db
) -> None:
    """All active missions (not just one) must be cancelled atomically."""
    async with db() as session:
        await session.execute(
            text("INSERT INTO vehicles (vehicle_id, current_status) VALUES ('v-10', 'moving')")
        )
        for _ in range(2):
            await session.execute(
                text(
                    "INSERT INTO missions (vehicle_id, status, started_at) "
                    "VALUES ('v-10', 'active', now() AT TIME ZONE 'UTC')"
                )
            )
        await session.commit()

    await client.patch("/api/vehicles/v-10/status", json={"status": "fault"})

    async with db() as session:
        active = (
            await session.execute(
                text(
                    "SELECT count(*) FROM missions "
                    "WHERE vehicle_id = 'v-10' AND status = 'active'"
                )
            )
        ).scalar()
        cancelled = (
            await session.execute(
                text(
                    "SELECT count(*) FROM missions "
                    "WHERE vehicle_id = 'v-10' AND status = 'cancelled'"
                )
            )
        ).scalar()

    assert active == 0
    assert cancelled == 2


async def test_fault_transition_atomicity(
    client: AsyncClient, db, vehicle_with_mission: str
) -> None:
    """After a fault PATCH, vehicle + mission + maintenance all reflect the
    transition — verifying that a single commit carries all three changes."""
    vid = vehicle_with_mission
    await client.patch(f"/api/vehicles/{vid}/status", json={"status": "fault"})

    async with db() as session:
        v_status = (
            await session.execute(
                text("SELECT current_status FROM vehicles WHERE vehicle_id = :vid"), {"vid": vid}
            )
        ).scalar()
        m_status = (
            await session.execute(
                text("SELECT status FROM missions WHERE vehicle_id = :vid"), {"vid": vid}
            )
        ).scalar()
        mx_count = (
            await session.execute(
                text("SELECT count(*) FROM maintenance_records WHERE vehicle_id = :vid"),
                {"vid": vid},
            )
        ).scalar()

    assert v_status == "fault"
    assert m_status == "cancelled"
    assert mx_count == 1
