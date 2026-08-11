from datetime import date

from pydantic import BaseModel, ConfigDict


class MeetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_date: date
    end_date: date | None
    event_count: int


class AthleteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    team_display: str


class ResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    result_id: int
    event_name: str
    event_number: int
    athlete: AthleteSummary
    final_time_cs: int | None
    place: int | None
    result_status: str
