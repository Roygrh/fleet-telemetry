from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VehicleStatus
from app.models.telemetry import TelemetryEvent
from app.repositories import anomaly as anomaly_repo
from app.repositories import telemetry as telemetry_repo
from app.repositories import vehicle as vehicle_repo
from app.repositories import zone as zone_repo
from app.schemas.telemetry import TelemetryEventCreate

# Each rule is a (anomaly_type, predicate, description_factory) triple.
_ANOMALY_RULES: list[tuple[str, object, object]] = [
    (
        "LOW_BATTERY",
        lambda p: p.battery_pct < 15,
        lambda p: f"Battery at {p.battery_pct:.1f}% — below 15% threshold",
    ),
    (
        "VEHICLE_FAULT",
        lambda p: p.status == VehicleStatus.fault,
        lambda p: "Vehicle reported fault status",
    ),
    (
        "ERROR_CODE_REPORTED",
        lambda p: len(p.error_codes) > 0,
        lambda p: f"Error codes: {', '.join(p.error_codes)}",
    ),
    (
        "HIGH_SPEED",
        lambda p: p.speed_mps > 8.0,
        lambda p: f"Speed {p.speed_mps:.1f} m/s exceeds 8.0 m/s limit",
    ),
]


async def ingest(session: AsyncSession, payload: TelemetryEventCreate) -> TelemetryEvent:
    # 1. Persist the raw telemetry event. flush() populates event.id so anomaly
    #    records can reference it via FK within the same transaction.
    event = await telemetry_repo.create(session, payload)

    # 2. Update the vehicle's cached state (last-write-wins; concurrent writes
    #    will serialize at the PostgreSQL row level).
    await vehicle_repo.update_state(
        session,
        vehicle_id=payload.vehicle_id,
        status=payload.status,
        battery_pct=payload.battery_pct,
        last_seen_at=payload.timestamp,
    )

    # 3. Detect anomalies and persist each one in the same transaction.
    for anomaly_type, predicate, describe in _ANOMALY_RULES:
        if predicate(payload):  # type: ignore[operator]
            await anomaly_repo.create(
                session,
                vehicle_id=payload.vehicle_id,
                timestamp=payload.timestamp,
                anomaly_type=anomaly_type,
                description=describe(payload),  # type: ignore[operator]
                telemetry_event_id=event.id,
            )

    # 4. Atomically increment the zone counter — single SQL statement, no
    #    Python read-modify-write, safe under concurrent entries.
    if payload.zone_entered:
        await zone_repo.increment(session, payload.zone_entered)

    await session.commit()
    return event
