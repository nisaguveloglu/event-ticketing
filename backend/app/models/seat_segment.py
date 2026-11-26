from sqlalchemy import Boolean, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SeatSegment(Base):
    __tablename__ = "seat_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"), nullable=False)
    row_label: Mapped[str] = mapped_column(String(10), nullable=False)
    orphan_exempt: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )

    hall = relationship("Hall", back_populates="segments")
    seats = relationship("Seat", back_populates="segment")
