from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.seat import Seat, SeatStatus
from app.models.seat_lock import SeatLock
from app.services.ticket_service import (
    _is_duplicate_event_seat_error,
    create_ticket_for_purchase,
)


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


def purchase_seat(db: Session, seat_id: int, session_id: str):
    try:
        seat = (
            db.query(Seat)
            .filter(Seat.id == seat_id)
            .with_for_update()
            .first()
        )

        if seat is None:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Seat not found",
            )

        if seat.status == SeatStatus.SOLD:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Seat is already sold",
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
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Seat is not locked by this session",
            )

        seat.status = SeatStatus.SOLD
        db.delete(seat_lock)

        ticket = create_ticket_for_purchase(
            db=db,
            seat=seat,
            session_id=session_id,
        )
        ticket_code = ticket.ticket_code

        db.commit()

        return {
            "message": "Seat purchased successfully",
            "seat_id": seat_id,
            "status": SeatStatus.SOLD,
            "ticket_code": ticket_code,
        }
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        if _is_duplicate_event_seat_error(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ticket already exists for this event and seat",
            ) from exc
        raise
    except SQLAlchemyError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise