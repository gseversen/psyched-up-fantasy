from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, BigIntPK, TimestampMixin

if TYPE_CHECKING:
    from backend.db.models.league import League
    from backend.db.models.league_member import LeagueMember


class User(BigIntPK, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)

    owned_leagues: Mapped[list[League]] = relationship(
        back_populates="owner", lazy="selectin"
    )
    league_memberships: Mapped[list[LeagueMember]] = relationship(
        back_populates="user", lazy="selectin"
    )
