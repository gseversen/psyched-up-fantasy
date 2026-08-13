"""PDF meet-results ingestion worker.

Standalone CLI worker that parses an NCAA-style meet results PDF and posts
structured data to the internal ingestion API. Communicates with the backend
exclusively over HTTP — no direct database access.

Usage:
    python -m workers.ingest_pdf \
        --pdf workers/fixtures/sample.pdf \
        --meet-id 1 \
        --api-base http://localhost:8000 \
        --api-key dev-ingest-key

Environment variables (override CLI flags):
    INGESTION_API_KEY   - API key for internal endpoints
    API_BASE_URL        - Base URL for the FastAPI backend

Supported PDF format:
    NCAA Division I psych sheet / results (text-extractable).
    See workers/parsers/ncaa_results.py for format documentation.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import sys
from pathlib import Path

import httpx

from workers.parsers.models import ParsedRow
from workers.parsers.ncaa_results import parse_pdf_file

logger = logging.getLogger("workers.ingest_pdf")

MAX_RETRIES = 4
BACKOFF_BASE = 0.5
BATCH_SIZE = 100


def _compute_source_hash(
    meet_id: int, event_number: int, first_name: str, last_name: str,
    final_time_cs: int | None, place: int | None,
) -> str:
    """Stable hash from row identity fields for idempotent ingestion."""
    payload = f"{meet_id}:{event_number}:{first_name.lower()}:{last_name.lower()}:{final_time_cs}:{place}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    """HTTP request with exponential backoff on 5xx / network errors."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code < 500:
                return resp
            last_exc = httpx.HTTPStatusError(
                f"Server error {resp.status_code}",
                request=resp.request,
                response=resp,
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            last_exc = exc

        if attempt < MAX_RETRIES:
            delay = BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "Retry %d/%d after %.1fs (error: %s)",
                attempt + 1, MAX_RETRIES, delay, last_exc,
            )
            await asyncio.sleep(delay)

    raise RuntimeError(f"All retries exhausted: {last_exc}") from last_exc


async def _fetch_event_mapping(
    client: httpx.AsyncClient, api_base: str, meet_id: int
) -> dict[int, int]:
    """Fetch event_number → meet_event_id mapping in one request."""
    resp = await _request_with_retry(
        client, "GET", f"{api_base}/internal/v1/meets/{meet_id}/events"
    )
    resp.raise_for_status()
    data = resp.json()
    return {ev["event_number"]: ev["meet_event_id"] for ev in data["events"]}


