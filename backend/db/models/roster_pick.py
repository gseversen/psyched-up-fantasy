from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from backend.db.models.league_member import LeagueMember
    from backend.db.models.athlete import Athlete


class RosterPick(BigIntPK, Base):
    __tablename__ = "roster_picks"
    __table_args__ = (
        UniqueConstraint(
            "league_member_id", "athlete_id", name="uq_roster_picks_member_athlete"
        ),
    )

    league_member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("league_members.id"), index=True, nullable=False
    )
    athlete_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("athletes.id"), index=True, nullable=False
    )
    pick_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    picked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    league_member: Mapped[LeagueMember] = relationship(back_populates="roster_picks")
    athlete: Mapped[Athlete] = relationship(back_populates="roster_picks")
