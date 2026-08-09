from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, BigIntPK, TimestampMixin

if TYPE_CHECKING:
    from backend.db.models.league import League
    from backend.db.models.meet_event import MeetEvent


class Meet(BigIntPK, TimestampMixin, Base):
    __tablename__ = "meets"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    meet_events: Mapped[list[MeetEvent]] = relationship(
        back_populates="meet", lazy="selectin"
    )
    leagues: Mapped[list[League]] = relationship(
        back_populates="meet", lazy="selectin"
    )
