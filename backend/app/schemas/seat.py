from pydantic import BaseModel

from app.models.seat import SeatStatus


class SeatResponse(BaseModel):
    id: int
    hall_id: int
    row: str
    number: int
    status: SeatStatus

    class Config:
        from_attributes = True