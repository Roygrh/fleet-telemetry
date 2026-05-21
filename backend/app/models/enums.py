import enum


class VehicleStatus(str, enum.Enum):
    idle = "idle"
    moving = "moving"
    charging = "charging"
    fault = "fault"


class MissionStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"
    completed = "completed"


class MaintenanceStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
