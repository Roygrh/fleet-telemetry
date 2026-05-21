from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VehicleStatus
from app.models.vehicle import Vehicle
from app.repositories import anomaly as anomaly_repo
from app.repositories import maintenance as maintenance_repo
from app.repositories import mission as mission_repo
from app.repositories import vehicle as vehicle_repo
from app.schemas.anomaly import AnomalyResponse
from app.schemas.vehicle import VehicleResponse


async def list_vehicles(session: AsyncSession) -> list[VehicleResponse]:
    vehicles = await vehicle_repo.get_all(session)
    # One query to fetch the latest anomaly per vehicle — avoids N+1.
    latest_anomalies = await anomaly_repo.get_latest_per_vehicle(session)

    return [
        VehicleResponse(
            vehicle_id=v.vehicle_id,
            current_status=v.current_status,
            battery_pct=v.battery_pct,
            last_seen_at=v.last_seen_at,
            latest_anomaly=(
                AnomalyResponse.model_validate(latest_anomalies[v.vehicle_id])
                if v.vehicle_id in latest_anomalies
                else None
            ),
        )
        for v in vehicles
    ]


async def update_status(
    session: AsyncSession, vehicle_id: str, new_status: VehicleStatus
) -> Vehicle:
    # Row-level lock prevents a concurrent fault transition from racing
    # with this one — both cannot hold the lock simultaneously.
    vehicle = await vehicle_repo.get_for_update(session, vehicle_id)
    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found",
        )

    if new_status == VehicleStatus.fault:
        now = datetime.now(timezone.utc)
        # Cancel every active mission for this vehicle atomically.
        await mission_repo.cancel_active(session, vehicle_id, now)
        # Create an open maintenance record — this must commit together with
        # the mission cancellation; a rollback undoes both.
        await maintenance_repo.create(
            session,
            vehicle_id=vehicle_id,
            reason="Vehicle entered fault state",
        )

    vehicle.current_status = new_status
    await session.commit()
    await session.refresh(vehicle)
    return vehicle
