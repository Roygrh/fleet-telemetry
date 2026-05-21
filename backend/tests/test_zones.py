"""
Tests for zone counter increment — correctness and concurrency safety.
"""

import asyncio

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

_ZONE = "charging_bay_1"

_BASE_PAYLOAD = {
    "vehicle_id": "v-01",
    "timestamp": "2026-05-20T10:00:00Z",
    "lat": 37.41,
    "lon": -122.08,
    "battery_pct": 60.0,
    "speed_mps": 1.0,
    "status": "moving",
    "error_codes": [],
    "zone_entered": _ZONE,
}


@pytest_asyncio.fixture(autouse=True)
async def seed_vehicle(db) -> None:
    async with db() as session:
        await session.execute(
            text("INSERT INTO vehicles (vehicle_id, current_status) VALUES ('v-01', 'idle')")
        )
        await session.commit()


async def _zone_count(db, zone_id: str = _ZONE) -> int:
    async with db() as session:
        row = (
            await session.execute(
                text("SELECT entry_count FROM zone_counters WHERE zone_id = :z"),
                {"z": zone_id},
            )
        ).one_or_none()
    return row.entry_count if row else 0


# ------------------------------------------------------------------ #
# Basic increment                                                      #
# ------------------------------------------------------------------ #

async def test_zone_entered_increments_counter(client: AsyncClient, db) -> None:
    assert await _zone_count(db) == 0

    response = await client.post("/api/telemetry", json=_BASE_PAYLOAD)
    assert response.status_code == 202

    assert await _zone_count(db) == 1


async def test_null_zone_entered_does_not_create_counter(
    client: AsyncClient, db
) -> None:
    await client.post("/api/telemetry", json={**_BASE_PAYLOAD, "zone_entered": None})

    async with db() as session:
        row = (await session.execute(text("SELECT count(*) FROM zone_counters"))).scalar()
    assert row == 0


async def test_multiple_sequential_entries_accumulate(
    client: AsyncClient, db
) -> None:
    for _ in range(5):
        await client.post("/api/telemetry", json=_BASE_PAYLOAD)

    assert await _zone_count(db) == 5


async def test_different_zones_counted_independently(
    client: AsyncClient, db
) -> None:
    zone_a = "aisle_a"
    zone_b = "aisle_b"

    await client.post("/api/telemetry", json={**_BASE_PAYLOAD, "zone_entered": zone_a})
    await client.post("/api/telemetry", json={**_BASE_PAYLOAD, "zone_entered": zone_a})
    await client.post("/api/telemetry", json={**_BASE_PAYLOAD, "zone_entered": zone_b})

    assert await _zone_count(db, zone_a) == 2
    assert await _zone_count(db, zone_b) == 1


# ------------------------------------------------------------------ #
# Concurrency — the critical test                                      #
# ------------------------------------------------------------------ #

async def test_concurrent_zone_increments_are_counted_exactly(
    client: AsyncClient, db
) -> None:
    """
    20 concurrent telemetry events all entering the same zone.
    The atomic INSERT ... ON CONFLICT DO UPDATE must count every one of them.
    A non-atomic read-modify-write in Python would lose counts.
    """
    N = 20

    responses = await asyncio.gather(
        *[client.post("/api/telemetry", json=_BASE_PAYLOAD) for _ in range(N)]
    )

    failed = [r.status_code for r in responses if r.status_code != 202]
    assert failed == [], f"Some requests failed: {failed}"

    assert await _zone_count(db) == N
