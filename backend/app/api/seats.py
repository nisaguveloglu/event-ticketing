from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.seat import Seat
from app.schemas.seat import SeatResponse
from app.schemas.seat_lock import SeatLockRequest
from app.services.seat_lock_service import (
    lock_seat,
    release_seat,
    purchase_seat,
)

router = APIRouter(
    prefix="/seats",
    tags=["seats"],
)


@router.get("/", response_model=list[SeatResponse])
def get_seats(db: Session = Depends(get_db)):
    return db.query(Seat).all()

@router.post("/{seat_id}/lock")
def lock_seat_endpoint(
    seat_id: int,
    request: SeatLockRequest,
    db: Session = Depends(get_db),
):
    return lock_seat(
        db=db,
        seat_id=seat_id,
        session_id=request.session_id,
    )

@router.delete("/{seat_id}/lock")
def release_seat_endpoint(
    seat_id: int,
    request: SeatLockRequest,
    db: Session = Depends(get_db),
):
    return release_seat(
        db=db,
        seat_id=seat_id,
        session_id=request.session_id,
    )

@router.post("/{seat_id}/purchase")
def purchase_seat_endpoint(
    seat_id: int,
    request: SeatLockRequest,
    db: Session = Depends(get_db),
):
    return purchase_seat(
        db=db,
        seat_id=seat_id,
        session_id=request.session_id,
    )