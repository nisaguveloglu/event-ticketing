from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    hall_id: Mapped[int] = mapped_column(
        ForeignKey("halls.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    hall = relationship("Hall")
