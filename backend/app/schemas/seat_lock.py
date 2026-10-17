from pydantic import BaseModel


class SeatLockRequest(BaseModel):
    session_id: str
    