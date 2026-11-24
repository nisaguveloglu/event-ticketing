from datetime import datetime, timezone
import enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TicketStatus(str, enum.Enum):
    VALID = "VALID"
    USED = "USED"


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("event_id", "seat_id", name="uq_tickets_event_seat"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"),
        nullable=True,
    )

    ticket_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id"),
        nullable=False,
    )

    seat_id: Mapped[int] = mapped_column(
        ForeignKey("seats.id"),
        nullable=False,
    )

    unit_price_kurus: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=TicketStatus.VALID.value,
        server_default=TicketStatus.VALID.value,
        nullable=False,
    )

    session_id: Mapped[str] = mapped_column(
        String(100),
        default="guest",
        server_default="guest",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    order = relationship("Order", back_populates="tickets")
    event = relationship("Event")
    seat = relationship("Seat")
    check_in = relationship("CheckIn", back_populates="ticket", uselist=False)
