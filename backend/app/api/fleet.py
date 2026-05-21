from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.fleet import FleetStateResponse
from app.services import fleet as fleet_service

router = APIRouter()


@router.get("/state", response_model=FleetStateResponse)
async def get_fleet_state(
    db: AsyncSession = Depends(get_db),
) -> FleetStateResponse:
    return await fleet_service.get_state(db)
