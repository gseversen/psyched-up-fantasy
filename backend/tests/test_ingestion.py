import pytest
import pytest_asyncio
from datetime import date, datetime, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.athlete import Athlete
from backend.db.models.event import Event
from backend.db.models.meet import Meet
from backend.db.models.meet_event import MeetEvent

API_KEY = "dev-ingest-key"
HEADERS = {"X-API-Key": API_KEY}


@pytest_asyncio.fixture
async def meet_event_and_athlete(session: AsyncSession) -> tuple[int, int]:
    """Create a meet_event and an athlete, return (meet_event_id, athlete_id)."""
    event = Event(name="200 Yard IM", stroke="IM", distance=200, gender="M")
    session.add(event)
    await session.flush()

    meet = Meet(name="Ingestion Test Meet", start_date=date(2026, 4, 1), end_date=None)
    session.add(meet)
    await session.flush()

    me = MeetEvent(meet_id=meet.id, event_id=event.id, event_number=1)
    session.add(me)
    await session.flush()

    athlete = Athlete(
        first_name="Leon", last_name="Marchand", gender="M",
        team_display="ASU Sun Devils", team_key="ASU",
    )
    session.add(athlete)
    await session.flush()

    return me.id, athlete.id


# --- Auth tests ---


@pytest.mark.asyncio
async def test_missing_api_key_returns_401(client: AsyncClient):
    resp = await client.post("/internal/v1/athletes/upsert", json={
        "first_name": "Test", "last_name": "Swimmer",
        "gender": "M", "team_display": "Test U", "team_key": "TST",
    })
    # FastAPI returns 422 for missing required header
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_wrong_api_key_returns_401(client: AsyncClient):
    resp = await client.post(
        "/internal/v1/athletes/upsert",
        headers={"X-API-Key": "wrong-key"},
        json={
            "first_name": "Test", "last_name": "Swimmer",
            "gender": "M", "team_display": "Test U", "team_key": "TST",
        },
    )
    assert resp.status_code == 401


# --- Athlete upsert tests ---


@pytest.mark.asyncio
async def test_upsert_athlete_create_then_unchanged(client: AsyncClient):
    payload = {
        "first_name": "Uniquename", "last_name": "Testswimmer",
        "gender": "M", "team_display": "Test Gators", "team_key": "TSTUF",
    }

    resp1 = await client.post("/internal/v1/athletes/upsert", headers=HEADERS, json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["created"] is True
    athlete_id = data1["id"]

    resp2 = await client.post("/internal/v1/athletes/upsert", headers=HEADERS, json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["id"] == athlete_id
    assert data2["created"] is False


# --- Entry upsert tests ---


@pytest.mark.asyncio
async def test_upsert_entry_same_hash_unchanged(
    client: AsyncClient, meet_event_and_athlete: tuple[int, int]
):
    me_id, ath_id = meet_event_and_athlete
    payload = {
        "meet_event_id": me_id, "athlete_id": ath_id,
        "seed_time_cs": 9850, "entry_status": "entered",
        "source_hash": "hash_a",
    }

    resp1 = await client.post("/internal/v1/entries/upsert", headers=HEADERS, json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["action"] == "created"

    resp2 = await client.post("/internal/v1/entries/upsert", headers=HEADERS, json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["action"] == "unchanged"
    assert resp2.json()["id"] == resp1.json()["id"]


@pytest.mark.asyncio
async def test_upsert_entry_different_hash_updates(
    client: AsyncClient, meet_event_and_athlete: tuple[int, int]
):
    me_id, ath_id = meet_event_and_athlete
    payload_v1 = {
        "meet_event_id": me_id, "athlete_id": ath_id,
        "seed_time_cs": 9850, "entry_status": "entered",
        "source_hash": "hash_v1",
    }
    payload_v2 = {
        "meet_event_id": me_id, "athlete_id": ath_id,
        "seed_time_cs": 9720, "entry_status": "entered",
        "source_hash": "hash_v2",
    }

    resp1 = await client.post("/internal/v1/entries/upsert", headers=HEADERS, json=payload_v1)
    assert resp1.json()["action"] == "created"

    resp2 = await client.post("/internal/v1/entries/upsert", headers=HEADERS, json=payload_v2)
    assert resp2.status_code == 200
    assert resp2.json()["action"] == "updated"
    assert resp2.json()["id"] == resp1.json()["id"]


# --- Result batch test ---


@pytest.mark.asyncio
async def test_batch_results(
    client: AsyncClient, meet_event_and_athlete: tuple[int, int], session: AsyncSession
):
    me_id, ath_id = meet_event_and_athlete

    ath2 = Athlete(
        first_name="Ryan", last_name="Murphy", gender="M",
        team_display="Cal Bears", team_key="CAL",
    )
    ath3 = Athlete(
        first_name="Luke", last_name="Hobson", gender="M",
        team_display="Texas Longhorns", team_key="TEX",
    )
    session.add_all([ath2, ath3])
    await session.flush()

    payload = {
        "results": [
            {
                "meet_event_id": me_id, "athlete_id": ath_id,
                "final_time_cs": 9712, "place": 1,
                "result_status": "official", "source_type": "pdf",
                "source_uri": "s3://results/im200.pdf", "source_hash": "batch_a",
            },
            {
                "meet_event_id": me_id, "athlete_id": ath2.id,
                "final_time_cs": 9801, "place": 2,
                "result_status": "official", "source_type": "pdf",
                "source_uri": "s3://results/im200.pdf", "source_hash": "batch_b",
            },
            {
                "meet_event_id": me_id, "athlete_id": ath3.id,
                "final_time_cs": 9899, "place": 3,
                "result_status": "official", "source_type": "pdf",
                "source_uri": "s3://results/im200.pdf", "source_hash": "batch_c",
            },
        ]
    }

    resp = await client.post("/internal/v1/results/batch", headers=HEADERS, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 3
    assert data["updated"] == 0
    assert data["unchanged"] == 0
    assert data["total"] == 3


# --- Validation tests ---


@pytest.mark.asyncio
async def test_invalid_result_status_returns_422(
    client: AsyncClient, meet_event_and_athlete: tuple[int, int]
):
    me_id, ath_id = meet_event_and_athlete
    payload = {
        "meet_event_id": me_id, "athlete_id": ath_id,
        "final_time_cs": 5000, "place": 1,
        "result_status": "INVALID_STATUS", "source_type": "pdf",
        "source_uri": "s3://test.pdf", "source_hash": "val_hash",
    }
    resp = await client.post("/internal/v1/results/upsert", headers=HEADERS, json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_negative_time_returns_422(
    client: AsyncClient, meet_event_and_athlete: tuple[int, int]
):
    me_id, ath_id = meet_event_and_athlete
    payload = {
        "meet_event_id": me_id, "athlete_id": ath_id,
        "seed_time_cs": -100, "entry_status": "entered",
        "source_hash": "neg_hash",
    }
    resp = await client.post("/internal/v1/entries/upsert", headers=HEADERS, json=payload)
    assert resp.status_code == 422
