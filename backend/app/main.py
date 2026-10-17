from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from sqlalchemy import text

from app.api.seats import router as seats_router
from app.core.database import Base, engine
from app.models import Hall, Seat, SeatLock
from app.websocket.manager import manager

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


@app.websocket("/ws/seats")
async def seat_websocket(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)