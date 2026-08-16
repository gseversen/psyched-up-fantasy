"""Idempotent seed script for development data.

Usage:
    python -m backend.scripts.seed
"""

import asyncio
import hashlib
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.db.models.athlete import Athlete
from backend.db.models.event import Event
from backend.db.models.meet import Meet
from backend.db.models.meet_entry import MeetEntry
from backend.db.models.meet_event import MeetEvent
from backend.db.models.result import Result
from backend.db.models.user import User

# Men's event_number values match the 2026 NCAA D1 men's psych sheet.
# Relays (2, 3, 8, 9, 14, 15, 20, 21) are omitted until we have relay data.
MEN_EVENTS: list[dict[str, Any]] = [
    {"name": "1650 Yard Freestyle", "stroke": "freestyle", "distance": 1650, "gender": "M", "event_number": 1},
    {"name": "100 Yard Butterfly", "stroke": "butterfly", "distance": 100, "gender": "M", "event_number": 4},
    {"name": "400 Yard IM", "stroke": "IM", "distance": 400, "gender": "M", "event_number": 5},
    {"name": "200 Yard Freestyle", "stroke": "freestyle", "distance": 200, "gender": "M", "event_number": 6},
    {"name": "100 Yard Breaststroke", "stroke": "breaststroke", "distance": 100, "gender": "M", "event_number": 7},
    {"name": "100 Yard Backstroke", "stroke": "backstroke", "distance": 100, "gender": "M", "event_number": 10},
    {"name": "200 Yard Breaststroke", "stroke": "breaststroke", "distance": 200, "gender": "M", "event_number": 11},
    {"name": "500 Yard Freestyle", "stroke": "freestyle", "distance": 500, "gender": "M", "event_number": 12},
    {"name": "50 Yard Freestyle", "stroke": "freestyle", "distance": 50, "gender": "M", "event_number": 13},
    {"name": "200 Yard IM", "stroke": "IM", "distance": 200, "gender": "M", "event_number": 16},
    {"name": "100 Yard Freestyle", "stroke": "freestyle", "distance": 100, "gender": "M", "event_number": 17},
    {"name": "200 Yard Butterfly", "stroke": "butterfly", "distance": 200, "gender": "M", "event_number": 18},
    {"name": "200 Yard Backstroke", "stroke": "backstroke", "distance": 200, "gender": "M", "event_number": 19},
]

WOMEN_EVENTS: list[dict[str, Any]] = [
    {"name": "50 Yard Freestyle", "stroke": "freestyle", "distance": 50, "gender": "F", "event_number": 1},
    {"name": "100 Yard Freestyle", "stroke": "freestyle", "distance": 100, "gender": "F", "event_number": 2},
    {"name": "200 Yard Freestyle", "stroke": "freestyle", "distance": 200, "gender": "F", "event_number": 3},
    {"name": "100 Yard Backstroke", "stroke": "backstroke", "distance": 100, "gender": "F", "event_number": 4},
    {"name": "100 Yard Breaststroke", "stroke": "breaststroke", "distance": 100, "gender": "F", "event_number": 5},
    {"name": "100 Yard Butterfly", "stroke": "butterfly", "distance": 100, "gender": "F", "event_number": 6},
    {"name": "200 Yard IM", "stroke": "IM", "distance": 200, "gender": "F", "event_number": 7},
]

ATHLETES: list[dict[str, str]] = [
    {"first_name": "Caeleb", "last_name": "Dressel", "gender": "M", "team_display": "Florida Gators", "team_key": "UF"},
    {"first_name": "Ryan", "last_name": "Murphy", "gender": "M", "team_display": "California Bears", "team_key": "CAL"},
    {"first_name": "Leon", "last_name": "Marchand", "gender": "M", "team_display": "Arizona State Sun Devils", "team_key": "ASU"},
    {"first_name": "Luke", "last_name": "Hobson", "gender": "M", "team_display": "Texas Longhorns", "team_key": "TEX"},
    {"first_name": "Jack", "last_name": "Alexy", "gender": "M", "team_display": "Virginia Cavaliers", "team_key": "UVA"},
    {"first_name": "Regan", "last_name": "Smith", "gender": "F", "team_display": "Stanford Cardinal", "team_key": "STAN"},
    {"first_name": "Kate", "last_name": "Douglass", "gender": "F", "team_display": "Virginia Cavaliers", "team_key": "UVA"},
    {"first_name": "Gretchen", "last_name": "Walsh", "gender": "F", "team_display": "Virginia Cavaliers", "team_key": "UVA"},
]

