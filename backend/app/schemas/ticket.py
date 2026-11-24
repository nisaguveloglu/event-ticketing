from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.seat import SeatStatus


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int | None = None
    ticket_code: str
    event_id: int
    event_name: str
    event_starts_at: datetime
    hall_id: int
    hall_name: str
    seat_id: int
    seat_row: str
    seat_number: int
    seat_label: str = ""
    category_name: str | None = None
    unit_price_kurus: int = 0
    status: str = "VALID"
    used_at: datetime | None = None
    seat_status: SeatStatus
    created_at: datetime
