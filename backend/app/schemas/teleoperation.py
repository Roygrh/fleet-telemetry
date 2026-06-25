import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

_VEHICLE_ID_RE = re.compile(r"^v-(\d{2})$")
_VALID_STATUSES = frozenset({"requested", "claimed", "active", "released", "completed", "failed"})
_VALID_COMMANDS = frozenset({"forward", "backward", "left", "right", "stop"})


def _check_vehicle_id(v: str) -> str:
    m = _VEHICLE_ID_RE.match(v)
    if not m or not (1 <= int(m.group(1)) <= 50):
        raise ValueError("vehicle_id must be v-01 through v-50")
    return v


class TeleoperationSessionCreate(BaseModel):
    vehicle_id: str
    reason: str | None = None

    @field_validator("vehicle_id")
    @classmethod
    def check_vehicle_id(cls, v: str) -> str:
        return _check_vehicle_id(v)


class TeleoperationSessionClaim(BaseModel):
    operator_id: str = "operator-1"


class TeleoperationSessionRelease(BaseModel):
    pass


class TeleoperationSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    vehicle_id: str
    status: str
    operator_id: str | None
    reason: str | None
    created_at: datetime
    claimed_at: datetime | None
    released_at: datetime | None
    last_command: str | None
    last_command_at: datetime | None
    last_sensor_payload: dict[str, Any] | None


class OperatorCommandMessage(BaseModel):
    command: Literal["forward", "backward", "left", "right", "stop"]


class VehicleSensorMessage(BaseModel):
    vehicle_id: str
    mode: str
    speed_mps: float
    battery_pct: float
    obstacle_distance_m: float
    connection_quality: str
    camera_frame_label: str
    last_command_echo: str | None = None

    @field_validator("vehicle_id")
    @classmethod
    def check_vehicle_id(cls, v: str) -> str:
        return _check_vehicle_id(v)