USERS: list[dict[str, str]] = [
    {"username": "alice", "email": "alice@example.com"},
    {"username": "bob", "email": "bob@example.com"},
    {"username": "carol", "email": "carol@example.com"},
    {"username": "dave", "email": "dave@example.com"},
    {"username": "eve", "email": "eve@example.com"},
    {"username": "frank", "email": "frank@example.com"},
]

MEN_MEET_NAME = "2026 NCAA Division I Championships"
WOMEN_MEET_NAME = "2026 NCAA Division I Women's Championships"

# (event_name, gender, athlete_idx, seed_time_cs, final_time_cs, place)
SEED_PERFORMANCES: list[tuple[str, str, int, int, int | None, int | None]] = [
    ("50 Yard Freestyle", "M", 0, 1860, 1847, 1),
    ("50 Yard Freestyle", "M", 4, 1892, 1878, 2),
    ("100 Yard Freestyle", "M", 0, 4170, 4135, 1),
    ("100 Yard Freestyle", "M", 4, 4205, 4188, 2),
    ("200 Yard Freestyle", "M", 3, 9350, 9278, 1),
    ("100 Yard Backstroke", "M", 1, 4420, 4398, 1),
    ("100 Yard Breaststroke", "M", 2, 5040, None, None),
    ("200 Yard IM", "M", 2, 9850, 9712, 1),
    ("50 Yard Freestyle", "F", 7, 2120, 2098, 1),
    ("100 Yard Freestyle", "F", 6, 4620, 4589, 1),
    ("100 Yard Backstroke", "F", 5, 4980, 4945, 1),
]


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _event_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k != "event_number"}


async def _get_or_create_event(session: AsyncSession, data: dict[str, Any]) -> Event:
    fields = _event_fields(data)
    stmt = select(Event).where(
        Event.name == fields["name"],
        Event.gender == fields["gender"],
    )
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()
    if event is None:
        event = Event(**fields)
        session.add(event)
        await session.flush()
    return event


async def _get_or_create_meet(
    session: AsyncSession, name: str, start: date, end: date
) -> Meet:
    stmt = select(Meet).where(Meet.name == name)
    result = await session.execute(stmt)
    meet = result.scalar_one_or_none()
    if meet is None:
        meet = Meet(name=name, start_date=start, end_date=end)
        session.add(meet)
        await session.flush()
    return meet


async def _get_or_create_athlete(session: AsyncSession, data: dict[str, str]) -> Athlete:
    stmt = select(Athlete).where(
        Athlete.first_name == data["first_name"],
        Athlete.last_name == data["last_name"],
        Athlete.team_key == data["team_key"],
    )
    result = await session.execute(stmt)
    athlete = result.scalar_one_or_none()
    if athlete is None:
        athlete = Athlete(**data)
        session.add(athlete)
        await session.flush()
    return athlete


async def _get_or_create_user(session: AsyncSession, data: dict[str, str]) -> User:
    stmt = select(User).where(User.username == data["username"])
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        user = User(username=data["username"], email=data["email"])
        session.add(user)
        await session.flush()
    return user


async def _ensure_meet_event(
    session: AsyncSession,
    meet: Meet,
    event: Event,
) -> MeetEvent:
    """Get or create a MeetEvent on the target meet. Does not set final event_number."""
    stmt = select(MeetEvent).where(MeetEvent.event_id == event.id)
    result = await session.execute(stmt)
    existing = list(result.scalars().all())

    me: MeetEvent | None = None
    for row in existing:
        if row.meet_id == meet.id:
            me = row
            break
    if me is None and existing:
        me = existing[0]
        me.meet_id = meet.id
        await session.flush()

    if me is None:
        me = MeetEvent(
            meet_id=meet.id,
            event_id=event.id,
            event_number=9000 + event.id,
        )
        session.add(me)
        await session.flush()
    return me


async def _collect_meet_events(
    session: AsyncSession,
    meet: Meet,
    catalog: list[dict[str, Any]],
    events_by_key: dict[tuple[str, str], Event],
) -> list[tuple[MeetEvent, int]]:
    pending: list[tuple[MeetEvent, int]] = []
    for data in catalog:
        event = events_by_key[(data["name"], data["gender"])]
        me = await _ensure_meet_event(session, meet, event)
        pending.append((me, int(data["event_number"])))
    return pending


