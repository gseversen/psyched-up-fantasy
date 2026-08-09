from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from backend.db.models.league import League
    from backend.db.models.user import User
    from backend.db.models.roster_pick import RosterPick


class LeagueMember(BigIntPK, Base):
    __tablename__ = "league_members"
    __table_args__ = (
        UniqueConstraint("league_id", "user_id", name="uq_league_members_league_user"),
    )

    league_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("leagues.id"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    league: Mapped[League] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="league_memberships")
    roster_picks: Mapped[list[RosterPick]] = relationship(
        back_populates="league_member", lazy="selectin"
    )
