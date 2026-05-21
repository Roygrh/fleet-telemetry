from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zone import ZoneCounter


async def increment(session: AsyncSession, zone_id: str) -> None:
    """Atomic upsert — the entire increment is a single SQL statement with no
    Python read-modify-write, so concurrent zone entries for the same zone
    are counted correctly even under high concurrency."""
    await session.execute(
        text(
            "INSERT INTO zone_counters (zone_id, entry_count) "
            "VALUES (:zone_id, 1) "
            "ON CONFLICT (zone_id) DO UPDATE "
            "SET entry_count = zone_counters.entry_count + 1"
        ),
        {"zone_id": zone_id},
    )


async def get_all(session: AsyncSession) -> list[ZoneCounter]:
    result = await session.execute(select(ZoneCounter).order_by(ZoneCounter.zone_id))
    return list(result.scalars().all())
