from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.user import User
from backend.db.session import get_session
from backend.dependencies.user import get_current_user
from backend.schemas.leagues import (
    DraftPickRequest,
    DraftStateResponse,
    LeagueCreateRequest,
    LeagueMemberResponse,
    LeagueResponse,
    LeagueRosterResponse,
)
from backend.services.draft_service import (
    get_draft_state,
    get_roster,
    make_pick,
    start_draft,
)
from backend.services.errors import LeagueError
from backend.services.league_service import (
    create_league,
    get_league,
    join_league,
    list_members,
)

router = APIRouter(prefix="/api/v1/leagues", tags=["leagues"])


def _http_error(exc: LeagueError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("", response_model=LeagueResponse, status_code=201)
async def handle_create_league(
    payload: LeagueCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> LeagueResponse:
    try:
        result = await create_league(session, user, payload)
    except LeagueError as exc:
        _http_error(exc)
    await session.commit()
    return result


@router.get("/{league_id}", response_model=LeagueResponse)
async def handle_get_league(
    league_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> LeagueResponse:
    try:
        return await get_league(session, user, league_id)
    except LeagueError as exc:
        _http_error(exc)


@router.post("/{league_id}/join", response_model=LeagueResponse)
async def handle_join_league(
    league_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> LeagueResponse:
    try:
        result = await join_league(session, user, league_id)
    except LeagueError as exc:
        _http_error(exc)
    await session.commit()
    return result


@router.get("/{league_id}/members", response_model=list[LeagueMemberResponse])
async def handle_list_members(
    league_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[LeagueMemberResponse]:
    try:
        return await list_members(session, user, league_id)
    except LeagueError as exc:
        _http_error(exc)


@router.post("/{league_id}/draft/start", response_model=DraftStateResponse)
async def handle_start_draft(
    league_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> DraftStateResponse:
    try:
        result = await start_draft(session, user, league_id)
    except LeagueError as exc:
        _http_error(exc)
    await session.commit()
    return result


@router.get("/{league_id}/draft/state", response_model=DraftStateResponse)
async def handle_draft_state(
    league_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> DraftStateResponse:
    try:
        return await get_draft_state(session, user, league_id)
    except LeagueError as exc:
        _http_error(exc)


@router.post("/{league_id}/draft/pick", response_model=DraftStateResponse)
async def handle_draft_pick(
    league_id: int,
    payload: DraftPickRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> DraftStateResponse:
    try:
        result = await make_pick(session, user, league_id, payload.athlete_id)
    except LeagueError as exc:
        _http_error(exc)
    await session.commit()
    return result


@router.get("/{league_id}/roster", response_model=LeagueRosterResponse)
async def handle_roster(
    league_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> LeagueRosterResponse:
    try:
        return await get_roster(session, user, league_id)
    except LeagueError as exc:
        _http_error(exc)
