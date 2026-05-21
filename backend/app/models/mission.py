from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import MissionStatus


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[str] = mapped_column(
        String(10), ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[MissionStatus] = mapped_column(
        Enum(MissionStatus, name="missionstatus"),
        nullable=False,
        server_default="active",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="missions")  # noqa: F821
