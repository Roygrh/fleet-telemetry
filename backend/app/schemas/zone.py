from pydantic import BaseModel, ConfigDict


class ZoneCountItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    zone_id: str
    entry_count: int


class ZoneCountResponse(BaseModel):
    zones: list[ZoneCountItem]
