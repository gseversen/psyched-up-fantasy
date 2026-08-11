from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntryStatus(StrEnum):
    ENTERED = "entered"
    SCR = "scr"
    DNS = "dns"


class ResultStatus(StrEnum):
    OFFICIAL = "official"
    PROVISIONAL = "provisional"
    DQ = "dq"
    SCR = "scr"
    DNS = "dns"


class SourceType(StrEnum):
    PDF = "pdf"
    HTML = "html"
    SD3 = "sd3"


class UpsertAction(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


# --- Athlete ---


class AthleteUpsertRequest(BaseModel):
    first_name: Annotated[str, Field(min_length=1, max_length=128)]
    last_name: Annotated[str, Field(min_length=1, max_length=128)]
    gender: Annotated[str, Field(pattern=r"^[MF]$")]
    team_display: Annotated[str, Field(min_length=1, max_length=256)]
    team_key: Annotated[str, Field(min_length=1, max_length=128)]

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class AthleteUpsertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created: bool


# --- Entry ---


class EntryUpsertRequest(BaseModel):
    meet_event_id: int
    athlete_id: int
    seed_time_cs: int | None = None
    lane: int | None = None
    entry_status: EntryStatus
    source_hash: Annotated[str, Field(min_length=1, max_length=64)]
    ingested_at: datetime | None = None

    @field_validator("entry_status", mode="before")
    @classmethod
    def normalize_entry_status(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("seed_time_cs")
    @classmethod
    def validate_seed_time(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("seed_time_cs must be non-negative")
        return v

    def resolved_ingested_at(self) -> datetime:
        return self.ingested_at or datetime.now(timezone.utc)


# --- Result ---


class ResultUpsertRequest(BaseModel):
    meet_event_id: int
    athlete_id: int
    final_time_cs: int | None = None
    place: int | None = None
    result_status: ResultStatus
    source_type: SourceType
    source_uri: Annotated[str, Field(min_length=1, max_length=512)]
    source_hash: Annotated[str, Field(min_length=1, max_length=64)]
    ingested_at: datetime | None = None

    @field_validator("result_status", mode="before")
    @classmethod
    def normalize_result_status(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("final_time_cs")
    @classmethod
    def validate_final_time(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("final_time_cs must be non-negative")
        return v

    def resolved_ingested_at(self) -> datetime:
        return self.ingested_at or datetime.now(timezone.utc)


# --- Upsert Response ---


class UpsertResponse(BaseModel):
    id: int
    action: UpsertAction


# --- Batch ---


class EntryBatchUpsertRequest(BaseModel):
    entries: Annotated[list[EntryUpsertRequest], Field(min_length=1, max_length=500)]


class ResultBatchUpsertRequest(BaseModel):
    results: Annotated[list[ResultUpsertRequest], Field(min_length=1, max_length=500)]


class BatchUpsertResponse(BaseModel):
    created: int
    updated: int
    unchanged: int
    total: int
