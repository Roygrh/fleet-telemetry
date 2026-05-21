from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import zone as zone_repo
from app.schemas.zone import ZoneCountItem, ZoneCountResponse


async def get_counts(session: AsyncSession) -> ZoneCountResponse:
    zones = await zone_repo.get_all(session)
    return ZoneCountResponse(zones=[ZoneCountItem.model_validate(z) for z in zones])
