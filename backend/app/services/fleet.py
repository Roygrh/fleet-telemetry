from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VehicleStatus
from app.models.vehicle import Vehicle
from app.schemas.fleet import FleetStateResponse


async def get_state(session: AsyncSession) -> FleetStateResponse:
    # A single GROUP BY query is a consistent read at READ COMMITTED isolation —
    # it sees a snapshot as of when the query starts, safe under concurrent updates.
    result = await session.execute(
        select(Vehicle.current_status, func.count().label("count"))
        .group_by(Vehicle.current_status)
    )
    counts: dict[VehicleStatus, int] = {row.current_status: row.count for row in result}

    return FleetStateResponse(
        idle=counts.get(VehicleStatus.idle, 0),
        moving=counts.get(VehicleStatus.moving, 0),
        charging=counts.get(VehicleStatus.charging, 0),
        fault=counts.get(VehicleStatus.fault, 0),
        total=sum(counts.values()),
    )
