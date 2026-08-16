"""Snake-draft lifecycle for fantasy leagues.

Draft order is join order: `league_members.id` ascending (owner first,
then each joiner). It is not randomized, so tests and restarts are
deterministic.

Snake: round 0 is pick 1→N, round 1 is N→1, repeating until every member
has `roster_size` athletes.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models.league import League
from backend.db.models.league_member import LeagueMember
from backend.db.models.meet_entry import MeetEntry
from backend.db.models.meet_event import MeetEvent
from backend.db.models.roster_pick import RosterPick
from backend.db.models.user import User
from backend.schemas.leagues import (
    DraftStateResponse,
    LeagueRosterResponse,
    LeagueStatus,
    MemberRosterResponse,
    RosterPickResponse,
)
from backend.schemas.meets import AthleteSummary
from backend.services.errors import LeagueError
from backend.services.league_service import load_league, require_membership


def snake_drafter_user_id(draft_order: list[int], pick_number: int) -> int:
    """Return whose turn it is for a 1-based overall pick number."""
    n = len(draft_order)
    if n == 0:
        raise ValueError("draft_order is empty")
    index = pick_number - 1
    round_num = index // n
    pos = index % n
    if round_num % 2 == 0:
        return draft_order[pos]
    return draft_order[n - 1 - pos]


async def _lock_league(session: AsyncSession, league_id: int) -> League:
    stmt = select(League).where(League.id == league_id).with_for_update()
    result = await session.execute(stmt)
    league = result.scalar_one_or_none()
    if league is None:
        raise LeagueError(404, "League not found")
    return league


async def _picks_for_league(
    session: AsyncSession, league_id: int
) -> list[RosterPick]:
    stmt = (
        select(RosterPick)
        .join(RosterPick.league_member)
        .where(LeagueMember.league_id == league_id)
        .options(
            selectinload(RosterPick.athlete),
            selectinload(RosterPick.league_member).selectinload(LeagueMember.user),
        )
        .order_by(RosterPick.pick_number)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _entered_athlete_ids(session: AsyncSession, meet_id: int) -> set[int]:
    stmt = (
        select(MeetEntry.athlete_id)
        .join(MeetEvent)
        .where(MeetEvent.meet_id == meet_id)
        .distinct()
    )
    result = await session.execute(stmt)
    return set(result.scalars().all())


async def _build_state(
    session: AsyncSession, league: League
) -> DraftStateResponse:
    picks = await _picks_for_league(session, league.id)
    member_count = len(league.members)
    total_picks = league.roster_size * member_count
    picks_made = len(picks)
    order = list(league.draft_order or [])

    current_pick_number: int | None = None
    current_drafter_user_id: int | None = None
    if league.status == LeagueStatus.DRAFTING.value and picks_made < total_picks and order:
        current_pick_number = picks_made + 1
        current_drafter_user_id = snake_drafter_user_id(order, current_pick_number)

    entered = await _entered_athlete_ids(session, league.meet_id)
    picked_ids = {p.athlete_id for p in picks}
    available = len(entered - picked_ids)

    return DraftStateResponse(
        league_id=league.id,
        status=LeagueStatus(league.status),
        current_pick_number=current_pick_number,
        current_drafter_user_id=current_drafter_user_id,
        picks_made=picks_made,
        total_picks=total_picks,
        available_athletes=available,
        draft_order=order,
        roster_size=league.roster_size,
    )


async def start_draft(
    session: AsyncSession, user: User, league_id: int
) -> DraftStateResponse:
    await _lock_league(session, league_id)
    league = await load_league(session, league_id, expire=True)
    if league is None:
        raise LeagueError(404, "League not found")
    require_membership(league, user.id)
    if league.owner_id != user.id:
        raise LeagueError(403, "Only the owner can start the draft")
    if league.status != LeagueStatus.SETUP.value:
        raise LeagueError(409, "Draft has already started")
    if len(league.members) < 2:
        raise LeagueError(422, "At least 2 members are required to start the draft")

    members = sorted(league.members, key=lambda m: m.id)
    league.draft_order = [m.user_id for m in members]
    league.status = LeagueStatus.DRAFTING.value
    await session.flush()
    return await _build_state(session, league)


async def get_draft_state(
    session: AsyncSession, user: User, league_id: int
) -> DraftStateResponse:
    league = await load_league(session, league_id)
    if league is None:
        raise LeagueError(404, "League not found")
    require_membership(league, user.id)
    return await _build_state(session, league)


async def make_pick(
    session: AsyncSession, user: User, league_id: int, athlete_id: int
) -> DraftStateResponse:
    await _lock_league(session, league_id)
    league = await load_league(session, league_id, expire=True)
    if league is None:
        raise LeagueError(404, "League not found")
    member = require_membership(league, user.id)

    if league.status == LeagueStatus.COMPLETE.value:
        raise LeagueError(409, "Draft is complete")
    if league.status != LeagueStatus.DRAFTING.value:
        raise LeagueError(409, "Draft has not started")

    picks = await _picks_for_league(session, league.id)
    order = list(league.draft_order or [])
    if not order:
        raise LeagueError(409, "Draft order is not set")

    next_pick = len(picks) + 1
    current_user_id = snake_drafter_user_id(order, next_pick)
    if user.id != current_user_id:
        raise LeagueError(403, "It is not your turn to pick")

    entered = await _entered_athlete_ids(session, league.meet_id)
    if athlete_id not in entered:
        raise LeagueError(422, "Athlete is not in the meet entry pool")

    if any(p.athlete_id == athlete_id for p in picks):
        raise LeagueError(409, "Athlete has already been picked in this league")

    member_pick_count = sum(1 for p in picks if p.league_member_id == member.id)
    if member_pick_count >= league.roster_size:
        raise LeagueError(409, "Roster is already full")

    session.add(
        RosterPick(
            league_member_id=member.id,
            athlete_id=athlete_id,
            pick_number=next_pick,
            picked_at=datetime.now(timezone.utc),
        )
    )
    await session.flush()

    if next_pick >= league.roster_size * len(league.members):
        league.status = LeagueStatus.COMPLETE.value
        await session.flush()

    return await _build_state(session, league)


async def get_roster(
    session: AsyncSession, user: User, league_id: int
) -> LeagueRosterResponse:
    league = await load_league(session, league_id)
    if league is None:
        raise LeagueError(404, "League not found")
    require_membership(league, user.id)

    picks = await _picks_for_league(session, league.id)
    picks_by_member: dict[int, list[RosterPick]] = {}
    for pick in picks:
        picks_by_member.setdefault(pick.league_member_id, []).append(pick)

    members = sorted(league.members, key=lambda m: m.id)
    return LeagueRosterResponse(
        league_id=league.id,
        members=[
            MemberRosterResponse(
                user_id=m.user_id,
                username=m.user.username,
                role=m.role,
                picks=[
                    RosterPickResponse(
                        pick_number=p.pick_number,
                        picked_at=p.picked_at,
                        athlete=AthleteSummary(
                            id=p.athlete.id,
                            first_name=p.athlete.first_name,
                            last_name=p.athlete.last_name,
                            team_display=p.athlete.team_display,
                        ),
                    )
                    for p in picks_by_member.get(m.id, [])
                ],
            )
            for m in members
        ],
    )
