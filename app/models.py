from typing import Literal, Union, Dict
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class DistancePayload(BaseModel):
    sensor_type: Literal['distance']
    sensor_id: int
    device_id: int
    timestamp: str
    data: dict[Literal['distance'], float]
    status: str = "active"


class GripForcePayload(BaseModel):
    sensor_type: Literal['grip_force']
    sensor_id: int
    device_id: int
    timestamp: str
    data: Dict[Literal['force'], float]
    status: str = "active"


class AxisPayload(BaseModel):
    sensor_type: Literal['axis']
    sensor_id: int
    device_id: int
    timestamp: str
    data: Dict[Literal['position', 'speed', 'acceleration', 'load'], float]
    status: str = "active"


class AirPressurePayload(BaseModel):
    sensor_type: Literal['air_pressure']
    sensor_id: int
    device_id: int
    timestamp: str
    data: Dict[Literal['pressure'], float]
    status: str = "active"


SensorPayload = Union[
    AxisPayload,
    DistancePayload,
    GripForcePayload]

number_of_sensors = 6
number_of_devices = 2
sensors = {
    "axis": ["position", "speed", "acceleration", "load"],
    "gripper": ["grip_force", "distance"]
}

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
    "sensor_type": "x_axis",
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
