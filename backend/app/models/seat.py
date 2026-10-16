from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    hall_id: Mapped[int] = mapped_column(
        ForeignKey("halls.id"),
        nullable=False,
    )

    row: Mapped[str] = mapped_column(String(10), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)

    hall = relationship(
        "Hall",
        back_populates="seats",
    )