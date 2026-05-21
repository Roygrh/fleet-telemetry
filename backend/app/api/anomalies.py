from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.anomaly import AnomalyResponse
from app.services import anomaly as anomaly_service

router = APIRouter()


@router.get("", response_model=list[AnomalyResponse])
async def get_anomalies(
    vehicle_id: str | None = Query(None, description="Filter by vehicle ID (e.g. v-12)"),
    since: datetime | None = Query(None, description="ISO datetime lower bound"),
    until: datetime | None = Query(None, description="ISO datetime upper bound"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    db: AsyncSession = Depends(get_db),
) -> list[AnomalyResponse]:
    return await anomaly_service.query(
        db, vehicle_id=vehicle_id, since=since, until=until, limit=limit
    )
