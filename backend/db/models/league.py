from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, BigIntPK, TimestampMixin

if TYPE_CHECKING:
    from backend.db.models.user import User
    from backend.db.models.meet import Meet
    from backend.db.models.league_member import LeagueMember


class League(BigIntPK, TimestampMixin, Base):
    __tablename__ = "leagues"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    meet_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("meets.id"), index=True, nullable=False
    )
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="setup"
    )
    roster_size: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="8"
    )
    draft_order: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)

    owner: Mapped[User] = relationship(back_populates="owned_leagues")
    meet: Mapped[Meet] = relationship(back_populates="leagues")
    members: Mapped[list[LeagueMember]] = relationship(
        back_populates="league", lazy="selectin"
    )
