from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VehicleStatus
from app.models.vehicle import Vehicle


async def get_all(session: AsyncSession) -> list[Vehicle]:
    result = await session.execute(select(Vehicle).order_by(Vehicle.vehicle_id))
    return list(result.scalars().all())


async def get_by_vehicle_id(session: AsyncSession, vehicle_id: str) -> Vehicle | None:
    result = await session.execute(
        select(Vehicle).where(Vehicle.vehicle_id == vehicle_id)
    )
    return result.scalar_one_or_none()


async def get_for_update(session: AsyncSession, vehicle_id: str) -> Vehicle | None:
    """SELECT ... FOR UPDATE — acquires a row-level lock for the fault transition."""
    result = await session.execute(
        select(Vehicle).where(Vehicle.vehicle_id == vehicle_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def update_state(
    session: AsyncSession,
    vehicle_id: str,
    status: VehicleStatus,
    battery_pct: float,
    last_seen_at: datetime,
) -> None:
    await session.execute(
        update(Vehicle)
        .where(Vehicle.vehicle_id == vehicle_id)
        .values(current_status=status, battery_pct=battery_pct, last_seen_at=last_seen_at)
    )
