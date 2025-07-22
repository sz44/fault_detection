from contextlib import asynccontextmanager
import datetime
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from websockets import connect
import redis.asyncio as redis
from pydantic import BaseModel, TypeAdapter
from typing import Union, Literal, Dict
import json
from fastapi import FastAPI, WebSocket
import logging
import asyncio

log = logging.getLogger(__name__)

r = redis.Redis(host="localhost", port=6379)

RETENTION_MS = 600_000


async def initialize_redis():
    keys = [
        "sensor:1:device:1:position",
        "sensor:2:device:1:speed",
        "sensor:3:device:1:acceleration",
        "sensor:4:device:1:load",
        "sensor:7:device:2:grip_force",
        "sensor:8:device:2:distance",
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
    sensor_type: Literal["distance"]
    sensor_id: int
    device_id: int
    timestamp: str # '2025-07-22T02:40:06.870829+00:00'
    data: Dict[Literal["distance"], float]
    status: str = "active"


class GripForcePayload(BaseModel):
    sensor_type: Literal["grip_force"]
    sensor_id: int
    device_id: int
    timestamp: str 
    data: Dict[Literal["force"], float]
    status: str = "active"


class AxisPayload(BaseModel):
    sensor_type: Literal["axis"]
    sensor_id: int
    device_id: int
    timestamp: str 
    data: Dict[Literal["position", "speed", "acceleration", "load"], float]
    status: str = "active"


class AirPressurePayload(BaseModel):
    sensor_type: Literal["air_pressure"]
    sensor_id: int
    device_id: int
    timestamp: str 
    data: Dict[Literal["pressure"], float]
    status: str = "active"


# Union type for all sensor payloads
SensorPayload = Union[
    DistancePayload, GripForcePayload, AxisPayload, AirPressurePayload
]
SensorPayloadAdapter = TypeAdapter(SensorPayload)

def get_timestamp(utc_str) -> int:
    """Get current timestamp in ISO format."""

    dt = datetime.datetime.fromisoformat(utc_str)
    return int(dt.timestamp() * 1000)  # Convert to milliseconds

# ----- Redis Write Function -----
async def add_sensor_data(payload: SensorPayload):
    """Add sensor data to Redis time series"""

    if payload.sensor_type == "distance":
        key = f"sensor:{payload.sensor_id}:device:{payload.device_id}:distance"
        value = payload.data["distance"]
        timestamp = get_timestamp(payload.timestamp)
        await r.execute_command("TS.ADD", key, timestamp, value)

    elif payload.sensor_type == "grip_force":
        key = f"sensor:{payload.sensor_id}:device:{payload.device_id}:grip_force"
        value = payload.data["force"]
        timestamp = get_timestamp(payload.timestamp)
        await r.execute_command("TS.ADD", key, timestamp, value)

    elif payload.sensor_type == "axis":
        assert isinstance(payload, AxisPayload)
        # Add each axis measurement separately
        for metric in ["position", "speed", "acceleration", "load"]:
            key = f"sensor:{payload.sensor_id}:device:{payload.device_id}:{metric}"
            value = payload.data[metric]  # type: ignore
            timestamp = get_timestamp(payload.timestamp)
            await r.execute_command("TS.ADD", key, timestamp, value)

    elif payload.sensor_type == "air_pressure":
        key = f"sensor:{payload.sensor_id}:device:{payload.device_id}:pressure"
        value = payload.data["pressure"]
        timestamp = get_timestamp(payload.timestamp)
        await r.execute_command("TS.ADD", key, timestamp, value)

# ------ Analysis Worker -----
analysis_queue = asyncio.Queue(maxsize=1000)

async def analysis_worker():
    """worker to analyze sensor data. 
    Every 10 seconds, fetch data from Redis and perform analysis.
    if data out or bounds, log it. and record in postgres
    """
    while True:
        try:
            # Fetch last 10 seconds of data for each sensor
            cur_time = await r.time()
            end_time = cur_time[0] * 1000 + cur_time[1] // 1000  # Current time
            start_time = end_time - 600_000  # 60 seconds ago

            keys = [
                "sensor:1:device:1:position",
                "sensor:2:device:1:speed",
                "sensor:3:device:1:acceleration",
                "sensor:4:device:1:load",
                "sensor:5:device:2:grip_force",
                "sensor:6:device:2:distance",
            ]

            for key in keys:
                data = await r.execute_command("TS.RANGE", key, start_time, end_time)
                log.info(f"Data for {key}: {data}")

        except Exception as e:
            log.error(f"Error in analysis worker: {e}")

        await asyncio.sleep(10)  # Adjust the sleep time as needed
    
async def dashboard_update_worker(data):
    """Worker to update dashboard with latest sensor data. sending data to websocket clients."""

    # async with connect("ws://localhost:8000/dashboard") as websocket:
        # await websocket.send(data)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/sensor")
async def get():
    return FileResponse("app/static/sensors.html")

# dashboard get endpoint
@app.get("/dashboard")
async def get_dashboard():
    return FileResponse("app/static/dashboard.html")

@app.get("/data/{sensor_id}/{device_id}/{metric}")
async def get_data(sensor_id: int, device_id: int, metric: str):
    key = f"sensor:{sensor_id}:device:{device_id}:{metric}"
    try:
        # Fetch last 10 seconds of data
        cur_time = await r.time()
        print(cur_time)
        end_time = cur_time[0] * 1000 + cur_time[1] // 1000  # Current time
        print(end_time)
        start_time = end_time - 600_000  # 60 seconds ago
        print(start_time)

        # start_time = "-"
        # end_time = "+"
        data = await r.execute_command("TS.RANGE", key, start_time, end_time)
        return {"start": start_time, "end": end_time, "key": key, "data": data}
    except redis.ResponseError as e:
        log.error(f"Error fetching data for {key}: {e}")
        return {"error": str(e)}

ws_clients = 0
# ----- WebSocket Endpoint -----
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    global ws_clients 
    ws_clients += 1
    print(f"Client connected. Total clients: {ws_clients}")
    try:
        while True:
            try:
                raw = await ws.receive_text()
                data = json.loads(raw)
                payload = SensorPayloadAdapter.validate_python(data)
                await add_sensor_data(payload)
                await dashboard_update_worker(raw)  
                await ws.send_text("ok")
            except Exception as e:
                log.error(f"WebSocket error: {e}")
                await ws.send_text(f"error: {str(e)}")
    except Exception:
        pass
    finally:
        ws_clients -= 1
        print(f"Client disconnected. Total clients: {ws_clients}")


# ----- Example Usage -----
"""
Example JSON payloads that would be sent via WebSocket:

Distance sensor:
{
    "sensor_type": "distance",
    "sensor_id": 1,
    "device_id": 100,
    "timestamp": "2025-07-18T10:30:00Z", or 
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
