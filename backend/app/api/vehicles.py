from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.vehicle import VehicleResponse, VehicleStatusUpdate
from app.services import vehicle as vehicle_service

router = APIRouter()


@router.get("", response_model=list[VehicleResponse])
async def list_vehicles(
    db: AsyncSession = Depends(get_db),
) -> list[VehicleResponse]:
    return await vehicle_service.list_vehicles(db)


@router.patch("/{vehicle_id}/status", response_model=VehicleResponse)
async def update_vehicle_status(
    vehicle_id: str,
    body: VehicleStatusUpdate,
    db: AsyncSession = Depends(get_db),
) -> VehicleResponse:
    vehicle = await vehicle_service.update_status(db, vehicle_id, body.status)
    return VehicleResponse(
        vehicle_id=vehicle.vehicle_id,
        current_status=vehicle.current_status,
        battery_pct=vehicle.battery_pct,
        last_seen_at=vehicle.last_seen_at,
    )
