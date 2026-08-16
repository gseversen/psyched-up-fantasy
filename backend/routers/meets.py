from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.schemas.meets import (
    EntryResponse,
    MeetEventResponse,
    MeetResponse,
    ResultResponse,
)
from backend.services.meet_service import (
    get_meet,
    get_meet_entries,
    get_meet_events,
    get_meet_results,
)

router = APIRouter(prefix="/api/v1/meets", tags=["meets"])


@router.get("/{meet_id}", response_model=MeetResponse)
async def read_meet(
    meet_id: int,
    session: AsyncSession = Depends(get_session),
) -> MeetResponse:
    meet = await get_meet(session, meet_id)
    if meet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meet not found")
    return meet


@router.get("/{meet_id}/results", response_model=list[ResultResponse])
async def read_meet_results(
    meet_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[ResultResponse]:
    results = await get_meet_results(session, meet_id)
    if results is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meet not found")
    return results


@router.get("/{meet_id}/entries", response_model=list[EntryResponse])
async def read_meet_entries(
    meet_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[EntryResponse]:
    entries = await get_meet_entries(session, meet_id)
    if entries is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meet not found")
    return entries


@router.get("/{meet_id}/events", response_model=list[MeetEventResponse])
async def read_meet_events(
    meet_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[MeetEventResponse]:
    events = await get_meet_events(session, meet_id)
    if events is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meet not found")
    return events
