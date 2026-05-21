from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MissionStatus
from app.models.mission import Mission


async def cancel_active(
    session: AsyncSession, vehicle_id: str, cancelled_at: datetime
) -> None:
    """Bulk-update all active missions for a vehicle to cancelled in one statement."""
    await session.execute(
        update(Mission)
        .where(Mission.vehicle_id == vehicle_id, Mission.status == MissionStatus.active)
        .values(status=MissionStatus.cancelled, cancelled_at=cancelled_at)
    )
