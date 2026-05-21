from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import Anomaly


async def create(
    session: AsyncSession,
    *,
    vehicle_id: str,
    timestamp: datetime,
    anomaly_type: str,
    description: str,
    telemetry_event_id: int | None = None,
) -> Anomaly:
    anomaly = Anomaly(
        vehicle_id=vehicle_id,
        timestamp=timestamp,
        anomaly_type=anomaly_type,
        description=description,
        telemetry_event_id=telemetry_event_id,
    )
    session.add(anomaly)
    return anomaly


async def get_latest_per_vehicle(session: AsyncSession) -> dict[str, Anomaly]:
    """Returns the single most-recent anomaly for every vehicle that has one."""
    subq = select(func.max(Anomaly.id)).group_by(Anomaly.vehicle_id).scalar_subquery()
    result = await session.execute(select(Anomaly).where(Anomaly.id.in_(subq)))
    return {a.vehicle_id: a for a in result.scalars().all()}


async def query(
    session: AsyncSession,
    *,
    vehicle_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
) -> list[Anomaly]:
    stmt = select(Anomaly)
    if vehicle_id is not None:
        stmt = stmt.where(Anomaly.vehicle_id == vehicle_id)
    if since is not None:
        stmt = stmt.where(Anomaly.timestamp >= since)
    if until is not None:
        stmt = stmt.where(Anomaly.timestamp <= until)
    stmt = stmt.order_by(Anomaly.timestamp.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
