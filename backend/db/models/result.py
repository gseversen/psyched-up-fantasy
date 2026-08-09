from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from backend.db.models.meet_event import MeetEvent
    from backend.db.models.athlete import Athlete


class Result(BigIntPK, Base):
    __tablename__ = "results"
    __table_args__ = (
        UniqueConstraint(
            "meet_event_id", "athlete_id", name="uq_results_event_athlete"
        ),
    )

    meet_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("meet_events.id"), index=True, nullable=False
    )
    athlete_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("athletes.id"), index=True, nullable=False
    )
    final_time_cs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    place: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_status: Mapped[str] = mapped_column(String(16), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False)

    meet_event: Mapped[MeetEvent] = relationship(back_populates="results")
    athlete: Mapped[Athlete] = relationship(back_populates="results")
