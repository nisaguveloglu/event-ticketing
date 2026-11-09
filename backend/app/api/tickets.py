from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.ticket import TicketResponse
from app.services.qr_service import generate_ticket_qr_png
from app.services.ticket_service import get_ticket_by_code

router = APIRouter(
    prefix="/tickets",
    tags=["tickets"],
)


@router.get("/{ticket_code}", response_model=TicketResponse)
def read_ticket(ticket_code: str, db: Session = Depends(get_db)):
    return get_ticket_by_code(db=db, ticket_code=ticket_code)


@router.get(
    "/{ticket_code}/qr",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Ticket QR code in PNG format",
        }
    },
)
def read_ticket_qr(ticket_code: str, db: Session = Depends(get_db)):
    ticket = get_ticket_by_code(db=db, ticket_code=ticket_code)
    png_bytes = generate_ticket_qr_png(ticket.ticket_code)
    return Response(content=png_bytes, media_type="image/png")
