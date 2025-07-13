
from sqlmodel import Field, SQLModel


class ComponentBase(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    component_id: str
    component_name: str
    timestamp: str
    status: str


class MotorData(ComponentBase, table=True):
    rpm: float
    torque: float
    temperature: float
    vibration: float
    power: float


class AxisData(ComponentBase, table=True):
    position: float
    speed: float
    acceleration: float
    load: float