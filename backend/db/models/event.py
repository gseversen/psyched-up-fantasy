from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from backend.db.models.meet_event import MeetEvent


class Event(BigIntPK, Base):
    __tablename__ = "events"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    stroke: Mapped[str] = mapped_column(String(32), nullable=False)
    distance: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)

    meet_events: Mapped[list[MeetEvent]] = relationship(
        back_populates="event", lazy="selectin"
    )
