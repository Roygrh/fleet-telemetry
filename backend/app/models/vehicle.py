from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import VehicleStatus


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    current_status: Mapped[VehicleStatus] = mapped_column(
        Enum(VehicleStatus, name="vehiclestatus"),
        nullable=False,
        server_default="idle",
    )
    battery_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    telemetry_events: Mapped[list["TelemetryEvent"]] = relationship(  # noqa: F821
        "TelemetryEvent", back_populates="vehicle"
    )
    missions: Mapped[list["Mission"]] = relationship(  # noqa: F821
        "Mission", back_populates="vehicle"
    )
    anomalies: Mapped[list["Anomaly"]] = relationship(  # noqa: F821
        "Anomaly", back_populates="vehicle"
    )
    maintenance_records: Mapped[list["MaintenanceRecord"]] = relationship(  # noqa: F821
        "MaintenanceRecord", back_populates="vehicle"
    )
