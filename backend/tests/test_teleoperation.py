"""
Tests for teleoperation HTTP endpoints.

Session lifecycle: requested → claimed → (active via WS) → released.

The full status set is: requested, claimed, active, released, completed, failed.
- active is set when the operator WebSocket connects (not testable via HTTP alone).
- completed and failed are documented lifecycle endpoints; no HTTP trigger yet.

WebSocket internals are exercised by scripts/mock_vehicle_client.py during demo runs.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text


@pytest_asyncio.fixture(autouse=True)
async def seed_vehicle(db) -> None:
    """Ensure v-01 exists before each test in this module."""
    async with db() as session:
        await session.execute(
            text("INSERT INTO vehicles (vehicle_id, current_status) VALUES ('v-01', 'idle')")
        )
        await session.commit()


# ------------------------------------------------------------------ #
# Create session                                                       #
# ------------------------------------------------------------------ #

async def test_create_session_returns_201(client: AsyncClient) -> None:
    response = await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "v-01", "reason": "obstacle detected"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["vehicle_id"] == "v-01"
    assert body["status"] == "requested"
    assert body["reason"] == "obstacle detected"
    assert isinstance(body["session_id"], str)
    assert len(body["session_id"]) == 36  # UUID


async def test_create_session_without_reason(client: AsyncClient) -> None:
    response = await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "v-01"},
    )
    assert response.status_code == 201
    assert response.json()["reason"] is None


async def test_create_session_invalid_vehicle_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "v-99"},
    )
    assert response.status_code == 422


async def test_create_session_bad_vehicle_format_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "vehicle-1"},
    )
    assert response.status_code == 422


# ------------------------------------------------------------------ #
# List sessions                                                        #
# ------------------------------------------------------------------ #

async def test_list_sessions_empty(client: AsyncClient) -> None:
    response = await client.get("/api/teleoperation/sessions")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_sessions_returns_created(client: AsyncClient) -> None:
    await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "v-01"},
    )
    response = await client.get("/api/teleoperation/sessions")
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 1
    assert sessions[0]["vehicle_id"] == "v-01"


# ------------------------------------------------------------------ #
# Claim session                                                        #
# ------------------------------------------------------------------ #

async def test_claim_session(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "v-01"},
    )
    session_id = create_resp.json()["session_id"]

    claim_resp = await client.post(
        f"/api/teleoperation/sessions/{session_id}/claim",
        json={"operator_id": "operator-42"},
    )
    assert claim_resp.status_code == 200
    body = claim_resp.json()
    # Claim sets status to "claimed"; "active" is set when the operator WS connects.
    assert body["status"] == "claimed"
    assert body["operator_id"] == "operator-42"
    assert body["claimed_at"] is not None


async def test_claim_nonexistent_session_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/api/teleoperation/sessions/nonexistent-uuid/claim",
        json={"operator_id": "op-1"},
    )
    assert response.status_code == 404


async def test_claim_already_claimed_session_returns_409(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "v-01"},
    )
    session_id = create_resp.json()["session_id"]

    await client.post(
        f"/api/teleoperation/sessions/{session_id}/claim",
        json={"operator_id": "op-1"},
    )

    # Second claim attempt must be rejected; session is now "claimed".
    response = await client.post(
        f"/api/teleoperation/sessions/{session_id}/claim",
        json={"operator_id": "op-2"},
    )
    assert response.status_code == 409


# ------------------------------------------------------------------ #
# Release session                                                      #
# ------------------------------------------------------------------ #

async def test_release_session(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "v-01"},
    )
    session_id = create_resp.json()["session_id"]

    await client.post(
        f"/api/teleoperation/sessions/{session_id}/claim",
        json={"operator_id": "op-1"},
    )

    release_resp = await client.post(
        f"/api/teleoperation/sessions/{session_id}/release"
    )
    assert release_resp.status_code == 200
    body = release_resp.json()
    assert body["status"] == "released"
    assert body["released_at"] is not None


async def test_release_session_from_active_returns_released(
    client: AsyncClient, db
) -> None:
    """Release must succeed even when the session is in active status.

    active is normally set by the operator WebSocket handler. Here we force it
    directly in the DB to test the HTTP release path in isolation.
    """
    create_resp = await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "v-01"},
    )
    session_id = create_resp.json()["session_id"]

    await client.post(
        f"/api/teleoperation/sessions/{session_id}/claim",
        json={"operator_id": "op-1"},
    )

    async with db() as session:
        await session.execute(
            text(
                "UPDATE teleoperation_sessions SET status = 'active' "
                "WHERE session_id = :sid"
            ),
            {"sid": session_id},
        )
        await session.commit()

    response = await client.post(f"/api/teleoperation/sessions/{session_id}/release")
    assert response.status_code == 200
    assert response.json()["status"] == "released"


async def test_release_nonexistent_session_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/api/teleoperation/sessions/nonexistent-uuid/release"
    )
    assert response.status_code == 404


async def test_release_already_released_session_returns_409(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "v-01"},
    )
    session_id = create_resp.json()["session_id"]

    await client.post(
        f"/api/teleoperation/sessions/{session_id}/claim",
        json={"operator_id": "op-1"},
    )
    await client.post(f"/api/teleoperation/sessions/{session_id}/release")

    response = await client.post(f"/api/teleoperation/sessions/{session_id}/release")
    assert response.status_code == 409


# ------------------------------------------------------------------ #
# Full lifecycle                                                        #
# ------------------------------------------------------------------ #

async def test_full_session_lifecycle(client: AsyncClient, db) -> None:
    # Create
    create_resp = await client.post(
        "/api/teleoperation/sessions",
        json={"vehicle_id": "v-01", "reason": "narrow corridor"},
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["session_id"]

    # Claim
    claim_resp = await client.post(
        f"/api/teleoperation/sessions/{session_id}/claim",
        json={"operator_id": "op-1"},
    )
    assert claim_resp.json()["status"] == "claimed"

    # Release
    release_resp = await client.post(
        f"/api/teleoperation/sessions/{session_id}/release"
    )
    assert release_resp.json()["status"] == "released"

    # Verify in DB
    async with db() as session:
        row = (
            await session.execute(
                text(
                    "SELECT status, operator_id, claimed_at, released_at "
                    "FROM teleoperation_sessions WHERE session_id = :sid"
                ),
                {"sid": session_id},
            )
        ).one()
    assert row.status == "released"
    assert row.operator_id == "op-1"
    assert row.claimed_at is not None
    assert row.released_at is not None
