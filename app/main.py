import json
import aioredis

from typing import Annotated
from fastapi import Depends, FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from models import AxisData
from sqlmodel import Session, SQLModel, create_engine
from config import get_settings
from redis_config import initialize_redis
import logging

log = logging.getLogger(__name__)

database = get_settings().POSTGRES_URL

redis = aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)

engine = create_engine(database)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    await initialize_redis(redis, log)
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def get():
    return FileResponse("app/static/index.html")


@app.get("/component/test-add")
async def test_add_axis_data(session: SessionDep):
    test_data = AxisData(
        sensor_id=1,
        device_id=1,
        timestamp="2024-06-01T12:00:00Z",
        status="idle",
        position=100.0,
        speed=10.0,
        acceleration=1.5,
        load=50.0,
    )
    session.add(test_data)
    session.commit()
    session.refresh(test_data)
    return {"message": "AxisData added", "id": test_data.id}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        # Parse JSON data
        try:
            payload = json.loads(data)
            axis_data = AxisData(**payload)
        except Exception as e:
            await websocket.send_text(f"Invalid data: {e}")
            continue

        # Save to DB
        with Session(engine) as session:
            session.add(axis_data)
            session.commit()
            session.refresh(axis_data)

        await websocket.send_text(f"Saved data with id: {axis_data.id}")
