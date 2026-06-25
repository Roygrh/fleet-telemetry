# Side-effect imports — registers all ORM classes with Base.metadata so that
# Alembic's env.py sees them when it does `import app.models`.
from app.models.vehicle import Vehicle
from app.models.telemetry import TelemetryEvent
from app.models.zone import ZoneCounter
from app.models.anomaly import Anomaly
from app.models.mission import Mission
from app.models.maintenance import MaintenanceRecord
from app.models.teleoperation import TeleoperationSession

__all__ = [
    "Vehicle",
    "TelemetryEvent",
    "ZoneCounter",
    "Anomaly",
    "Mission",
    "MaintenanceRecord",
    "TeleoperationSession",
]
