from pydantic import BaseModel


class FleetStateResponse(BaseModel):
    idle: int
    moving: int
    charging: int
    fault: int
    total: int
