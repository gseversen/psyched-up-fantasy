from sqlalchemy import func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.athlete import Athlete
from backend.db.models.event import Event
from backend.db.models.meet import Meet
from backend.db.models.meet_entry import MeetEntry
from backend.db.models.meet_event import MeetEvent
from backend.db.models.result import Result
from backend.schemas.meets import (
    AthleteSummary,
    EntryResponse,
    MeetEventResponse,
    MeetResponse,
    ResultResponse,
)


async def get_meet(session: AsyncSession, meet_id: int) -> MeetResponse | None:
    stmt = (
        select(Meet)
        .options(selectinload(Meet.meet_events))
        .where(Meet.id == meet_id)
    )
    result = await session.execute(stmt)
    meet = result.scalar_one_or_none()
    if meet is None:
        return None

    return MeetResponse(
        id=meet.id,
        name=meet.name,
        start_date=meet.start_date,
        end_date=meet.end_date,
        event_count=len(meet.meet_events),
    )


async def get_meet_results(
    session: AsyncSession, meet_id: int
) -> list[ResultResponse] | None:
    meet_exists = await session.execute(select(Meet.id).where(Meet.id == meet_id))
    if meet_exists.scalar_one_or_none() is None:
        return None

    stmt = (
        select(Result)
        .join(Result.meet_event)
        .join(MeetEvent.meet)
        .where(Meet.id == meet_id)
        .options(
            selectinload(Result.meet_event).selectinload(MeetEvent.event),
            selectinload(Result.athlete),
        )
        .order_by(MeetEvent.event_number, Result.place)
    )
    rows = await session.execute(stmt)
    results = rows.scalars().all()

    return [
        ResultResponse(
            result_id=r.id,
            event_name=r.meet_event.event.name,
            event_number=r.meet_event.event_number,
            athlete=AthleteSummary(
                id=r.athlete.id,
                first_name=r.athlete.first_name,
                last_name=r.athlete.last_name,
                team_display=r.athlete.team_display,
            ),
            final_time_cs=r.final_time_cs,
            place=r.place,
            result_status=r.result_status,
        )
        for r in results
    ]


async def _meet_exists(session: AsyncSession, meet_id: int) -> bool:
    result = await session.execute(select(Meet.id).where(Meet.id == meet_id))
    return result.scalar_one_or_none() is not None


def _athlete_summary(athlete: Athlete) -> AthleteSummary:
    return AthleteSummary(
        id=athlete.id,
        first_name=athlete.first_name,
        last_name=athlete.last_name,
        team_display=athlete.team_display,
    )


async def get_meet_entries(
    session: AsyncSession, meet_id: int
) -> list[EntryResponse] | None:
    if not await _meet_exists(session, meet_id):
        return None

    stmt = (
        select(MeetEntry)
        .join(MeetEntry.meet_event)
        .where(MeetEvent.meet_id == meet_id)
        .options(
            selectinload(MeetEntry.meet_event).selectinload(MeetEvent.event),
            selectinload(MeetEntry.athlete),
        )
        .order_by(
            MeetEvent.event_number,
            nulls_last(MeetEntry.seed_time_cs.asc()),
        )
    )
    rows = await session.execute(stmt)
    entries = rows.scalars().all()

    return [
        EntryResponse(
            entry_id=e.id,
            event_number=e.meet_event.event_number,
            event_name=e.meet_event.event.name,
            athlete=_athlete_summary(e.athlete),
            seed_time_cs=e.seed_time_cs,
            entry_status=e.entry_status,
        )
        for e in entries
    ]


async def get_meet_events(
    session: AsyncSession, meet_id: int
) -> list[MeetEventResponse] | None:
    if not await _meet_exists(session, meet_id):
        return None

    stmt = (
        select(
            MeetEvent.event_number,
            Event.name,
            Event.gender,
            func.count(MeetEntry.id).label("entry_count"),
        )
        .join(MeetEvent.event)
        .outerjoin(MeetEntry, MeetEntry.meet_event_id == MeetEvent.id)
        .where(MeetEvent.meet_id == meet_id)
        .group_by(MeetEvent.id, MeetEvent.event_number, Event.name, Event.gender)
        .order_by(MeetEvent.event_number)
    )
    rows = await session.execute(stmt)
    return [
        MeetEventResponse(
            event_number=row.event_number,
            event_name=row.name,
            gender=row.gender,
            entry_count=row.entry_count,
        )
        for row in rows.all()
    ]
