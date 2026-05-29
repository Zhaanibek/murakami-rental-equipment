from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, index=True)
    last_seen = Column(DateTime, nullable=True)
    
    # Current Telemetry state
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    battery = Column(Integer, nullable=True)
    power_source = Column(String, nullable=True)
    is_charging = Column(Boolean, nullable=True)
    speed = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    relay_state = Column(String, default="OFF")
    rssi = Column(Integer, nullable=True)
    
    # Payload details
    operating_mode = Column(String, nullable=True)
    hydrogen_ppm = Column(Float, nullable=True)
    total_hours = Column(Float, nullable=True)
    
    # Cellular connection details
    mcc = Column(Integer, nullable=True)
    mnc = Column(Integer, nullable=True)
    lac = Column(Integer, nullable=True)
    cell_id = Column(Integer, nullable=True)
    
    # Configurations
    reporting_interval = Column(Integer, default=30)
    desired_power_state = Column(String, default="ON")  # User desired power state (ON / OFF)

    # Relationships
    telemetry_history = relationship("TelemetryHistory", back_populates="device", cascade="all, delete-orphan")
    commands = relationship("DeviceCommand", back_populates="device", cascade="all, delete-orphan")


class TelemetryHistory(Base):
    __tablename__ = "telemetry_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    
    recorded_at = Column(DateTime, nullable=False)
    received_at = Column(DateTime, server_default=func.now())
    
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    battery = Column(Integer, nullable=True)
    power_source = Column(String, nullable=True)
    is_charging = Column(Boolean, nullable=True)
    speed = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    relay_state = Column(String, nullable=True)
    rssi = Column(Integer, nullable=True)
    
    # Payload
    operating_mode = Column(String, nullable=True)
    hydrogen_ppm = Column(Float, nullable=True)
    total_hours = Column(Float, nullable=True)

    # Relationships
    device = relationship("Device", back_populates="telemetry_history")


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    id = Column(String, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    
    type = Column(String, nullable=False)  # e.g., "SET_INTERVAL", "SET_RELAY"
    payload = Column(JSON, nullable=True)  # e.g., {"interval": 15}
    status = Column(String, default="PENDING")  # PENDING, SENT, ACKNOWLEDGED
    
    created_at = Column(DateTime, server_default=func.now())
    sent_at = Column(DateTime, nullable=True)
    acked_at = Column(DateTime, nullable=True)

    # Relationships
    device = relationship("Device", back_populates="commands")