async def _upsert_athlete(
    client: httpx.AsyncClient, api_base: str, row: ParsedRow, team_key: str,
) -> int:
    """Upsert a single athlete and return their ID."""
    payload = {
        "first_name": row.athlete_first_name,
        "last_name": row.athlete_last_name,
        "gender": row.gender,
        "team_display": row.team,
        "team_key": team_key,
    }
    resp = await _request_with_retry(
        client, "POST", f"{api_base}/internal/v1/athletes/upsert", json=payload
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _derive_team_key(team_display: str) -> str:
    """Normalize team name to a short key for matching."""
    return team_display.strip().upper().replace(" ", "")[:12]


async def ingest_pdf(
    pdf_path: Path,
    meet_id: int,
    api_base: str,
    api_key: str,
    *,
    _client: httpx.AsyncClient | None = None,
) -> dict[str, int]:
    """Main ingestion orchestration. Returns counts dict."""
    rows = parse_pdf_file(pdf_path)
    if not rows:
        logger.warning("No rows parsed from %s", pdf_path)
        return {"parsed": 0, "skipped_no_event": 0, "entries": 0, "results": 0}

    logger.info("Parsed %d rows from %s", len(rows), pdf_path)

    headers = {"X-API-Key": api_key}
    source_uri = str(pdf_path.resolve())

    async def _run(client: httpx.AsyncClient) -> dict[str, int]:
        event_map = await _fetch_event_mapping(client, api_base, meet_id)
        logger.info("Loaded %d event mappings for meet_id=%d", len(event_map), meet_id)

        athlete_cache: dict[tuple[str, str, str], int] = {}
        skipped_no_event = 0

        entry_payloads: list[dict] = []
        result_payloads: list[dict] = []

        for row in rows:
            meet_event_id = event_map.get(row.event_number)
            if meet_event_id is None:
                logger.debug(
                    "Skipping row: event_number=%d not in meet_id=%d",
                    row.event_number, meet_id,
                )
                skipped_no_event += 1
                continue

            team_key = _derive_team_key(row.team)
            cache_key = (
                row.athlete_first_name.lower(),
                row.athlete_last_name.lower(),
                team_key,
            )

            if cache_key not in athlete_cache:
                athlete_id = await _upsert_athlete(client, api_base, row, team_key)
                athlete_cache[cache_key] = athlete_id
            else:
                athlete_id = athlete_cache[cache_key]

            source_hash = _compute_source_hash(
                meet_id, row.event_number,
                row.athlete_first_name, row.athlete_last_name,
                row.final_time_cs, row.place,
            )

            if row.seed_time_cs is not None:
                entry_payloads.append({
                    "meet_event_id": meet_event_id,
                    "athlete_id": athlete_id,
                    "seed_time_cs": row.seed_time_cs,
                    "entry_status": "entered",
                    "source_hash": source_hash,
                })

            if row.final_time_cs is not None or row.result_status != "official":
                result_payloads.append({
                    "meet_event_id": meet_event_id,
                    "athlete_id": athlete_id,
                    "final_time_cs": row.final_time_cs,
                    "place": row.place,
                    "result_status": row.result_status,
                    "source_type": "pdf",
                    "source_uri": source_uri,
                    "source_hash": source_hash,
                })

        entry_counts = {"created": 0, "updated": 0, "unchanged": 0}
        for i in range(0, len(entry_payloads), BATCH_SIZE):
            batch = entry_payloads[i : i + BATCH_SIZE]
            resp = await _request_with_retry(
                client, "POST",
                f"{api_base}/internal/v1/entries/batch",
                json={"entries": batch},
            )
            resp.raise_for_status()
            data = resp.json()
            for key in entry_counts:
                entry_counts[key] += data[key]

        result_counts = {"created": 0, "updated": 0, "unchanged": 0}
        for i in range(0, len(result_payloads), BATCH_SIZE):
            batch = result_payloads[i : i + BATCH_SIZE]
            resp = await _request_with_retry(
                client, "POST",
                f"{api_base}/internal/v1/results/batch",
                json={"results": batch},
            )
            resp.raise_for_status()
            data = resp.json()
            for key in result_counts:
                result_counts[key] += data[key]

        return {
            "parsed": len(rows),
            "skipped_no_event": skipped_no_event,
            "athletes_resolved": len(athlete_cache),
            "entries_created": entry_counts["created"],
            "entries_updated": entry_counts["updated"],
            "entries_unchanged": entry_counts["unchanged"],
            "results_created": result_counts["created"],
            "results_updated": result_counts["updated"],
            "results_unchanged": result_counts["unchanged"],
        }

    if _client is not None:
        return await _run(_client)

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        return await _run(client)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest NCAA meet results from a PDF into the fantasy swimming API."
    )
    parser.add_argument(
        "--pdf", type=Path, required=True, help="Path to the PDF file to parse"
    )
    parser.add_argument(
        "--meet-id", type=int, required=True, help="Meet ID to associate results with"
    )
    parser.add_argument(
        "--api-base",
        default=os.environ.get("API_BASE_URL", "http://localhost:8000"),
        help="Base URL of the ingestion API (default: $API_BASE_URL or localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("INGESTION_API_KEY", "dev-ingest-key"),
        help="API key for internal endpoints (default: $INGESTION_API_KEY)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    return parser.parse_args(argv)


async def main(args: argparse.Namespace) -> None:
    if not args.pdf.exists():
        logger.error("PDF file not found: %s", args.pdf)
        sys.exit(1)

    summary = await ingest_pdf(args.pdf, args.meet_id, args.api_base, args.api_key)

    print("\n=== Ingestion Summary ===")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(main(args))
