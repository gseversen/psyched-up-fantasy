from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.athlete import Athlete
from backend.db.models.event import Event
from backend.db.models.meet import Meet
from backend.db.models.meet_entry import MeetEntry
from backend.db.models.meet_event import MeetEvent
from backend.db.models.user import User
from backend.services.draft_service import snake_drafter_user_id


@pytest_asyncio.fixture
async def users(session: AsyncSession) -> list[User]:
    alice = User(username="draft_alice", email="draft_alice@example.com")
    bob = User(username="draft_bob", email="draft_bob@example.com")
    session.add_all([alice, bob])
    await session.flush()
    return [alice, bob]


@pytest_asyncio.fixture
async def pool(session: AsyncSession) -> tuple[Meet, list[Athlete], Athlete]:
    """Meet with four entered athletes plus one athlete not in the pool."""
    event = Event(name="100 Yard Freestyle", stroke="freestyle", distance=100, gender="M")
    session.add(event)
    await session.flush()

    meet = Meet(name="Draft Test Meet", start_date=date(2026, 3, 1), end_date=None)
    session.add(meet)
    await session.flush()

    me = MeetEvent(meet_id=meet.id, event_id=event.id, event_number=1)
    session.add(me)
    await session.flush()

    entered: list[Athlete] = []
    for i, last in enumerate(["Alpha", "Bravo", "Charlie", "Delta"], start=1):
        athlete = Athlete(
            first_name="Swimmer",
            last_name=last,
            gender="M",
            team_display="Test Univ",
            team_key=f"T{i}",
        )
        session.add(athlete)
        entered.append(athlete)
    outsider = Athlete(
        first_name="Out",
        last_name="Sider",
        gender="M",
        team_display="Other Univ",
        team_key="OUT",
    )
    session.add(outsider)
    await session.flush()

    now = datetime.now(timezone.utc)
    for athlete in entered:
        session.add(
            MeetEntry(
                meet_event_id=me.id,
                athlete_id=athlete.id,
                seed_time_cs=5000,
                lane=None,
                entry_status="entered",
                source_hash=f"hash-{athlete.id}",
                ingested_at=now,
            )
        )
    await session.flush()
    return meet, entered, outsider


