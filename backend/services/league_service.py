from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.league import League
from backend.db.models.league_member import LeagueMember
from backend.db.models.meet import Meet
from backend.db.models.user import User
from backend.schemas.leagues import (
    LeagueCreateRequest,
    LeagueMemberResponse,
    LeagueResponse,
    LeagueStatus,
    MeetSummary,
    UserSummary,
)
from backend.services.errors import LeagueError


async def load_league(
    session: AsyncSession, league_id: int, *, expire: bool = False
) -> League | None:
    if expire:
        cached = await session.get(League, league_id)
        if cached is not None:
            session.expire(cached)
    stmt = (
        select(League)
        .where(League.id == league_id)
        .options(
            selectinload(League.members).selectinload(LeagueMember.user),
            selectinload(League.owner),
            selectinload(League.meet),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def require_membership(league: League, user_id: int) -> LeagueMember:
    member = next((m for m in league.members if m.user_id == user_id), None)
    if member is None:
        raise LeagueError(403, "Not a member of this league")
    return member


def _to_response(league: League) -> LeagueResponse:
    return LeagueResponse(
        id=league.id,
        name=league.name,
        meet=MeetSummary(id=league.meet.id, name=league.meet.name),
        status=LeagueStatus(league.status),
        roster_size=league.roster_size,
        member_count=len(league.members),
        owner=UserSummary(id=league.owner.id, username=league.owner.username),
    )


async def create_league(
    session: AsyncSession, user: User, payload: LeagueCreateRequest
) -> LeagueResponse:
    meet = await session.get(Meet, payload.meet_id)
    if meet is None:
        raise LeagueError(422, "meet_id does not exist")

    league = League(
        name=payload.name,
        meet_id=payload.meet_id,
        owner_id=user.id,
        status=LeagueStatus.SETUP.value,
        roster_size=payload.roster_size,
    )
    session.add(league)
    await session.flush()

    owner_member = LeagueMember(
        league_id=league.id,
        user_id=user.id,
        role="owner",
    )
    session.add(owner_member)
    await session.flush()

    loaded = await load_league(session, league.id, expire=True)
    assert loaded is not None
    return _to_response(loaded)


async def get_league(
    session: AsyncSession, user: User, league_id: int
) -> LeagueResponse:
    league = await load_league(session, league_id)
    if league is None:
        raise LeagueError(404, "League not found")
    require_membership(league, user.id)
    return _to_response(league)


async def join_league(
    session: AsyncSession, user: User, league_id: int
) -> LeagueResponse:
    league = await load_league(session, league_id)
    if league is None:
        raise LeagueError(404, "League not found")
    if league.status != LeagueStatus.SETUP.value:
        raise LeagueError(409, "League is not accepting new members")
    if any(m.user_id == user.id for m in league.members):
        raise LeagueError(409, "Already a member of this league")

    session.add(
        LeagueMember(league_id=league.id, user_id=user.id, role="member")
    )
    await session.flush()

    loaded = await load_league(session, league.id, expire=True)
    assert loaded is not None
    return _to_response(loaded)


async def list_members(
    session: AsyncSession, user: User, league_id: int
) -> list[LeagueMemberResponse]:
    league = await load_league(session, league_id)
    if league is None:
        raise LeagueError(404, "League not found")
    require_membership(league, user.id)
    return [
        LeagueMemberResponse(
            user_id=m.user_id,
            username=m.user.username,
            role=m.role,
        )
        for m in sorted(league.members, key=lambda m: m.id)
    ]
