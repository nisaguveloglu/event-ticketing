from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReservationItem(Base):
    __tablename__ = "reservation_items"
    __table_args__ = (
        UniqueConstraint(
            "reservation_id",
            "event_seat_id",
            name="uq_reservation_items_res_event_seat",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"),
        nullable=False,
    )
    event_seat_id: Mapped[int] = mapped_column(
        ForeignKey("event_seats.id"),
        nullable=False,
    )
    unit_price_kurus: Mapped[int] = mapped_column(Integer, nullable=False)

    reservation = relationship("Reservation", back_populates="items")
    event_seat = relationship("EventSeat")
