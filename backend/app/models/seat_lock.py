from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SeatLock(Base):
    __tablename__ = "seat_locks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    seat_id: Mapped[int] = mapped_column(
        ForeignKey("seats.id"),
        nullable=False,
        unique=True,
    )

    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    seat = relationship("Seat")