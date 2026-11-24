from datetime import datetime

from pydantic import BaseModel


class CheckInRequest(BaseModel):
    event_id: int
    ticket_code: str


class CheckInResponse(BaseModel):
    result: str
    ticket_code: str
    event_id: int
    seat_id: int
    checked_in_at: datetime
