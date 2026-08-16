import pytest
import pytest_asyncio
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.meet import Meet
from backend.db.models.user import User


@pytest_asyncio.fixture
async def users(session: AsyncSession) -> list[User]:
    alice = User(username="alice_test", email="alice_test@example.com")
    bob = User(username="bob_test", email="bob_test@example.com")
    carol = User(username="carol_test", email="carol_test@example.com")
    session.add_all([alice, bob, carol])
    await session.flush()
    return [alice, bob, carol]


@pytest_asyncio.fixture
async def meet(session: AsyncSession) -> Meet:
    m = Meet(name="League Test Meet", start_date=date(2026, 3, 1), end_date=None)
    session.add(m)
    await session.flush()
    return m


def _headers(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


@pytest.mark.asyncio
async def test_create_league_and_join(
    client: AsyncClient, users: list[User], meet: Meet
):
    alice, bob, _carol = users
    resp = await client.post(
        "/api/v1/leagues",
        headers=_headers(alice),
        json={"name": "Test League", "meet_id": meet.id, "roster_size": 2},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test League"
    assert data["status"] == "setup"
    assert data["roster_size"] == 2
    assert data["member_count"] == 1
    assert data["owner"]["username"] == "alice_test"
    assert data["meet"]["id"] == meet.id
    league_id = data["id"]

    join = await client.post(
        f"/api/v1/leagues/{league_id}/join",
        headers=_headers(bob),
    )
    assert join.status_code == 200
    assert join.json()["member_count"] == 2

    members = await client.get(
        f"/api/v1/leagues/{league_id}/members",
        headers=_headers(alice),
    )
    assert members.status_code == 200
    names = {m["username"] for m in members.json()}
    assert names == {"alice_test", "bob_test"}
    roles = {m["username"]: m["role"] for m in members.json()}
    assert roles["alice_test"] == "owner"
    assert roles["bob_test"] == "member"


@pytest.mark.asyncio
async def test_join_twice_returns_409(
    client: AsyncClient, users: list[User], meet: Meet
):
    alice, bob, _carol = users
    created = await client.post(
        "/api/v1/leagues",
        headers=_headers(alice),
        json={"name": "Dup Join", "meet_id": meet.id},
    )
    league_id = created.json()["id"]
    await client.post(f"/api/v1/leagues/{league_id}/join", headers=_headers(bob))
    again = await client.post(
        f"/api/v1/leagues/{league_id}/join", headers=_headers(bob)
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_missing_user_header_returns_401(client: AsyncClient, meet: Meet):
    resp = await client.post(
        "/api/v1/leagues",
        json={"name": "No Auth", "meet_id": meet.id},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unknown_user_returns_401(client: AsyncClient, meet: Meet):
    resp = await client.post(
        "/api/v1/leagues",
        headers={"X-User-Id": "999999"},
        json={"name": "Ghost", "meet_id": meet.id},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_non_member_cannot_view_league(
    client: AsyncClient, users: list[User], meet: Meet
):
    alice, _bob, carol = users
    created = await client.post(
        "/api/v1/leagues",
        headers=_headers(alice),
        json={"name": "Private", "meet_id": meet.id},
    )
    league_id = created.json()["id"]
    resp = await client.get(
        f"/api/v1/leagues/{league_id}",
        headers=_headers(carol),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_with_missing_meet_returns_422(
    client: AsyncClient, users: list[User]
):
    alice, _bob, _carol = users
    resp = await client.post(
        "/api/v1/leagues",
        headers=_headers(alice),
        json={"name": "Bad Meet", "meet_id": 999999},
    )
    assert resp.status_code == 422
