from fastapi import FastAPI
from sqlalchemy import text

from app.api.seats import router as seats_router
from app.core.database import Base, engine
from app.models import Hall, Seat, SeatLock


Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(seats_router)


@app.get("/")
def root():
    return {"message": "Cinema Ticketing Backend"}


@app.get("/db-test")
def db_test():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {"database": "connected"}