async def _apply_event_numbers(
    session: AsyncSession,
    pending: list[tuple[MeetEvent, int]],
) -> list[MeetEvent]:
    """Two-phase numbering avoids unique (meet_id, event_number) collisions."""
    for me, target_number in pending:
        if me.event_number != target_number:
            me.event_number = 1000 + me.id
    await session.flush()

    for me, target_number in pending:
        me.event_number = target_number
    await session.flush()

    return [me for me, _ in pending]


async def _seed_entries_and_results(
    session: AsyncSession,
    meet_event_by_key: dict[tuple[str, str], MeetEvent],
    athletes: list[Athlete],
) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    entries_created = 0
    results_created = 0

    for event_name, gender, ath_idx, seed_cs, final_cs, place in SEED_PERFORMANCES:
        me = meet_event_by_key[(event_name, gender)]
        ath = athletes[ath_idx]

        existing_entry = await session.execute(
            select(MeetEntry).where(
                MeetEntry.meet_event_id == me.id,
                MeetEntry.athlete_id == ath.id,
            )
        )
        if existing_entry.scalar_one_or_none() is None:
            entry = MeetEntry(
                meet_event_id=me.id,
                athlete_id=ath.id,
                seed_time_cs=seed_cs,
                lane=None,
                entry_status="confirmed",
                source_hash=_hash(f"seed-entry-{me.id}-{ath.id}"),
                ingested_at=now,
            )
            session.add(entry)
            entries_created += 1

        if final_cs is not None:
            existing_result = await session.execute(
                select(Result).where(
                    Result.meet_event_id == me.id,
                    Result.athlete_id == ath.id,
                )
            )
            if existing_result.scalar_one_or_none() is None:
                result = Result(
                    meet_event_id=me.id,
                    athlete_id=ath.id,
                    final_time_cs=final_cs,
                    place=place,
                    result_status="official",
                    source_type="seed_script",
                    source_uri="backend/scripts/seed.py",
                    source_hash=_hash(f"seed-result-{me.id}-{ath.id}"),
                    ingested_at=now,
                )
                session.add(result)
                results_created += 1

    await session.flush()
    return entries_created, results_created


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            events_by_key: dict[tuple[str, str], Event] = {}
            for event_data in MEN_EVENTS + WOMEN_EVENTS:
                event = await _get_or_create_event(session, event_data)
                events_by_key[(event.name, event.gender)] = event

            men_meet = await _get_or_create_meet(
                session, MEN_MEET_NAME, date(2026, 3, 25), date(2026, 3, 28)
            )
            women_meet = await _get_or_create_meet(
                session, WOMEN_MEET_NAME, date(2026, 3, 18), date(2026, 3, 21)
            )

            # Move rows onto the correct meets first so numbering cannot collide.
            men_pending = await _collect_meet_events(
                session, men_meet, MEN_EVENTS, events_by_key
            )
            women_pending = await _collect_meet_events(
                session, women_meet, WOMEN_EVENTS, events_by_key
            )
            men_meet_events = await _apply_event_numbers(session, men_pending)
            women_meet_events = await _apply_event_numbers(session, women_pending)

            athletes: list[Athlete] = []
            for ath_data in ATHLETES:
                athletes.append(await _get_or_create_athlete(session, ath_data))

            event_by_id = {e.id: e for e in events_by_key.values()}
            meet_event_by_key: dict[tuple[str, str], MeetEvent] = {}
            for me in men_meet_events + women_meet_events:
                event = event_by_id[me.event_id]
                meet_event_by_key[(event.name, event.gender)] = me

            entries_created, results_created = await _seed_entries_and_results(
                session, meet_event_by_key, athletes
            )

            users: list[User] = []
            for user_data in USERS:
                users.append(await _get_or_create_user(session, user_data))

    await engine.dispose()

    print("=== Seed complete ===")
    print(f"  Events:           {len(events_by_key)}")
    print(f"  Men's meet:       id={men_meet.id} {men_meet.name}")
    print(f"  Women's meet:     id={women_meet.id} {women_meet.name}")
    print(f"  Men's events:     {len(men_meet_events)}")
    print(f"  Women's events:   {len(women_meet_events)}")
    print(f"  Athletes:         {len(athletes)}")
    print(f"  Entries:          {entries_created} created")
    print(f"  Results:          {results_created} created")
    print("  Users:")
    for user in users:
        print(f"    {user.id}: {user.username} <{user.email}>")


if __name__ == "__main__":
    asyncio.run(main())
