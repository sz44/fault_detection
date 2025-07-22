from contextlib import asynccontextmanager
from websockets import connect
import asyncpg
from pydantic import BaseModel, TypeAdapter
from typing import Union, Literal, Dict
import json
from fastapi import FastAPI, WebSocket
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

DATABASE_URL = "postgresql://postgres:hegelewe34@localhost:5432/tool_sensors"

async def get_db():
    """Simple database connection"""
    return await asyncpg.connect(DATABASE_URL)


async def initialize_database():
    """Create table and hypertable"""
    conn = await get_db()
    
    # Create TimescaleDB extension
    await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    
    # Create sensor data table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            time TIMESTAMPTZ NOT NULL,
            sensor_id INTEGER NOT NULL,
            device_id INTEGER NOT NULL,
            metric TEXT NOT NULL,
            value DOUBLE PRECISION NOT NULL
        );
    """)
    
    # Make it a TimescaleDB hypertable
    try:
        await conn.execute("SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);")
    except:
        pass  # Already exists
    
    await conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_database()
    yield


app = FastAPI(lifespan=lifespan)

# ----- Payload Models -----

class DistancePayload(BaseModel):
    sensor_type: Literal["distance"]
    sensor_id: int
    device_id: int
    timestamp: int
    data: Dict[Literal["distance"], float]
    status: str = "active"


class GripForcePayload(BaseModel):
    sensor_type: Literal["grip_force"]
    sensor_id: int
    device_id: int
    timestamp: int
    data: Dict[Literal["force"], float]
    status: str = "active"


class AxisPayload(BaseModel):
    sensor_type: Literal["axis"]
    sensor_id: int
    device_id: int
    timestamp: int
    data: Dict[Literal["position", "speed", "acceleration", "load"], float]
    status: str = "active"


class AirPressurePayload(BaseModel):
    sensor_type: Literal["air_pressure"]
    sensor_id: int
    device_id: int
    timestamp: int
    data: Dict[Literal["pressure"], float]
    status: str = "active"


SensorPayload = Union[DistancePayload, GripForcePayload, AxisPayload, AirPressurePayload]
SensorPayloadAdapter = TypeAdapter(SensorPayload)


# ----- Database Write Function -----
async def add_sensor_data(payload: SensorPayload):
    """Add sensor data to database"""
    conn = await get_db()
    timestamp_dt = datetime.fromtimestamp(payload.timestamp / 1000)
    
    if payload.sensor_type == "distance":
        await conn.execute(
            "INSERT INTO sensor_data (time, sensor_id, device_id, metric, value) VALUES ($1, $2, $3, $4, $5)",
            timestamp_dt, payload.sensor_id, payload.device_id, "distance", payload.data["distance"]
        )
    
    elif payload.sensor_type == "grip_force":
        await conn.execute(
            "INSERT INTO sensor_data (time, sensor_id, device_id, metric, value) VALUES ($1, $2, $3, $4, $5)",
            timestamp_dt, payload.sensor_id, payload.device_id, "grip_force", payload.data["force"]
        )
    
    elif payload.sensor_type == "axis":
        for metric, value in payload.data.items():
            await conn.execute(
                "INSERT INTO sensor_data (time, sensor_id, device_id, metric, value) VALUES ($1, $2, $3, $4, $5)",
                timestamp_dt, payload.sensor_id, payload.device_id, metric, value
            )
    
    elif payload.sensor_type == "air_pressure":
        await conn.execute(
            "INSERT INTO sensor_data (time, sensor_id, device_id, metric, value) VALUES ($1, $2, $3, $4, $5)",
            timestamp_dt, payload.sensor_id, payload.device_id, "pressure", payload.data["pressure"]
        )
    
    await conn.close()


# ----- Fetch Data Endpoint -----
@app.get("/data/{sensor_id}/{device_id}/{metric}")
async def get_data(sensor_id: int, device_id: int, metric: str):
    """Get last 60 seconds of data"""
    conn = await get_db()
    
    end_time = datetime.now()
    start_time = end_time - timedelta(seconds=60)
    
    rows = await conn.fetch(
        "SELECT time, value FROM sensor_data WHERE sensor_id = $1 AND device_id = $2 AND metric = $3 AND time BETWEEN $4 AND $5 ORDER BY time",
        sensor_id, device_id, metric, start_time, end_time
    )
    
    # Format like Redis TS.RANGE
    data = [[int(row['time'].timestamp() * 1000), row['value']] for row in rows]
    
    await conn.close()
    
    return {
        "start": int(start_time.timestamp() * 1000),
        "end": int(end_time.timestamp() * 1000),
        "key": f"sensor:{sensor_id}:device:{device_id}:{metric}",
        "data": data
    }


# ----- WebSocket Endpoint -----
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    async with connect("ws://localhost:8000/ws") as websocket:
        while True:
            try:
                raw = await ws.receive_text()
                data = json.loads(raw)
                payload = SensorPayloadAdapter.validate_python(data)
                await add_sensor_data(payload)
                await ws.send_text("ok")
                await websocket.send(raw)
            except Exception as e:
                log.error(f"WebSocket error: {e}")
                await ws.send_text(f"error: {str(e)}")