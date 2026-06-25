import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TeleoperationSession(Base):
    __tablename__ = "teleoperation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    vehicle_id: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"),
        nullable=False,
    )
    # String status avoids a new PostgreSQL enum type and its migration complexity.
    # Valid values: requested, active, released, failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="requested")
    operator_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_command: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_command_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sensor_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    vehicle: Mapped["Vehicle"] = relationship("Vehicle", foreign_keys=[vehicle_id])  # noqa: F821
