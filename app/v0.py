import json
import aioredis

from typing import Annotated
from fastapi import Depends, FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from pydantic import TypeAdapter

import models
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

# ----- Database Write Function -----
async def add_sensor_data(payload: SensorPayload, session: Session):
    """Add sensor data to the appropriate database table"""
    
    if payload.sensor_type == 'distance':
        db_record = models.DistancePayload(
            sensor_id=payload.sensor_id,
            device_id=payload.device_id,
            timestamp=payload.timestamp,
            status=payload.status,
            distance=payload.data['distance']
        )
    elif payload.sensor_type == 'grip_force':
        db_record = models.GripForceData(
            sensor_id=payload.sensor_id,
            device_id=payload.device_id,
            timestamp=payload.timestamp,
            status=payload.status,
            force=payload.data['force']
        )
    elif payload.sensor_type == 'axis':
        db_record = AxisData(
            sensor_id=payload.sensor_id,
            device_id=payload.device_id,
            timestamp=payload.timestamp,
            status=payload.status,
            position=payload.data['position'],
            speed=payload.data['speed'],
            acceleration=payload.data['acceleration'],
            load=payload.data['load']
        )
    elif payload.sensor_type == 'air_pressure':
        db_record = AirPressureData(
            sensor_id=payload.sensor_id,
            device_id=payload.device_id,
            timestamp=payload.timestamp,
            status=payload.status,
            pressure=payload.data['pressure']
        )
    
    session.add(db_record)
    session.commit()
    session.refresh(db_record)
    return db_record

SensorsPayloadAdapter = TypeAdapter(SensorPayload)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        raw = await websocket.receive_text()
        # Parse JSON data
        try:
            data = json.loads(raw)
            payload = SensorsPayloadAdapter.validate_python(data)
            await add_sensor_data(payload)
            await websocket.send_text("ok")
        except Exception as e:
            log.error(f'WebSocket error: {e}')
            await websocket.send_text(f'error: {str(e)}')
            continue

        # Save to DB
        with Session(engine) as session:
            session.add(payload)
            session.commit()
            session.refresh(payload)

            await websocket.send_text(f"Saved data with id: {payload.id}")
