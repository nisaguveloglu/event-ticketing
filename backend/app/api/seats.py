from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.seat import Seat


router = APIRouter(
    prefix="/seats",
    tags=["seats"],
)


@router.get("/")
def get_seats(db: Session = Depends(get_db)):
    seats = db.query(Seat).all()
    return seats