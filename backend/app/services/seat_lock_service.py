from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.seat import Seat, SeatStatus
from app.models.seat_lock import SeatLock


def lock_seat(db: Session, seat_id: int, session_id: str):
    seat = db.query(Seat).filter(Seat.id == seat_id).first()

    if seat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seat not found",
        )

    if seat.status != SeatStatus.AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seat is not available",
        )

    seat_lock = SeatLock(
        seat_id=seat_id,
        session_id=session_id,
    )

    seat.status = SeatStatus.LOCKED

    db.add(seat_lock)
    db.commit()

    return {
        "message": "Seat locked successfully",
        "seat_id": seat_id,
        "status": SeatStatus.LOCKED,
    }


def release_seat(db: Session, seat_id: int, session_id: str):
    seat = db.query(Seat).filter(Seat.id == seat_id).first()

    if seat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seat not found",
        )

    seat_lock = (
        db.query(SeatLock)
        .filter(
            SeatLock.seat_id == seat_id,
            SeatLock.session_id == session_id,
        )
        .first()
    )

    if seat_lock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seat lock not found for this session",
        )

    db.delete(seat_lock)
    seat.status = SeatStatus.AVAILABLE

    db.commit()

    return {
        "message": "Seat lock released successfully",
        "seat_id": seat_id,
        "status": SeatStatus.AVAILABLE,
    }