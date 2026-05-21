import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants.zones import ZONE_SET
from app.models.enums import VehicleStatus

_VEHICLE_ID_RE = re.compile(r"^v-(\d{2})$")


def _validate_vehicle_id(v: str) -> str:
    m = _VEHICLE_ID_RE.match(v)
    if not m or not (1 <= int(m.group(1)) <= 50):
        raise ValueError("vehicle_id must be v-01 through v-50")
    return v


class TelemetryEventCreate(BaseModel):
    vehicle_id: str
    timestamp: datetime
    lat: float
    lon: float
    battery_pct: float = Field(ge=0.0, le=100.0)
    speed_mps: float = Field(ge=0.0)
    status: VehicleStatus
    error_codes: list[str] = []
    zone_entered: str | None = None

    @field_validator("vehicle_id")
    @classmethod
    def check_vehicle_id(cls, v: str) -> str:
        return _validate_vehicle_id(v)

    @field_validator("zone_entered")
    @classmethod
    def check_zone(cls, v: str | None) -> str | None:
        if v is not None and v not in ZONE_SET:
            raise ValueError(f"'{v}' is not a recognised zone")
        return v


class TelemetryEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: str
    timestamp: datetime
    lat: float
    lon: float
    battery_pct: float
    speed_mps: float
    status: VehicleStatus
    error_codes: list[str]
    zone_entered: str | None
