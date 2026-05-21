from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import VehicleStatus


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    __table_args__ = (
        Index("ix_telemetry_vehicle_timestamp", "vehicle_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[str] = mapped_column(
        String(10), ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    battery_pct: Mapped[float] = mapped_column(Float, nullable=False)
    speed_mps: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(
        # create_type=False — vehiclestatus is created by Vehicle.current_status
        Enum(VehicleStatus, name="vehiclestatus", create_type=False),
        nullable=False,
    )
    error_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    zone_entered: Mapped[str | None] = mapped_column(String(50), nullable=True)

    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="telemetry_events")  # noqa: F821
    anomalies: Mapped[list["Anomaly"]] = relationship("Anomaly", back_populates="telemetry_event")  # noqa: F821
