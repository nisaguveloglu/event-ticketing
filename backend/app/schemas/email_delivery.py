from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmailDeliveryRequest(BaseModel):
    email: str


class EmailDeliveryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    delivery_id: int
    status: str
    attempts: int
    sent_at: datetime | None = None
    last_error: str | None = None


class EmailDeliveryListResponse(BaseModel):
    items: list[EmailDeliveryItemResponse]
