from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.athlete import Athlete
from backend.db.models.meet_entry import MeetEntry
from backend.db.models.meet_event import MeetEvent
from backend.db.models.result import Result
from backend.schemas.ingestion import (
    AthleteUpsertRequest,
    AthleteUpsertResponse,
    BatchUpsertResponse,
    EntryBatchUpsertRequest,
    EntryUpsertRequest,
    ResultBatchUpsertRequest,
    ResultUpsertRequest,
    UpsertAction,
    UpsertResponse,
)


class ForeignKeyError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


async def _check_meet_event_exists(session: AsyncSession, meet_event_id: int) -> None:
    result = await session.execute(
        select(MeetEvent.id).where(MeetEvent.id == meet_event_id)
    )
    if result.scalar_one_or_none() is None:
        raise ForeignKeyError(f"meet_event_id={meet_event_id} does not exist")


async def _check_athlete_exists(session: AsyncSession, athlete_id: int) -> None:
    result = await session.execute(
        select(Athlete.id).where(Athlete.id == athlete_id)
    )
    if result.scalar_one_or_none() is None:
        raise ForeignKeyError(f"athlete_id={athlete_id} does not exist")


async def upsert_athlete(
    session: AsyncSession, payload: AthleteUpsertRequest
) -> AthleteUpsertResponse:
    stmt = select(Athlete).where(
        func.lower(Athlete.first_name) == payload.first_name.lower(),
        func.lower(Athlete.last_name) == payload.last_name.lower(),
        Athlete.team_key == payload.team_key,
        Athlete.gender == payload.gender,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        return AthleteUpsertResponse(id=existing.id, created=False)

    athlete = Athlete(
        first_name=payload.first_name,
        last_name=payload.last_name,
        gender=payload.gender,
        team_display=payload.team_display,
        team_key=payload.team_key,
    )
    session.add(athlete)
    await session.flush()
    return AthleteUpsertResponse(id=athlete.id, created=True)


async def upsert_entry(
    session: AsyncSession, payload: EntryUpsertRequest
) -> UpsertResponse:
    await _check_meet_event_exists(session, payload.meet_event_id)
    await _check_athlete_exists(session, payload.athlete_id)

    existing = await session.execute(
        select(MeetEntry).where(
            MeetEntry.meet_event_id == payload.meet_event_id,
            MeetEntry.athlete_id == payload.athlete_id,
        )
    )
    row = existing.scalar_one_or_none()

    ingested_at = payload.resolved_ingested_at()

    if row is None:
        stmt = pg_insert(MeetEntry).values(
            meet_event_id=payload.meet_event_id,
            athlete_id=payload.athlete_id,
            seed_time_cs=payload.seed_time_cs,
            lane=payload.lane,
            entry_status=payload.entry_status.value,
            source_hash=payload.source_hash,
            ingested_at=ingested_at,
        )
        result = await session.execute(stmt.returning(MeetEntry.id))
        entry_id = result.scalar_one()
        return UpsertResponse(id=entry_id, action=UpsertAction.CREATED)

    if row.source_hash == payload.source_hash:
        return UpsertResponse(id=row.id, action=UpsertAction.UNCHANGED)

    row.seed_time_cs = payload.seed_time_cs
    row.lane = payload.lane
    row.entry_status = payload.entry_status.value
    row.source_hash = payload.source_hash
    row.ingested_at = ingested_at
    await session.flush()
    return UpsertResponse(id=row.id, action=UpsertAction.UPDATED)


async def upsert_result(
    session: AsyncSession, payload: ResultUpsertRequest
) -> UpsertResponse:
    await _check_meet_event_exists(session, payload.meet_event_id)
    await _check_athlete_exists(session, payload.athlete_id)

    existing = await session.execute(
        select(Result).where(
            Result.meet_event_id == payload.meet_event_id,
            Result.athlete_id == payload.athlete_id,
        )
    )
    row = existing.scalar_one_or_none()

    ingested_at = payload.resolved_ingested_at()

    if row is None:
        stmt = pg_insert(Result).values(
            meet_event_id=payload.meet_event_id,
            athlete_id=payload.athlete_id,
            final_time_cs=payload.final_time_cs,
            place=payload.place,
            result_status=payload.result_status.value,
            source_type=payload.source_type.value,
            source_uri=payload.source_uri,
            source_hash=payload.source_hash,
            ingested_at=ingested_at,
        )
        result = await session.execute(stmt.returning(Result.id))
        result_id = result.scalar_one()
        return UpsertResponse(id=result_id, action=UpsertAction.CREATED)

    if row.source_hash == payload.source_hash:
        return UpsertResponse(id=row.id, action=UpsertAction.UNCHANGED)

    row.final_time_cs = payload.final_time_cs
    row.place = payload.place
    row.result_status = payload.result_status.value
    row.source_type = payload.source_type.value
    row.source_uri = payload.source_uri
    row.source_hash = payload.source_hash
    row.ingested_at = ingested_at
    await session.flush()
    return UpsertResponse(id=row.id, action=UpsertAction.UPDATED)


async def batch_upsert_entries(
    session: AsyncSession, payload: EntryBatchUpsertRequest
) -> BatchUpsertResponse:
    counts = {UpsertAction.CREATED: 0, UpsertAction.UPDATED: 0, UpsertAction.UNCHANGED: 0}
    for entry_req in payload.entries:
        resp = await upsert_entry(session, entry_req)
        counts[resp.action] += 1
    await session.flush()
    return BatchUpsertResponse(
        created=counts[UpsertAction.CREATED],
        updated=counts[UpsertAction.UPDATED],
        unchanged=counts[UpsertAction.UNCHANGED],
        total=len(payload.entries),
    )


async def batch_upsert_results(
    session: AsyncSession, payload: ResultBatchUpsertRequest
) -> BatchUpsertResponse:
    counts = {UpsertAction.CREATED: 0, UpsertAction.UPDATED: 0, UpsertAction.UNCHANGED: 0}
    for result_req in payload.results:
        resp = await upsert_result(session, result_req)
        counts[resp.action] += 1
    await session.flush()
    return BatchUpsertResponse(
        created=counts[UpsertAction.CREATED],
        updated=counts[UpsertAction.UPDATED],
        unchanged=counts[UpsertAction.UNCHANGED],
        total=len(payload.results),
    )
