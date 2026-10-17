from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.seat import Seat
from app.schemas.seat import SeatResponse


router = APIRouter(
    prefix="/seats",
    tags=["seats"],
)


@router.get("/", response_model=list[SeatResponse])
def get_seats(db: Session = Depends(get_db)):
    return db.query(Seat).all()