from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.telemetry import TelemetryEventCreate, TelemetryEventResponse
from app.services import telemetry as telemetry_service

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=TelemetryEventResponse)
async def ingest_telemetry(
    payload: TelemetryEventCreate,
    db: AsyncSession = Depends(get_db),
) -> TelemetryEventResponse:
    event = await telemetry_service.ingest(db, payload)
    return TelemetryEventResponse.model_validate(event)
