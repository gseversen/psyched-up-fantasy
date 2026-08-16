from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.meets import AthleteSummary


class LeagueStatus(StrEnum):
    SETUP = "setup"
    DRAFTING = "drafting"
    COMPLETE = "complete"


class LeagueCreateRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=128)]
    meet_id: int
    roster_size: Annotated[int, Field(ge=1, le=32)] = 8


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class MeetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class LeagueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    meet: MeetSummary
    status: LeagueStatus
    roster_size: int
    member_count: int
    owner: UserSummary


class LeagueMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    role: str


class DraftPickRequest(BaseModel):
    athlete_id: int


class DraftStateResponse(BaseModel):
    league_id: int
    status: LeagueStatus
    current_pick_number: int | None
    current_drafter_user_id: int | None
    picks_made: int
    total_picks: int
    available_athletes: int
    draft_order: list[int]
    roster_size: int


class RosterPickResponse(BaseModel):
    pick_number: int
    picked_at: datetime
    athlete: AthleteSummary


class MemberRosterResponse(BaseModel):
    user_id: int
    username: str
    role: str
    picks: list[RosterPickResponse]


class LeagueRosterResponse(BaseModel):
    league_id: int
    members: list[MemberRosterResponse]
