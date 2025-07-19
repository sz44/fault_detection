from sqlmodel import Field, SQLModel

class SensorDataBase(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    sensor_id: int
    device_id: int
    timestamp: str
    status: str

class DistanceData(SensorDataBase, table=True):
    distance: float

class GripForceData(SensorDataBase, table=True):
    force: float

class AxisData(SensorDataBase, table=True):
    position: float
    speed: float
    acceleration: float
    load: float

class AirPressureData(SensorDataBase, table=True):
    pressure: float

devices = {
    "axis": ["position", "speed", "acceleration", "load"],
    "gripper": ["grip_force", "distance"]
}