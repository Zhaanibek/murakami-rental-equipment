import uuid
from datetime import datetime
from typing import List
from fastapi import FastAPI, Depends, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app import models, schemas

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Rental Equipment Management API",
    description="MVP API for tracking rental equipment and dispatching commands.",
    version="1.0.0"
)

# Enable CORS for development (Nginx proxy handles production routing without CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health", status_code=status.HTTP_200_OK)
def health_check():
    """Verify that backend is active."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# --- DEVICE TELEMETRY INGESTION ---

@app.post(
    "/api/telemetry/{device_id}",
    response_model=schemas.TelemetryResponse,
    status_code=status.HTTP_200_OK
)
def post_telemetry(
    telemetry: schemas.TelemetryCreate,
    device_id: str = Path(..., pattern="^[a-zA-Z0-9_-]{3,50}$", description="Sanitized unique device identifier"),
    db: Session = Depends(get_db)
):
    """
    Endpoint for devices to upload telemetry data.
    Updates the device state, archives data to history, and returns pending commands.
    """
    # 1. Fetch or create the Device state entry
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        device = models.Device(
            id=device_id,
            reporting_interval=30,
            desired_power_state="ON",
            relay_state=telemetry.relay_state
        )
        db.add(device)
        db.flush()  # Generate device entry in the current transaction session

    # 2. Update device state columns from latest telemetry
    device.last_seen = datetime.utcnow()
    device.lat = telemetry.lat
    device.lng = telemetry.lng
    device.battery = telemetry.battery
    device.power_source = telemetry.power_source
    device.is_charging = telemetry.is_charging
    device.speed = telemetry.speed
    device.accuracy = telemetry.accuracy
    device.relay_state = telemetry.relay_state
    device.rssi = telemetry.rssi
    
    if telemetry.payload:
        device.operating_mode = telemetry.payload.operating_mode
        device.hydrogen_ppm = telemetry.payload.hydrogen_ppm
        device.total_hours = telemetry.payload.total_hours
        
    device.mcc = telemetry.mcc
    device.mnc = telemetry.mnc
    device.lac = telemetry.lac
    device.cell_id = telemetry.cell_id

    # 3. Create a historical telemetry entry
    history = models.TelemetryHistory(
        device_id=device_id,
        recorded_at=telemetry.recorded_at,
        lat=telemetry.lat,
        lng=telemetry.lng,
        battery=telemetry.battery,
        power_source=telemetry.power_source,
        is_charging=telemetry.is_charging,
        speed=telemetry.speed,
        accuracy=telemetry.accuracy,
        relay_state=telemetry.relay_state,
        rssi=telemetry.rssi,
        operating_mode=telemetry.payload.operating_mode if telemetry.payload else None,
        hydrogen_ppm=telemetry.payload.hydrogen_ppm if telemetry.payload else None,
        total_hours=telemetry.payload.total_hours if telemetry.payload else None,
    )
    db.add(history)

    # 4. Handle incoming Acknowledged (acked) commands list
    if telemetry.acked:
        db.query(models.DeviceCommand).filter(
            models.DeviceCommand.device_id == device_id,
            models.DeviceCommand.id.in_(telemetry.acked),
            models.DeviceCommand.status != "ACKNOWLEDGED"
        ).update(
            {
                models.DeviceCommand.status: "ACKNOWLEDGED",
                models.DeviceCommand.acked_at: datetime.utcnow()
            },
            synchronize_session=False
        )

        # Update actual interval in device configuration if SET_INTERVAL was ACKed
        interval_commands = db.query(models.DeviceCommand).filter(
            models.DeviceCommand.device_id == device_id,
            models.DeviceCommand.id.in_(telemetry.acked),
            models.DeviceCommand.type == "SET_INTERVAL"
        ).all()
        for cmd in interval_commands:
            if cmd.payload and "interval" in cmd.payload:
                device.reporting_interval = int(cmd.payload["interval"])

    # 5. Fetch commands to return in response (PENDING or SENT)
    pending_commands = db.query(models.DeviceCommand).filter(
        models.DeviceCommand.device_id == device_id,
        models.DeviceCommand.status.in_(["PENDING", "SENT"])
    ).all()

    # Mark PENDING commands as SENT
    response_commands = []
    for cmd in pending_commands:
        if cmd.status == "PENDING":
            cmd.status = "SENT"
            cmd.sent_at = datetime.utcnow()
        response_commands.append(
            schemas.DeviceCommandResponse(
                id=cmd.id,
                type=cmd.type,
                payload=cmd.payload
            )
        )

    # Commit changes to DB
    db.commit()

    # 6. Build the telemetry response JSON
    power_cmd = "TURN_ON" if device.desired_power_state == "ON" else "TURN_OFF"
    
    return schemas.TelemetryResponse(
        interval=device.reporting_interval,
        commands=response_commands,
        desired_power_state=device.desired_power_state,
        power_command=power_cmd
    )

# --- FRONTEND MANAGEMENT API ---

@app.get("/api/devices", response_model=List[schemas.DeviceInfo])
def list_devices(db: Session = Depends(get_db)):
    """Fetch list of all devices in the system."""
    return db.query(models.Device).order_by(models.Device.id).all()

@app.get("/api/devices/{device_id}", response_model=schemas.DeviceInfo)
def get_device(
    device_id: str = Path(..., pattern="^[a-zA-Z0-9_-]{3,50}$"),
    db: Session = Depends(get_db)
):
    """Get latest state of a specific device."""
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@app.get("/api/devices/{device_id}/history", response_model=List[schemas.TelemetryHistoryInfo])
def get_device_history(
    device_id: str = Path(..., pattern="^[a-zA-Z0-9_-]{3,50}$"),
    db: Session = Depends(get_db)
):
    """Retrieve the telemetry trace history of a device."""
    # Ensure device exists
    device_exists = db.query(models.Device.id).filter(models.Device.id == device_id).first()
    if not device_exists:
        raise HTTPException(status_code=404, detail="Device not found")

    return db.query(models.TelemetryHistory)\
             .filter(models.TelemetryHistory.device_id == device_id)\
             .order_by(models.TelemetryHistory.recorded_at.desc())\
             .limit(100)\
             .all()

@app.post("/api/devices/{device_id}/commands", response_model=schemas.CommandInfo)
def send_command(
    command_req: schemas.CommandCreate,
    device_id: str = Path(..., pattern="^[a-zA-Z0-9_-]{3,50}$"),
    db: Session = Depends(get_db)
):
    """
    Queue a command for the specified device.
    If command is SET_RELAY, updates desired_power_state instantly.
    """
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Generate random unique short command ID
    cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"

    # If it is a relay change command, update the device desired state instantly
    if command_req.type == "SET_RELAY":
        state = command_req.payload.get("state")
        if state not in ("ON", "OFF"):
            raise HTTPException(status_code=400, detail="Relay state must be ON or OFF")
        device.desired_power_state = state

    # Save command to DB queue
    new_cmd = models.DeviceCommand(
        id=cmd_id,
        device_id=device_id,
        type=command_req.type,
        payload=command_req.payload,
        status="PENDING"
    )
    db.add(new_cmd)
    db.commit()
    db.refresh(new_cmd)
    
    return new_cmd

@app.get("/api/devices/{device_id}/commands", response_model=List[schemas.CommandInfo])
def list_device_commands(
    device_id: str = Path(..., pattern="^[a-zA-Z0-9_-]{3,50}$"),
    db: Session = Depends(get_db)
):
    """Get the command log/queue list for a device."""
    device_exists = db.query(models.Device.id).filter(models.Device.id == device_id).first()
    if not device_exists:
        raise HTTPException(status_code=404, detail="Device not found")

    return db.query(models.DeviceCommand)\
             .filter(models.DeviceCommand.device_id == device_id)\
             .order_by(models.DeviceCommand.created_at.desc())\
             .limit(50)\
             .all()
