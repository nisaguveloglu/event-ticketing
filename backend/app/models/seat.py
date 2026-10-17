import enum

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SeatStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    LOCKED = "LOCKED"
    SOLD = "SOLD"


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    hall_id: Mapped[int] = mapped_column(
        ForeignKey("halls.id"),
        nullable=False,
    )

    row: Mapped[str] = mapped_column(String(10), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[SeatStatus] = mapped_column(
        Enum(SeatStatus),
        default=SeatStatus.AVAILABLE,
        nullable=False,
    )

    hall = relationship(
        "Hall",
        back_populates="seats",
    )