from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.zone import ZoneCountResponse
from app.services import zone as zone_service

router = APIRouter()


@router.get("/counts", response_model=ZoneCountResponse)
async def get_zone_counts(
    db: AsyncSession = Depends(get_db),
) -> ZoneCountResponse:
    return await zone_service.get_counts(db)
