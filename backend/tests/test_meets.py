import pytest
import pytest_asyncio
from datetime import date, datetime, timezone
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.db.base import Base
from backend.db.models.athlete import Athlete
from backend.db.models.event import Event
from backend.db.models.meet import Meet
from backend.db.models.meet_entry import MeetEntry
from backend.db.models.meet_event import MeetEvent
from backend.db.models.result import Result
from backend.db.session import get_session
from backend.main import app


@pytest_asyncio.fixture
async def session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as sess:
        async with sess.begin():
            yield sess
            await sess.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession):
    async def _override_session():
        yield session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_meet(session: AsyncSession) -> int:
    """Insert minimal data and return the meet ID."""
    event = Event(name="100 Yard Freestyle", stroke="freestyle", distance=100, gender="M")
    session.add(event)
    await session.flush()

    meet = Meet(name="Test Meet", start_date=date(2026, 3, 1), end_date=None)
    session.add(meet)
    await session.flush()

    me = MeetEvent(meet_id=meet.id, event_id=event.id, event_number=1)
    session.add(me)
    await session.flush()

    athlete = Athlete(
        first_name="Test", last_name="Swimmer", gender="M",
        team_display="Test Univ", team_key="TST"
    )
    session.add(athlete)
    await session.flush()

    now = datetime.now(timezone.utc)
    entry = MeetEntry(
        meet_event_id=me.id, athlete_id=athlete.id, seed_time_cs=4500,
        lane=4, entry_status="confirmed",
        source_hash="abc123", ingested_at=now,
    )
    session.add(entry)

    result = Result(
        meet_event_id=me.id, athlete_id=athlete.id,
        final_time_cs=4480, place=1, result_status="official",
        source_type="test", source_uri="test://seed",
        source_hash="def456", ingested_at=now,
    )
    session.add(result)
    await session.flush()

    return meet.id


@pytest.mark.asyncio
async def test_get_meet(client: AsyncClient, seeded_meet: int):
    resp = await client.get(f"/api/v1/meets/{seeded_meet}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Meet"
    assert data["event_count"] == 1


@pytest.mark.asyncio
async def test_get_meet_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/meets/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_meet_results(client: AsyncClient, seeded_meet: int):
    resp = await client.get(f"/api/v1/meets/{seeded_meet}/results")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    result = data[0]
    assert result["event_name"] == "100 Yard Freestyle"
    assert result["event_number"] == 1
    assert result["final_time_cs"] == 4480
    assert result["place"] == 1
    assert result["result_status"] == "official"
    assert result["athlete"]["first_name"] == "Test"
    assert result["athlete"]["last_name"] == "Swimmer"
    assert result["athlete"]["team_display"] == "Test Univ"


@pytest.mark.asyncio
async def test_get_meet_results_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/meets/999999/results")
    assert resp.status_code == 404
