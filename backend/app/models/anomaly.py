from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Anomaly(Base):
    __tablename__ = "anomalies"
    __table_args__ = (
        Index("ix_anomaly_vehicle_timestamp", "vehicle_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[str] = mapped_column(
        String(10), ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    telemetry_event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("telemetry_events.id", ondelete="SET NULL"), nullable=True
    )

    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="anomalies")  # noqa: F821
    telemetry_event: Mapped["TelemetryEvent | None"] = relationship(  # noqa: F821
        "TelemetryEvent", back_populates="anomalies"
    )
