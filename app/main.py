from contextlib import asynccontextmanager
import redis.asyncio as redis
from pydantic import BaseModel, TypeAdapter
from typing import Union, Literal, Dict
import json
from fastapi import FastAPI, WebSocket 
import logging

log = logging.getLogger(__name__)

r = redis.Redis(host='localhost', port=6379)

RETENTION_MS = 600_000


async def initialize_redis():
    keys = [
        "sensor:1:device:1:position",
        "sensor:2:device:1:speed",
        "sensor:3:device:1:acceleration",
        "sensor:4:device:1:load",
        "sensor:7:device:2:grip_force",
        "sensor:8:device:2:distance"
    ]
    for key in keys:
        try:
            await r.execute_command(
                "TS.CREATE", key, "RETENTION", RETENTION_MS, "DUPLICATE_POLICY", "first"
            )
        except redis.ResponseError as e:
            log.info(f"Timeseries already exists or error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_redis()
    yield


app = FastAPI(lifespan=lifespan)

# ----- Payload Models -----


class DistancePayload(BaseModel):
    sensor_type: Literal['distance']
    sensor_id: int
    device_id: int
    timestamp: int
    data: Dict[Literal['distance'], float]
    status: str = "active"


class GripForcePayload(BaseModel):
    sensor_type: Literal['grip_force']
    sensor_id: int
    device_id: int
    timestamp: int
    data: Dict[Literal['force'], float]
    status: str = "active"


class AxisPayload(BaseModel):
    sensor_type: Literal['axis']
    sensor_id: int
    device_id: int
    timestamp: int
    data: Dict[Literal['position', 'speed', 'acceleration', 'load'], float]
    status: str = "active"


class AirPressurePayload(BaseModel):
    sensor_type: Literal['air_pressure']
    sensor_id: int
    device_id: int
    timestamp: int
    data: Dict[Literal['pressure'], float]
    status: str = "active"


# Union type for all sensor payloads
SensorPayload = Union[DistancePayload, GripForcePayload, AxisPayload, AirPressurePayload]
SensorPayloadAdapter = TypeAdapter(SensorPayload)

# ----- Redis Write Function -----
async def add_sensor_data(payload: SensorPayload):
    """Add sensor data to Redis time series"""

    if payload.sensor_type == 'distance':
        key = f"sensor:{payload.sensor_id}:device:{payload.device_id}:distance"
        value = payload.data['distance']
        await r.execute_command('TS.ADD', key, payload.timestamp, value)

    elif payload.sensor_type == 'grip_force':
        key = f"sensor:{payload.sensor_id}:device:{payload.device_id}:grip_force"
        value = payload.data['force']
        await r.execute_command('TS.ADD', key, payload.timestamp, value)

    elif payload.sensor_type == 'axis':
        assert isinstance(payload, AxisPayload)  
        # Add each axis measurement separately
        for metric in ['position', 'speed', 'acceleration', 'load']:
            key = f"sensor:{payload.sensor_id}:device:{payload.device_id}:{metric}"
            value = payload.data[metric]
            await r.execute_command('TS.ADD', key, payload.timestamp, value)

    elif payload.sensor_type == 'air_pressure':
        key = f"sensor:{payload.sensor_id}:device:{payload.device_id}:pressure"
        value = payload.data['pressure']
        await r.execute_command('TS.ADD', key, payload.timestamp, value)

# ----- WebSocket Endpoint -----


@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    while True:
        try:
            raw = await ws.receive_text()
            data = json.loads(raw)
            payload = SensorPayloadAdapter.validate_python(data)
            await add_sensor_data(payload)
            await ws.send_text('ok')
        except Exception as e:
            log.error(f'WebSocket error: {e}')
            await ws.send_text(f'error: {str(e)}')

# ----- Example Usage -----
"""
Example JSON payloads that would be sent via WebSocket:

Distance sensor:
{
    "sensor_type": "distance",
    "sensor_id": 1,
    "device_id": 100,
    "timestamp": "2025-07-18T10:30:00Z",
    "data": {"distance": 15.5},
    "status": "active"
}

Grip force sensor:
{
    "sensor_type": "grip_force",
    "sensor_id": 2,
    "device_id": 100,
    "timestamp": "2025-07-18T10:30:00Z",
    "data": {"force": 25.3},
    "status": "active"
}

Axis sensor:
{
    "sensor_type": "axis",
    "sensor_id": 3,
    "device_id": 100,
    "timestamp": "2025-07-18T10:30:00Z",
    "data": {
        "position": 100.0,
        "speed": 5.2,
        "acceleration": 0.8,
        "load": 75.5
    },
    "status": "active"
}

Air pressure sensor:
{
    "sensor_type": "air_pressure",
    "sensor_id": 4,
    "device_id": 100,
    "timestamp": "2025-07-18T10:30:00Z",
    "data": {"pressure": 1013.25},
    "status": "active"
}
"""
