from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import VehicleStatus
from app.schemas.anomaly import AnomalyResponse


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vehicle_id: str
    current_status: VehicleStatus
    battery_pct: float | None
    last_seen_at: datetime | None
    # Populated by the service layer; not a direct ORM column.
    latest_anomaly: AnomalyResponse | None = None


class VehicleStatusUpdate(BaseModel):
    status: VehicleStatus
