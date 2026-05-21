from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MaintenanceStatus
from app.models.maintenance import MaintenanceRecord


async def create(
    session: AsyncSession, *, vehicle_id: str, reason: str
) -> MaintenanceRecord:
    record = MaintenanceRecord(
        vehicle_id=vehicle_id,
        reason=reason,
        status=MaintenanceStatus.open,
    )
    session.add(record)
    return record
