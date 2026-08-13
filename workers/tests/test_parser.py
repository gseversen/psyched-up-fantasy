"""Unit tests for the NCAA PDF parser."""

from pathlib import Path

import pytest

from workers.parsers.models import ParsedRow
from workers.parsers.ncaa_results import (
    parse_ncaa_text,
    parse_pdf_file,
    time_to_centiseconds,
)

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


class TestTimeConversion:
    def test_seconds_only(self):
        assert time_to_centiseconds("18.47") == 1847

    def test_minutes_and_seconds(self):
        assert time_to_centiseconds("1:33.50") == 9350

    def test_minutes_exact(self):
        assert time_to_centiseconds("1:37.12") == 9712

    def test_dq_returns_none(self):
        assert time_to_centiseconds("DQ") is None

    def test_scr_returns_none(self):
        assert time_to_centiseconds("SCR") is None

    def test_dns_returns_none(self):
        assert time_to_centiseconds("DNS") is None

    def test_nt_returns_none(self):
        assert time_to_centiseconds("NT") is None

    def test_invalid_returns_none(self):
        assert time_to_centiseconds("abc") is None

    def test_zero_time(self):
        assert time_to_centiseconds("0.00") == 0


class TestParseNcaaText:
    @pytest.fixture
    def sample_text(self) -> str:
        return FIXTURE_PATH.read_text()

    def test_parses_correct_row_count(self, sample_text: str):
        rows = parse_ncaa_text(sample_text)
        assert len(rows) == 22

    def test_first_event_dressel(self, sample_text: str):
        rows = parse_ncaa_text(sample_text)
        dressel = rows[0]
        assert dressel.event_number == 1
        assert dressel.athlete_first_name == "Caeleb"
        assert dressel.athlete_last_name == "Dressel"
        assert dressel.team == "Florida"
        assert dressel.gender == "M"
        assert dressel.seed_time_cs == 1860
        assert dressel.final_time_cs == 1847
        assert dressel.place == 1
        assert dressel.result_status == "official"

    def test_minutes_time_parsed_correctly(self, sample_text: str):
        rows = parse_ncaa_text(sample_text)
        hobson = next(r for r in rows if r.athlete_last_name == "Hobson")
        assert hobson.seed_time_cs == 9350
        assert hobson.final_time_cs == 9278
        assert hobson.event_number == 3

    def test_dq_row(self, sample_text: str):
        rows = parse_ncaa_text(sample_text)
        dq_row = next(r for r in rows if r.athlete_last_name == "Smith" and r.athlete_first_name == "John")
        assert dq_row.result_status == "dq"
        assert dq_row.final_time_cs is None
        assert dq_row.place is None

    def test_scr_row(self, sample_text: str):
        rows = parse_ncaa_text(sample_text)
        scr_row = next(r for r in rows if r.athlete_last_name == "Weitzeil")
        assert scr_row.result_status == "scr"
        assert scr_row.final_time_cs is None
        assert scr_row.place is None

    def test_women_events_detected(self, sample_text: str):
        rows = parse_ncaa_text(sample_text)
        women_rows = [r for r in rows if r.gender == "F"]
        assert len(women_rows) >= 5
        assert all(r.gender == "F" for r in women_rows)

    def test_event_names_populated(self, sample_text: str):
        rows = parse_ncaa_text(sample_text)
        assert rows[0].event_name == "50 Yard Freestyle"

    def test_empty_input_returns_empty(self):
        assert parse_ncaa_text("") == []

    def test_garbage_input_returns_empty(self):
        assert parse_ncaa_text("this is not a meet PDF\nrandom text\n") == []

    def test_partial_event_no_crash(self):
        text = "Event 99  Men 100 Yard Butterfly\n===\nPL Name Team Seed Finals\n"
        rows = parse_ncaa_text(text)
        assert rows == []


class TestParsePdfFile:
    def test_fixture_file_parses(self):
        rows = parse_pdf_file(FIXTURE_PATH)
        assert len(rows) > 0
        assert all(isinstance(r, ParsedRow) for r in rows)
