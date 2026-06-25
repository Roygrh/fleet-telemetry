from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.teleoperation import TeleoperationSession
from app.repositories import teleoperation as teleop_repo
from app.schemas.teleoperation import TeleoperationSessionCreate, TeleoperationSessionClaim


async def create_session(
    session: AsyncSession,
    body: TeleoperationSessionCreate,
) -> TeleoperationSession:
    record = await teleop_repo.create(session, body.vehicle_id, body.reason)
    await session.commit()
    await session.refresh(record)
    return record


async def list_sessions(session: AsyncSession) -> list[TeleoperationSession]:
    return await teleop_repo.list_sessions(session)


async def claim_session(
    session: AsyncSession,
    session_id: str,
    body: TeleoperationSessionClaim,
) -> TeleoperationSession:
    existing = await teleop_repo.get_by_session_id(session, session_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if existing.status not in ("requested",):
        raise HTTPException(
            status_code=409,
            detail=f"Session is already in status '{existing.status}' and cannot be claimed",
        )
    record = await teleop_repo.claim(session, session_id, body.operator_id)
    await session.commit()
    await session.refresh(record)
    return record


async def release_session(
    session: AsyncSession,
    session_id: str,
) -> TeleoperationSession:
    existing = await teleop_repo.get_by_session_id(session, session_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if existing.status not in ("requested", "claimed", "active"):
        raise HTTPException(
            status_code=409,
            detail=f"Session is already in status '{existing.status}' and cannot be released",
        )
    record = await teleop_repo.release(session, session_id)
    await session.commit()
    await session.refresh(record)
    return record


async def activate_session(
    session: AsyncSession,
    session_id: str,
) -> None:
    existing = await teleop_repo.get_by_session_id(session, session_id)
    if existing and existing.status in ("requested", "claimed"):
        await teleop_repo.activate(session, session_id)
        await session.commit()


async def record_command(
    session: AsyncSession,
    session_id: str,
    command: str,
) -> None:
    await teleop_repo.record_command(session, session_id, command)
    await session.commit()


async def record_sensor_payload(
    session: AsyncSession,
    vehicle_id: str,
    payload: dict,
) -> None:
    active = await teleop_repo.get_active_session_for_vehicle(session, vehicle_id)
    if active:
        await teleop_repo.record_sensor_payload(session, active.session_id, payload)
        await session.commit()


async def get_session(
    session: AsyncSession,
    session_id: str,
) -> TeleoperationSession | None:
    return await teleop_repo.get_by_session_id(session, session_id)
