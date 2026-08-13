"""NCAA-style meet results PDF parser.

Supported format:
    Text extracted from NCAA Division I psych sheet / results PDFs.
    Each event block starts with a header line like:
        "Event 1  Men 50 Yard Freestyle"
    Followed by a separator, column headers, then result rows with format:
        PL  Name                  Team              Seed      Finals

    Times are in either SS.CC or M:SS.CC format.
    Special values: DQ, SCR, DNS, NS (no-show), NT (no time).

This parser works on the text content of a PDF (e.g. extracted via pdfplumber).
For the fixture, the .pdf file is already in text format for testing convenience.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from workers.parsers.models import ParsedEvent, ParsedRow

logger = logging.getLogger(__name__)

EVENT_HEADER_RE = re.compile(
    r"^Event\s+(\d+)\s+(Men|Women)\s+(.+)$", re.IGNORECASE
)

RESULT_ROW_RE = re.compile(
    r"^\s*"
    r"(?:(\d+|DQ|dq)\s+)?"   # optional place or DQ marker
    r"(\S+(?:\s+\S+)*?)"     # athlete name (non-greedy multi-word)
    r"\s{2,}"                 # column gap
    r"(\S+(?:\s\S+)*?)"      # team (multi-word allowed)
    r"\s{2,}"                 # column gap
    r"(\S+)"                  # seed time
    r"\s+"                    # gap
    r"(\S+)"                  # finals time / status
    r"\s*$"
)

SKIP_LINE_PATTERNS = (
    re.compile(r"^={3,}"),
    re.compile(r"^-[-\s]+$"),
    re.compile(r"^PL\s+Name", re.IGNORECASE),
)

NON_TIME_VALUES = {"dq", "scr", "dns", "ns", "nt"}


def time_to_centiseconds(time_str: str) -> int | None:
    """Convert a time string (SS.CC or M:SS.CC) to centiseconds.

    Returns None for non-time values (DQ, SCR, DNS, NT, NS).
    """
    normalized = time_str.strip().lower()
    if normalized in NON_TIME_VALUES:
        return None

    try:
        if ":" in time_str:
            minutes_str, seconds_str = time_str.split(":", 1)
            minutes = int(minutes_str)
            seconds = float(seconds_str)
            return round(minutes * 6000 + seconds * 100)
        else:
            seconds = float(time_str)
            return round(seconds * 100)
    except (ValueError, OverflowError):
        return None


def _determine_result_status(place_str: str | None, finals_str: str) -> str:
    """Derive result_status from place and finals columns."""
    finals_lower = finals_str.strip().lower()
    if finals_lower == "dq":
        return "dq"
    if finals_lower == "scr":
        return "scr"
    if finals_lower in ("dns", "ns"):
        return "dns"
    if place_str and place_str.upper() == "DQ":
        return "dq"
    return "official"


def _parse_name(name_str: str) -> tuple[str, str]:
    """Split a name into first and last. Assumes 'First Last' ordering."""
    parts = name_str.strip().split()
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def parse_ncaa_text(text: str) -> list[ParsedRow]:
    """Parse NCAA-style meet results text into structured rows.

    Malformed lines are logged and skipped — never raises on bad data.
    """
    rows: list[ParsedRow] = []
    current_event_number: int | None = None
    current_event_name: str | None = None
    current_gender: str | None = None

    for line_num, line in enumerate(text.splitlines(), start=1):
        line = line.rstrip()
        if not line:
            continue

        if any(p.match(line) for p in SKIP_LINE_PATTERNS):
            continue

        header_match = EVENT_HEADER_RE.match(line)
        if header_match:
            current_event_number = int(header_match.group(1))
            gender_word = header_match.group(2).lower()
            current_gender = "M" if gender_word == "men" else "F"
            current_event_name = header_match.group(3).strip()
            continue

        if current_event_number is None:
            continue

        row_match = RESULT_ROW_RE.match(line)
        if not row_match:
            logger.debug("Skipping unparseable line %d: %r", line_num, line)
            continue

        place_str, name_str, team_str, seed_str, finals_str = row_match.groups()

        try:
            first_name, last_name = _parse_name(name_str)
            seed_cs = time_to_centiseconds(seed_str)
            final_cs = time_to_centiseconds(finals_str)
            result_status = _determine_result_status(place_str, finals_str)
            place: int | None = None
            if place_str and place_str.isdigit():
                place = int(place_str)

            row = ParsedRow(
                event_number=current_event_number,
                event_name=current_event_name,  # type: ignore[arg-type]
                athlete_first_name=first_name,
                athlete_last_name=last_name,
                team=team_str,
                gender=current_gender,  # type: ignore[arg-type]
                seed_time_cs=seed_cs,
                final_time_cs=final_cs,
                place=place,
                result_status=result_status,
            )
            rows.append(row)
        except Exception as exc:
            logger.warning(
                "Malformed row at line %d (skipping): %s — %r", line_num, exc, line
            )
            continue

    logger.info("Parsed %d rows from text", len(rows))
    return rows


def parse_pdf_file(path: Path) -> list[ParsedRow]:
    """Parse a PDF file. Auto-detects binary PDF vs plain text fixture.

    For binary PDFs, uses pdfplumber to extract text.
    For text fixtures (like sample.pdf), reads as plain text.
    """
    raw = path.read_bytes()
    if raw[:5] == b"%PDF-":
        try:
            from workers.parsers.ncaa_psych_sheet import parse_psych_sheet
            rows = parse_psych_sheet(path)
            if rows:
                return rows
        except Exception as exc:
            logger.warning("Psych sheet parser failed, trying results parser: %s", exc)

        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            text = "\n".join(text_parts)
        return parse_ncaa_text(text)

    text = raw.decode("utf-8", errors="replace")
    return parse_ncaa_text(text)
