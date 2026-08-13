"""Integration tests for the PDF ingestion worker.

Tests the full worker flow with mocked HTTP responses to verify:
- Correct API call sequence (event lookup → athlete upserts → batch calls)
- Payload structure matches ingestion API schemas
- Idempotent re-run produces unchanged counts
"""

import json
from pathlib import Path

import httpx
import pytest

from workers.ingest_pdf import ingest_pdf

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample.pdf"

MEET_EVENTS_RESPONSE = {
    "meet_id": 1,
    "events": [
        {"event_number": i, "meet_event_id": 100 + i}
        for i in range(1, 21)
    ],
}


def _make_batch_response(total: int, created: int = 0, updated: int = 0, unchanged: int = 0):
    return {"total": total, "created": created, "updated": updated, "unchanged": unchanged}


class FakeTransport(httpx.AsyncBaseTransport):
    """Mock transport that records requests and returns canned responses."""

    def __init__(self, *, first_run: bool = True):
        self.requests: list[tuple[str, str, dict | None]] = []
        self._athlete_counter = 0
        self._first_run = first_run

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        method = request.method

        body = None
        if request.content:
            body = json.loads(request.content)

        self.requests.append((method, url, body))

        if "/meets/" in url and "/events" in url and method == "GET":
            return httpx.Response(200, json=MEET_EVENTS_RESPONSE)

        if "/athletes/upsert" in url and method == "POST":
            self._athlete_counter += 1
            return httpx.Response(
                200,
                json={"id": self._athlete_counter, "created": self._first_run},
            )

        if "/entries/batch" in url and method == "POST":
            total = len(body["entries"])
            if self._first_run:
                return httpx.Response(200, json=_make_batch_response(total, created=total))
            return httpx.Response(200, json=_make_batch_response(total, unchanged=total))

        if "/results/batch" in url and method == "POST":
            total = len(body["results"])
            if self._first_run:
                return httpx.Response(200, json=_make_batch_response(total, created=total))
            return httpx.Response(200, json=_make_batch_response(total, unchanged=total))

        return httpx.Response(404, json={"detail": "Not found"})


@pytest.fixture
def first_run_transport():
    return FakeTransport(first_run=True)


@pytest.fixture
def second_run_transport():
    return FakeTransport(first_run=False)


@pytest.mark.asyncio
async def test_first_run_creates_entries_and_results(first_run_transport):
    client = httpx.AsyncClient(transport=first_run_transport)
    summary = await ingest_pdf(
        pdf_path=FIXTURE_PATH,
        meet_id=1,
        api_base="http://test",
        api_key="test-key",
        _client=client,
    )

    assert summary["parsed"] == 22
    assert summary["entries_created"] == 22
    assert summary["results_created"] == 22
    assert summary["entries_unchanged"] == 0
    assert summary["results_unchanged"] == 0
    assert summary["skipped_no_event"] == 0
    assert summary["athletes_resolved"] > 0


@pytest.mark.asyncio
async def test_second_run_all_unchanged(second_run_transport):
    client = httpx.AsyncClient(transport=second_run_transport)
    summary = await ingest_pdf(
        pdf_path=FIXTURE_PATH,
        meet_id=1,
        api_base="http://test",
        api_key="test-key",
        _client=client,
    )

    assert summary["parsed"] == 22
    assert summary["entries_created"] == 0
    assert summary["results_created"] == 0
    assert summary["entries_unchanged"] == 22
    assert summary["results_unchanged"] == 22


@pytest.mark.asyncio
async def test_event_lookup_called_once(first_run_transport):
    client = httpx.AsyncClient(transport=first_run_transport)
    await ingest_pdf(
        pdf_path=FIXTURE_PATH,
        meet_id=1,
        api_base="http://test",
        api_key="test-key",
        _client=client,
    )

    event_lookups = [r for r in first_run_transport.requests if "/events" in r[1] and r[0] == "GET"]
    assert len(event_lookups) == 1


@pytest.mark.asyncio
async def test_batch_payloads_have_correct_structure(first_run_transport):
    client = httpx.AsyncClient(transport=first_run_transport)
    await ingest_pdf(
        pdf_path=FIXTURE_PATH,
        meet_id=1,
        api_base="http://test",
        api_key="test-key",
        _client=client,
    )

    entry_batches = [r for r in first_run_transport.requests if "/entries/batch" in r[1]]
    assert len(entry_batches) >= 1
    entry_payload = entry_batches[0][2]
    assert "entries" in entry_payload
    first_entry = entry_payload["entries"][0]
    assert "meet_event_id" in first_entry
    assert "athlete_id" in first_entry
    assert "seed_time_cs" in first_entry
    assert "entry_status" in first_entry
    assert "source_hash" in first_entry

    result_batches = [r for r in first_run_transport.requests if "/results/batch" in r[1]]
    assert len(result_batches) >= 1
    result_payload = result_batches[0][2]
    assert "results" in result_payload
    first_result = result_payload["results"][0]
    assert "meet_event_id" in first_result
    assert "athlete_id" in first_result
    assert "final_time_cs" in first_result
    assert "result_status" in first_result
    assert "source_type" in first_result
    assert "source_uri" in first_result
    assert "source_hash" in first_result


@pytest.mark.asyncio
async def test_source_hash_is_stable():
    """Same input produces same source_hash across runs."""
    from workers.ingest_pdf import _compute_source_hash

    h1 = _compute_source_hash(1, 1, "Caeleb", "Dressel", 1847, 1)
    h2 = _compute_source_hash(1, 1, "Caeleb", "Dressel", 1847, 1)
    h3 = _compute_source_hash(1, 1, "Caeleb", "Dressel", 1850, 1)

    assert h1 == h2
    assert h1 != h3
