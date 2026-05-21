from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ZoneCounter(Base):
    __tablename__ = "zone_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
