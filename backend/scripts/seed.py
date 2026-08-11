"""Idempotent seed script for development data.

Usage:
    python -m backend.scripts.seed
"""

import asyncio
import hashlib
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.db.models.athlete import Athlete
from backend.db.models.event import Event
from backend.db.models.meet import Meet
from backend.db.models.meet_entry import MeetEntry
from backend.db.models.meet_event import MeetEvent
from backend.db.models.result import Result

NCAA_EVENTS: list[dict[str, str | int]] = [
    {"name": "50 Yard Freestyle", "stroke": "freestyle", "distance": 50, "gender": "M"},
    {"name": "100 Yard Freestyle", "stroke": "freestyle", "distance": 100, "gender": "M"},
    {"name": "200 Yard Freestyle", "stroke": "freestyle", "distance": 200, "gender": "M"},
    {"name": "500 Yard Freestyle", "stroke": "freestyle", "distance": 500, "gender": "M"},
    {"name": "1650 Yard Freestyle", "stroke": "freestyle", "distance": 1650, "gender": "M"},
    {"name": "100 Yard Backstroke", "stroke": "backstroke", "distance": 100, "gender": "M"},
    {"name": "200 Yard Backstroke", "stroke": "backstroke", "distance": 200, "gender": "M"},
    {"name": "100 Yard Breaststroke", "stroke": "breaststroke", "distance": 100, "gender": "M"},
    {"name": "200 Yard Breaststroke", "stroke": "breaststroke", "distance": 200, "gender": "M"},
    {"name": "100 Yard Butterfly", "stroke": "butterfly", "distance": 100, "gender": "M"},
    {"name": "200 Yard Butterfly", "stroke": "butterfly", "distance": 200, "gender": "M"},
    {"name": "200 Yard IM", "stroke": "IM", "distance": 200, "gender": "M"},
    {"name": "400 Yard IM", "stroke": "IM", "distance": 400, "gender": "M"},
    {"name": "50 Yard Freestyle", "stroke": "freestyle", "distance": 50, "gender": "F"},
    {"name": "100 Yard Freestyle", "stroke": "freestyle", "distance": 100, "gender": "F"},
    {"name": "200 Yard Freestyle", "stroke": "freestyle", "distance": 200, "gender": "F"},
    {"name": "100 Yard Backstroke", "stroke": "backstroke", "distance": 100, "gender": "F"},
    {"name": "100 Yard Breaststroke", "stroke": "breaststroke", "distance": 100, "gender": "F"},
    {"name": "100 Yard Butterfly", "stroke": "butterfly", "distance": 100, "gender": "F"},
    {"name": "200 Yard IM", "stroke": "IM", "distance": 200, "gender": "F"},
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


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


async def _get_or_create_event(session: AsyncSession, data: dict[str, str | int]) -> Event:
    stmt = select(Event).where(
        Event.name == data["name"],
        Event.gender == data["gender"],
    )
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()
    if event is None:
        event = Event(**data)  # type: ignore[arg-type]
        session.add(event)
        await session.flush()
    return event


async def _get_or_create_meet(session: AsyncSession) -> Meet:
    stmt = select(Meet).where(Meet.name == "2026 NCAA Division I Championships")
    result = await session.execute(stmt)
    meet = result.scalar_one_or_none()
    if meet is None:
        meet = Meet(
            name="2026 NCAA Division I Championships",
            start_date=date(2026, 3, 25),
            end_date=date(2026, 3, 28),
        )
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


async def _seed_entries_and_results(
    session: AsyncSession,
    meet_events: list[MeetEvent],
    athletes: list[Athlete],
) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    entries_created = 0
    results_created = 0

    seed_data: list[tuple[int, int, int, int | None, int | None]] = [
        # (meet_event_idx, athlete_idx, seed_time_cs, final_time_cs, place)
        (0, 0, 1860, 1847, 1),   # Dressel 50 Free
        (0, 4, 1892, 1878, 2),   # Alexy 50 Free
        (1, 0, 4170, 4135, 1),   # Dressel 100 Free
        (1, 4, 4205, 4188, 2),   # Alexy 100 Free
        (2, 3, 9350, 9278, 1),   # Hobson 200 Free
        (5, 1, 4420, 4398, 1),   # Murphy 100 Back
        (7, 2, 5040, None, None),  # Marchand 100 Breast (entry only)
        (11, 2, 9850, 9712, 1),  # Marchand 200 IM
        (13, 7, 2120, 2098, 1),  # G. Walsh 50 Free (F)
        (14, 6, 4620, 4589, 1),  # Douglass 100 Free (F)
        (16, 5, 4980, 4945, 1),  # R. Smith 100 Back (F)
    ]

    for me_idx, ath_idx, seed_cs, final_cs, place in seed_data:
        me = meet_events[me_idx]
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
            events: list[Event] = []
            for event_data in NCAA_EVENTS:
                events.append(await _get_or_create_event(session, event_data))

            meet = await _get_or_create_meet(session)

            meet_events: list[MeetEvent] = []
            for idx, event in enumerate(events, start=1):
                stmt = select(MeetEvent).where(
                    MeetEvent.meet_id == meet.id,
                    MeetEvent.event_id == event.id,
                )
                result = await session.execute(stmt)
                me = result.scalar_one_or_none()
                if me is None:
                    me = MeetEvent(
                        meet_id=meet.id,
                        event_id=event.id,
                        event_number=idx,
                    )
                    session.add(me)
                    await session.flush()
                meet_events.append(me)

            athletes: list[Athlete] = []
            for ath_data in ATHLETES:
                athletes.append(await _get_or_create_athlete(session, ath_data))

            entries_created, results_created = await _seed_entries_and_results(
                session, meet_events, athletes
            )

    await engine.dispose()

    print("=== Seed complete ===")
    print(f"  Events:      {len(events)}")
    print(f"  Meet:        {meet.name}")
    print(f"  Meet events: {len(meet_events)}")
    print(f"  Athletes:    {len(athletes)}")
    print(f"  Entries:     {entries_created} created")
    print(f"  Results:     {results_created} created")


if __name__ == "__main__":
    asyncio.run(main())
