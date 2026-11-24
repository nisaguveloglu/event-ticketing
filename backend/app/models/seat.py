import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, text
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
    row_label: Mapped[str] = mapped_column(String(10), default="A", server_default="A", nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_order: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)

    segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("seat_segments.id"),
        nullable=True,
    )

    x: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    y: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)

    is_accessible: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )

    status: Mapped[SeatStatus] = mapped_column(
        Enum(SeatStatus),
        default=SeatStatus.AVAILABLE,
        nullable=False,
    )

    hall = relationship(
        "Hall",
        back_populates="seats",
    )
    segment = relationship(
        "SeatSegment",
        back_populates="seats",
    )

    def __init__(self, **kwargs):
        if "row_label" in kwargs and "row" not in kwargs:
            kwargs["row"] = kwargs["row_label"]
        elif "row" in kwargs and "row_label" not in kwargs:
            kwargs["row_label"] = kwargs["row"]
        super().__init__(**kwargs)
