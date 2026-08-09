from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, BigIntPK, TimestampMixin

if TYPE_CHECKING:
    from backend.db.models.meet_entry import MeetEntry
    from backend.db.models.result import Result
    from backend.db.models.roster_pick import RosterPick


class Athlete(BigIntPK, TimestampMixin, Base):
    __tablename__ = "athletes"

    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)
    team_display: Mapped[str] = mapped_column(String(256), nullable=False)
    team_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    entries: Mapped[list[MeetEntry]] = relationship(
        back_populates="athlete", lazy="selectin"
    )
    results: Mapped[list[Result]] = relationship(
        back_populates="athlete", lazy="selectin"
    )
    roster_picks: Mapped[list[RosterPick]] = relationship(
        back_populates="athlete", lazy="selectin"
    )
