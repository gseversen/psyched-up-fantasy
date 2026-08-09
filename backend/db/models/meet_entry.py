from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from backend.db.models.meet_event import MeetEvent
    from backend.db.models.athlete import Athlete


class MeetEntry(BigIntPK, Base):
    __tablename__ = "meet_entries"
    __table_args__ = (
        UniqueConstraint(
            "meet_event_id", "athlete_id", name="uq_meet_entries_event_athlete"
        ),
    )

    meet_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("meet_events.id"), index=True, nullable=False
    )
    athlete_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("athletes.id"), index=True, nullable=False
    )
    seed_time_cs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lane: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_status: Mapped[str] = mapped_column(String(16), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    meet_event: Mapped[MeetEvent] = relationship(back_populates="entries")
    athlete: Mapped[Athlete] = relationship(back_populates="entries")
