"""Pydantic models for parsed PDF rows.

These models represent the intermediate state between raw PDF text extraction
and the HTTP payloads sent to the internal ingestion API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ParsedRow(BaseModel):
    """A single athlete result/entry row parsed from an NCAA-style meet PDF."""

    event_number: int = Field(ge=1)
    event_name: str = Field(min_length=1)
    athlete_first_name: str = Field(min_length=1)
    athlete_last_name: str = Field(min_length=1)
    team: str = Field(min_length=1)
    gender: str = Field(pattern=r"^[MF]$")
    seed_time_cs: int | None = None
    final_time_cs: int | None = None
    place: int | None = None
    result_status: str = "official"

    @field_validator("athlete_first_name", "athlete_last_name", "team", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class ParsedEvent(BaseModel):
    """A collection of rows for a single event."""

    event_number: int
    event_name: str
    gender: str
    rows: list[ParsedRow]
