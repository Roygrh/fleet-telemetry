from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnomalyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: str
    timestamp: datetime
    anomaly_type: str
    description: str
    telemetry_event_id: int | None
