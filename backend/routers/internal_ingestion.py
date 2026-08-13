from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.dependencies.auth import verify_ingestion_api_key
from backend.schemas.ingestion import (
    AthleteUpsertRequest,
    AthleteUpsertResponse,
    BatchUpsertResponse,
    EntryBatchUpsertRequest,
    EntryUpsertRequest,
    MeetEventsLookupResponse,
    ResultBatchUpsertRequest,
    ResultUpsertRequest,
    UpsertResponse,
)
from backend.services.ingestion_service import (
    ForeignKeyError,
    batch_upsert_entries,
    batch_upsert_results,
    lookup_meet_events,
    upsert_athlete,
    upsert_entry,
    upsert_result,
)

router = APIRouter(
    prefix="/internal/v1",
    tags=["ingestion"],
    dependencies=[Depends(verify_ingestion_api_key)],
)


@router.post("/athletes/upsert", response_model=AthleteUpsertResponse)
async def handle_athlete_upsert(
    payload: AthleteUpsertRequest,
    session: AsyncSession = Depends(get_session),
) -> AthleteUpsertResponse:
    result = await upsert_athlete(session, payload)
    await session.commit()
    return result


@router.post("/entries/upsert", response_model=UpsertResponse)
async def handle_entry_upsert(
    payload: EntryUpsertRequest,
    session: AsyncSession = Depends(get_session),
) -> UpsertResponse:
    try:
        result = await upsert_entry(session, payload)
    except ForeignKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.detail
        )
    await session.commit()
    return result


@router.post("/entries/batch", response_model=BatchUpsertResponse)
async def handle_entry_batch(
    payload: EntryBatchUpsertRequest,
    session: AsyncSession = Depends(get_session),
) -> BatchUpsertResponse:
    try:
        result = await batch_upsert_entries(session, payload)
    except ForeignKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.detail
        )
    await session.commit()
    return result


@router.post("/results/upsert", response_model=UpsertResponse)
async def handle_result_upsert(
    payload: ResultUpsertRequest,
    session: AsyncSession = Depends(get_session),
) -> UpsertResponse:
    try:
        result = await upsert_result(session, payload)
    except ForeignKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.detail
        )
    await session.commit()
    return result


@router.post("/results/batch", response_model=BatchUpsertResponse)
async def handle_result_batch(
    payload: ResultBatchUpsertRequest,
    session: AsyncSession = Depends(get_session),
) -> BatchUpsertResponse:
    try:
        result = await batch_upsert_results(session, payload)
    except ForeignKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.detail
        )
    await session.commit()
    return result


@router.get("/meets/{meet_id}/events", response_model=MeetEventsLookupResponse)
async def handle_meet_events_lookup(
    meet_id: int,
    session: AsyncSession = Depends(get_session),
) -> MeetEventsLookupResponse:
    return await lookup_meet_events(session, meet_id)
