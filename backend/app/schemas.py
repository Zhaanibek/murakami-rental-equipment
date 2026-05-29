from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from pydantic.alias_generators import to_camel

class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )

# Nested payload fields in telemetry JSON
class TelemetryExtraPayload(BaseSchema):
    operating_mode: Optional[str] = None
    hydrogen_ppm: Optional[float] = None
    total_hours: Optional[float] = None

# Main telemetry JSON from device
class TelemetryCreate(BaseSchema):
    recorded_at: datetime
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    battery: int = Field(..., ge=0, le=100)
    power_source: str
    is_charging: bool
    speed: float = Field(..., ge=0.0)
    accuracy: float = Field(..., ge=0.0)
    payload: Optional[TelemetryExtraPayload] = None
    acked: List[str] = Field(default_factory=list)
    relay_state: str = Field(..., pattern="^(ON|OFF)$")
    mcc: Optional[int] = None
    mnc: Optional[int] = None
    lac: Optional[int] = None
    cell_id: Optional[int] = None
    rssi: int = Field(..., ge=-150, le=0)

# Response schema for commands in telemetry API
class DeviceCommandResponse(BaseSchema):
    id: str
    type: str
    payload: Optional[Dict[str, Any]] = None

# Telemetry response schema
class TelemetryResponse(BaseSchema):
    interval: int
    commands: List[DeviceCommandResponse]
    desired_power_state: str
    power_command: str

# Command request from UI
class CommandCreate(BaseSchema):
    type: str  # SET_INTERVAL, SET_RELAY
    payload: Dict[str, Any]

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("SET_INTERVAL", "SET_RELAY"):
            raise ValueError("Type must be either SET_INTERVAL or SET_RELAY")
        return v

# Command info schema for UI
class CommandInfo(BaseSchema):
    id: str
    type: str
    payload: Optional[Dict[str, Any]] = None
    status: str
    created_at: datetime
    sent_at: Optional[datetime] = None
    acked_at: Optional[datetime] = None

# Device list schema for UI
class DeviceInfo(BaseSchema):
    id: str
    last_seen: Optional[datetime] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    battery: Optional[int] = None
    power_source: Optional[str] = None
    is_charging: Optional[bool] = None
    speed: Optional[float] = None
    accuracy: Optional[float] = None
    relay_state: Optional[str] = None
    rssi: Optional[int] = None
    operating_mode: Optional[str] = None
    hydrogen_ppm: Optional[float] = None
    total_hours: Optional[float] = None
    mcc: Optional[int] = None
    mnc: Optional[int] = None
    lac: Optional[int] = None
    cell_id: Optional[int] = None
    reporting_interval: int
    desired_power_state: str

# Telemetry History response for UI
class TelemetryHistoryInfo(BaseSchema):
    id: int
    recorded_at: datetime
    received_at: datetime
    lat: float
    lng: float
    battery: Optional[int] = None
    power_source: Optional[str] = None
    is_charging: Optional[bool] = None
    speed: Optional[float] = None
    accuracy: Optional[float] = None
    relay_state: Optional[str] = None
    rssi: Optional[int] = None
    operating_mode: Optional[str] = None
    hydrogen_ppm: Optional[float] = None
    total_hours: Optional[float] = None
