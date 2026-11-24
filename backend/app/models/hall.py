from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Hall(Base):
    __tablename__ = "halls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_x: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    stage_y: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    seats = relationship(
        "Seat",
        back_populates="hall",
        cascade="all, delete-orphan",
    )
    segments = relationship(
        "SeatSegment",
        back_populates="hall",
        cascade="all, delete-orphan",
    )
