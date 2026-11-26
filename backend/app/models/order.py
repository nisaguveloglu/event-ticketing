from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"),
        unique=True,
        nullable=False,
    )
    guest_session_id: Mapped[int] = mapped_column(
        ForeignKey("guest_sessions.id"),
        nullable=False,
    )
    total_price_kurus: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10),
        default="TRY",
        server_default="TRY",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    reservation = relationship("Reservation")
    guest_session = relationship("GuestSession")
    tickets = relationship("Ticket", back_populates="order")
    deliveries = relationship("EmailDelivery", back_populates="order")
