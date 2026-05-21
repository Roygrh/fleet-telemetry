"""
Tests for POST /api/telemetry — ingestion, vehicle state update, anomaly detection.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

# A valid baseline payload that triggers no anomalies.
_BASE = {
    "vehicle_id": "v-01",
    "timestamp": "2026-05-20T10:00:00Z",
    "lat": 37.41,
    "lon": -122.08,
    "battery_pct": 60.0,
    "speed_mps": 1.0,
    "status": "moving",
    "error_codes": [],
    "zone_entered": None,
}


@pytest_asyncio.fixture(autouse=True)
async def seed_vehicle(db) -> None:
    """Ensure vehicle v-01 exists before every test in this module."""
    async with db() as session:
        await session.execute(
            text("INSERT INTO vehicles (vehicle_id, current_status) VALUES ('v-01', 'idle')")
        )
        await session.commit()


# ------------------------------------------------------------------ #
# Ingestion + vehicle state                                            #
# ------------------------------------------------------------------ #

async def test_ingest_returns_202_and_event(client: AsyncClient) -> None:
    response = await client.post("/api/telemetry", json=_BASE)
    assert response.status_code == 202
    body = response.json()
    assert body["vehicle_id"] == "v-01"
    assert body["battery_pct"] == pytest.approx(60.0)
    assert body["status"] == "moving"
    assert isinstance(body["id"], int)


async def test_ingest_updates_vehicle_state(client: AsyncClient, db) -> None:
    payload = {**_BASE, "battery_pct": 42.5, "status": "charging"}
    await client.post("/api/telemetry", json=payload)

    async with db() as session:
        row = (
            await session.execute(
                text("SELECT current_status, battery_pct FROM vehicles WHERE vehicle_id = 'v-01'")
            )
        ).one()
    assert row.current_status == "charging"
    assert row.battery_pct == pytest.approx(42.5)


# ------------------------------------------------------------------ #
# Anomaly detection — one test per rule                               #
# ------------------------------------------------------------------ #

async def _anomaly_types(db, vehicle_id: str = "v-01") -> set[str]:
    async with db() as session:
        rows = (
            await session.execute(
                text("SELECT anomaly_type FROM anomalies WHERE vehicle_id = :vid"),
                {"vid": vehicle_id},
            )
        ).all()
    return {r.anomaly_type for r in rows}


async def test_no_anomaly_for_normal_telemetry(client: AsyncClient, db) -> None:
    await client.post("/api/telemetry", json=_BASE)
    assert await _anomaly_types(db) == set()


async def test_anomaly_low_battery(client: AsyncClient, db) -> None:
    await client.post("/api/telemetry", json={**_BASE, "battery_pct": 14.9})
    assert "LOW_BATTERY" in await _anomaly_types(db)


async def test_anomaly_battery_at_threshold_is_not_flagged(
    client: AsyncClient, db
) -> None:
    await client.post("/api/telemetry", json={**_BASE, "battery_pct": 15.0})
    assert "LOW_BATTERY" not in await _anomaly_types(db)


async def test_anomaly_vehicle_fault(client: AsyncClient, db) -> None:
    await client.post("/api/telemetry", json={**_BASE, "status": "fault"})
    assert "VEHICLE_FAULT" in await _anomaly_types(db)


async def test_anomaly_error_codes_reported(client: AsyncClient, db) -> None:
    await client.post("/api/telemetry", json={**_BASE, "error_codes": ["E001", "E002"]})
    assert "ERROR_CODE_REPORTED" in await _anomaly_types(db)


async def test_anomaly_high_speed(client: AsyncClient, db) -> None:
    await client.post("/api/telemetry", json={**_BASE, "speed_mps": 8.1})
    assert "HIGH_SPEED" in await _anomaly_types(db)


async def test_anomaly_speed_at_threshold_is_not_flagged(
    client: AsyncClient, db
) -> None:
    await client.post("/api/telemetry", json={**_BASE, "speed_mps": 8.0})
    assert "HIGH_SPEED" not in await _anomaly_types(db)


async def test_multiple_rules_fire_independently(client: AsyncClient, db) -> None:
    # battery < 15  AND  speed > 8  → two separate anomaly rows
    await client.post("/api/telemetry", json={**_BASE, "battery_pct": 10.0, "speed_mps": 9.0})
    types = await _anomaly_types(db)
    assert "LOW_BATTERY" in types
    assert "HIGH_SPEED" in types


async def test_anomaly_linked_to_telemetry_event(client: AsyncClient, db) -> None:
    response = await client.post("/api/telemetry", json={**_BASE, "battery_pct": 5.0})
    event_id = response.json()["id"]

    async with db() as session:
        row = (
            await session.execute(
                text(
                    "SELECT telemetry_event_id FROM anomalies "
                    "WHERE vehicle_id = 'v-01' AND anomaly_type = 'LOW_BATTERY'"
                )
            )
        ).one()
    assert row.telemetry_event_id == event_id


async def test_invalid_vehicle_id_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/telemetry", json={**_BASE, "vehicle_id": "v-99"})
    assert response.status_code == 422


async def test_invalid_zone_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/telemetry", json={**_BASE, "zone_entered": "nonexistent_zone"}
    )
    assert response.status_code == 422
