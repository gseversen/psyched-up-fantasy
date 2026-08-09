from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, BigIntPK

if TYPE_CHECKING:
    from backend.db.models.meet import Meet
    from backend.db.models.event import Event
    from backend.db.models.meet_entry import MeetEntry
    from backend.db.models.result import Result


class MeetEvent(BigIntPK, Base):
    __tablename__ = "meet_events"
    __table_args__ = (
        UniqueConstraint("meet_id", "event_number", name="uq_meet_events_meet_number"),
    )

    meet_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("meets.id"), index=True, nullable=False
    )
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("events.id"), index=True, nullable=False
    )
    event_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    meet: Mapped[Meet] = relationship(back_populates="meet_events")
    event: Mapped[Event] = relationship(back_populates="meet_events")
    entries: Mapped[list[MeetEntry]] = relationship(
        back_populates="meet_event", lazy="selectin"
    )
    results: Mapped[list[Result]] = relationship(
        back_populates="meet_event", lazy="selectin"
    )
