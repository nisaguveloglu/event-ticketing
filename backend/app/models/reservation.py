from datetime import datetime, timezone
import enum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReservationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PURCHASED = "PURCHASED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        Index(
            "uq_reservations_active_guest_session",
            "guest_session_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    guest_session_id: Mapped[int] = mapped_column(
        ForeignKey("guest_sessions.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ReservationStatus.ACTIVE.value,
        server_default=ReservationStatus.ACTIVE.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    event = relationship("Event")
    guest_session = relationship("GuestSession")
    items = relationship(
        "ReservationItem",
        back_populates="reservation",
        cascade="all, delete-orphan",
    )
