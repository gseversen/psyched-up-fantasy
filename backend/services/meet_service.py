from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.meet import Meet
from backend.db.models.meet_event import MeetEvent
from backend.db.models.result import Result
from backend.schemas.meets import AthleteSummary, MeetResponse, ResultResponse


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
