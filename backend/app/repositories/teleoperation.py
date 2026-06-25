import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.teleoperation import TeleoperationSession


async def create(
    session: AsyncSession,
    vehicle_id: str,
    reason: str | None,
) -> TeleoperationSession:
    record = TeleoperationSession(
        session_id=str(uuid.uuid4()),
        vehicle_id=vehicle_id,
        status="requested",
        reason=reason,
    )
    session.add(record)
    await session.flush()
    return record


async def get_by_session_id(
    session: AsyncSession,
    session_id: str,
) -> TeleoperationSession | None:
    result = await session.execute(
        select(TeleoperationSession).where(TeleoperationSession.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def list_sessions(
    session: AsyncSession,
    limit: int = 50,
) -> list[TeleoperationSession]:
    result = await session.execute(
        select(TeleoperationSession)
        .order_by(TeleoperationSession.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def claim(
    session: AsyncSession,
    session_id: str,
    operator_id: str,
) -> TeleoperationSession | None:
    await session.execute(
        update(TeleoperationSession)
        .where(TeleoperationSession.session_id == session_id)
        .values(
            status="claimed",
            operator_id=operator_id,
            claimed_at=datetime.now(timezone.utc),
        )
    )
    return await get_by_session_id(session, session_id)


async def activate(
    session: AsyncSession,
    session_id: str,
) -> None:
    await session.execute(
        update(TeleoperationSession)
        .where(TeleoperationSession.session_id == session_id)
        .values(status="active")
    )


async def release(
    session: AsyncSession,
    session_id: str,
) -> TeleoperationSession | None:
    await session.execute(
        update(TeleoperationSession)
        .where(TeleoperationSession.session_id == session_id)
        .values(
            status="released",
            released_at=datetime.now(timezone.utc),
        )
    )
    return await get_by_session_id(session, session_id)


async def record_command(
    session: AsyncSession,
    session_id: str,
    command: str,
) -> None:
    await session.execute(
        update(TeleoperationSession)
        .where(TeleoperationSession.session_id == session_id)
        .values(
            last_command=command,
            last_command_at=datetime.now(timezone.utc),
        )
    )


async def record_sensor_payload(
    session: AsyncSession,
    session_id: str,
    payload: dict,
) -> None:
    await session.execute(
        update(TeleoperationSession)
        .where(TeleoperationSession.session_id == session_id)
        .values(last_sensor_payload=payload)
    )


async def get_active_session_for_vehicle(
    session: AsyncSession,
    vehicle_id: str,
) -> TeleoperationSession | None:
    # Match both claimed (operator assigned, WS not yet open) and active (WS live).
    result = await session.execute(
        select(TeleoperationSession)
        .where(
            TeleoperationSession.vehicle_id == vehicle_id,
            TeleoperationSession.status.in_(["claimed", "active"]),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()
