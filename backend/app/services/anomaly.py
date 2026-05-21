from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import anomaly as anomaly_repo
from app.schemas.anomaly import AnomalyResponse


async def query(
    session: AsyncSession,
    *,
    vehicle_id: str | None,
    since: datetime | None,
    until: datetime | None,
    limit: int,
) -> list[AnomalyResponse]:
    anomalies = await anomaly_repo.query(
        session,
        vehicle_id=vehicle_id,
        since=since,
        until=until,
        limit=limit,
    )
    return [AnomalyResponse.model_validate(a) for a in anomalies]