def _headers(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


async def _create_two_member_league(
    client: AsyncClient,
    alice: User,
    bob: User,
    meet: Meet,
    *,
    roster_size: int = 2,
) -> int:
    created = await client.post(
        "/api/v1/leagues",
        headers=_headers(alice),
        json={"name": "Draft League", "meet_id": meet.id, "roster_size": roster_size},
    )
    assert created.status_code == 201
    league_id = created.json()["id"]
    joined = await client.post(
        f"/api/v1/leagues/{league_id}/join", headers=_headers(bob)
    )
    assert joined.status_code == 200
    return league_id


def test_snake_order_two_members():
    order = [1, 2]
    assert snake_drafter_user_id(order, 1) == 1
    assert snake_drafter_user_id(order, 2) == 2
    assert snake_drafter_user_id(order, 3) == 2
    assert snake_drafter_user_id(order, 4) == 1


@pytest.mark.asyncio
async def test_start_draft_sets_join_order_and_first_turn(
    client: AsyncClient, users: list[User], pool: tuple[Meet, list[Athlete], Athlete]
):
    alice, bob = users
    meet, entered, _outsider = pool
    league_id = await _create_two_member_league(client, alice, bob, meet)

    start = await client.post(
        f"/api/v1/leagues/{league_id}/draft/start", headers=_headers(alice)
    )
    assert start.status_code == 200
    state = start.json()
    assert state["status"] == "drafting"
    assert state["draft_order"] == [alice.id, bob.id]
    assert state["current_pick_number"] == 1
    assert state["current_drafter_user_id"] == alice.id
    assert state["picks_made"] == 0
    assert state["total_picks"] == 4
    assert state["available_athletes"] == len(entered)


@pytest.mark.asyncio
async def test_pick_advances_turn(
    client: AsyncClient, users: list[User], pool: tuple[Meet, list[Athlete], Athlete]
):
    alice, bob = users
    meet, entered, _outsider = pool
    league_id = await _create_two_member_league(client, alice, bob, meet)
    await client.post(
        f"/api/v1/leagues/{league_id}/draft/start", headers=_headers(alice)
    )

    pick = await client.post(
        f"/api/v1/leagues/{league_id}/draft/pick",
        headers=_headers(alice),
        json={"athlete_id": entered[0].id},
    )
    assert pick.status_code == 200
    state = pick.json()
    assert state["picks_made"] == 1
    assert state["current_pick_number"] == 2
    assert state["current_drafter_user_id"] == bob.id
    assert state["available_athletes"] == len(entered) - 1


@pytest.mark.asyncio
async def test_snake_reverses_on_second_round(
    client: AsyncClient, users: list[User], pool: tuple[Meet, list[Athlete], Athlete]
):
    alice, bob = users
    meet, entered, _outsider = pool
    league_id = await _create_two_member_league(client, alice, bob, meet)
    await client.post(
        f"/api/v1/leagues/{league_id}/draft/start", headers=_headers(alice)
    )
    await client.post(
        f"/api/v1/leagues/{league_id}/draft/pick",
        headers=_headers(alice),
        json={"athlete_id": entered[0].id},
    )
    second = await client.post(
        f"/api/v1/leagues/{league_id}/draft/pick",
        headers=_headers(bob),
        json={"athlete_id": entered[1].id},
    )
    assert second.status_code == 200
    state = second.json()
    assert state["picks_made"] == 2
    assert state["current_drafter_user_id"] == bob.id


@pytest.mark.asyncio
async def test_pick_when_not_your_turn_returns_403(
    client: AsyncClient, users: list[User], pool: tuple[Meet, list[Athlete], Athlete]
):
    alice, bob = users
    meet, entered, _outsider = pool
    league_id = await _create_two_member_league(client, alice, bob, meet)
    await client.post(
        f"/api/v1/leagues/{league_id}/draft/start", headers=_headers(alice)
    )
    resp = await client.post(
        f"/api/v1/leagues/{league_id}/draft/pick",
        headers=_headers(bob),
        json={"athlete_id": entered[0].id},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_athlete_across_league_returns_409(
    client: AsyncClient, users: list[User], pool: tuple[Meet, list[Athlete], Athlete]
):
    alice, bob = users
    meet, entered, _outsider = pool
    league_id = await _create_two_member_league(client, alice, bob, meet)
    await client.post(
        f"/api/v1/leagues/{league_id}/draft/start", headers=_headers(alice)
    )
    first = await client.post(
        f"/api/v1/leagues/{league_id}/draft/pick",
        headers=_headers(alice),
        json={"athlete_id": entered[0].id},
    )
    assert first.status_code == 200
    dup = await client.post(
        f"/api/v1/leagues/{league_id}/draft/pick",
        headers=_headers(bob),
        json={"athlete_id": entered[0].id},
    )
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_athlete_not_in_pool_returns_422(
    client: AsyncClient, users: list[User], pool: tuple[Meet, list[Athlete], Athlete]
):
    alice, bob = users
    meet, _entered, outsider = pool
    league_id = await _create_two_member_league(client, alice, bob, meet)
    await client.post(
        f"/api/v1/leagues/{league_id}/draft/start", headers=_headers(alice)
    )
    resp = await client.post(
        f"/api/v1/leagues/{league_id}/draft/pick",
        headers=_headers(alice),
        json={"athlete_id": outsider.id},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_draft_completes_and_rejects_further_picks(
    client: AsyncClient, users: list[User], pool: tuple[Meet, list[Athlete], Athlete]
):
    alice, bob = users
    meet, entered, _outsider = pool
    league_id = await _create_two_member_league(client, alice, bob, meet)
    await client.post(
        f"/api/v1/leagues/{league_id}/draft/start", headers=_headers(alice)
    )

    sequence = [
        (alice, entered[0].id),
        (bob, entered[1].id),
        (bob, entered[2].id),
        (alice, entered[3].id),
    ]
    last = None
    for user, athlete_id in sequence:
        last = await client.post(
            f"/api/v1/leagues/{league_id}/draft/pick",
            headers=_headers(user),
            json={"athlete_id": athlete_id},
        )
        assert last.status_code == 200

    assert last is not None
    assert last.json()["status"] == "complete"
    assert last.json()["picks_made"] == 4
    assert last.json()["current_drafter_user_id"] is None

    extra = await client.post(
        f"/api/v1/leagues/{league_id}/draft/pick",
        headers=_headers(alice),
        json={"athlete_id": entered[0].id},
    )
    assert extra.status_code == 409

    roster = await client.get(
        f"/api/v1/leagues/{league_id}/roster", headers=_headers(alice)
    )
    assert roster.status_code == 200
    members = {m["username"]: m for m in roster.json()["members"]}
    assert len(members["draft_alice"]["picks"]) == 2
    assert len(members["draft_bob"]["picks"]) == 2


@pytest.mark.asyncio
async def test_start_requires_two_members(
    client: AsyncClient, users: list[User], pool: tuple[Meet, list[Athlete], Athlete]
):
    alice, _bob = users
    meet, _entered, _outsider = pool
    created = await client.post(
        "/api/v1/leagues",
        headers=_headers(alice),
        json={"name": "Solo", "meet_id": meet.id, "roster_size": 2},
    )
    league_id = created.json()["id"]
    resp = await client.post(
        f"/api/v1/leagues/{league_id}/draft/start", headers=_headers(alice)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_start_rejected_if_already_drafting(
    client: AsyncClient, users: list[User], pool: tuple[Meet, list[Athlete], Athlete]
):
    alice, bob = users
    meet, _entered, _outsider = pool
    league_id = await _create_two_member_league(client, alice, bob, meet)
    first = await client.post(
        f"/api/v1/leagues/{league_id}/draft/start", headers=_headers(alice)
    )
    assert first.status_code == 200
    second = await client.post(
        f"/api/v1/leagues/{league_id}/draft/start", headers=_headers(alice)
    )
    assert second.status_code == 409
