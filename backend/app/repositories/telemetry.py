from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import TelemetryEvent
from app.schemas.telemetry import TelemetryEventCreate


async def create(session: AsyncSession, payload: TelemetryEventCreate) -> TelemetryEvent:
    event = TelemetryEvent(
        vehicle_id=payload.vehicle_id,
        timestamp=payload.timestamp,
        lat=payload.lat,
        lon=payload.lon,
        battery_pct=payload.battery_pct,
        speed_mps=payload.speed_mps,
        status=payload.status,
        error_codes=payload.error_codes,
        zone_entered=payload.zone_entered,
    )
    session.add(event)
    # Flush to get the auto-generated PK so anomalies can reference it in the same tx.
    await session.flush()
    return event
