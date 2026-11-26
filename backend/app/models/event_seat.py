from sqlalchemy import Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.seat import SeatStatus


class EventSeat(Base):
    __tablename__ = "event_seats"
    __table_args__ = (
        UniqueConstraint("event_id", "seat_id", name="uq_event_seats_event_seat"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_categories.id"),
        nullable=False,
    )
    price_kurus: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SeatStatus] = mapped_column(
        Enum(SeatStatus),
        default=SeatStatus.AVAILABLE,
        nullable=False,
    )
    current_reservation_id: Mapped[int | None] = mapped_column(
        ForeignKey("reservations.id"),
        nullable=True,
    )

    event = relationship("Event", back_populates="event_seats")
    seat = relationship("Seat")
    category = relationship("TicketCategory")
    current_reservation = relationship("Reservation")
