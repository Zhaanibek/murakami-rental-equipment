import os
import pytest
from fastapi.testclient import TestClient

# Set environment variable to SQLite for local isolated testing before importing the app
os.environ["DATABASE_URL"] = "sqlite:///./test_rental_equipment.db"

# Clear test DB if it exists from a crashed run
if os.path.exists("./test_rental_equipment.db"):
    try:
        os.remove("./test_rental_equipment.db")
    except OSError:
        pass

from app.main import app
from app.database import engine, Base

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    # Make sure all tables are created in the SQLite database
    Base.metadata.create_all(bind=engine)
    yield
    # Teardown: close engine connections and delete SQLite file
    engine.dispose()
    if os.path.exists("./test_rental_equipment.db"):
        try:
            os.remove("./test_rental_equipment.db")
        except OSError:
            pass

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_device_not_found():
    response = client.get("/api/devices/non_existent_device")
    assert response.status_code == 404

def test_device_telemetry_flow():
    device_id = "test_velo_999"
    
    # 1. Post telemetry for new device (should create the device)
    telemetry_payload = {
        "recordedAt": "2026-05-16T11:30:00.000Z",
        "lat": 43.238949,
        "lng": 76.889709,
        "battery": 87,
        "powerSource": "battery",
        "isCharging": False,
        "speed": 12.5,
        "accuracy": 8,
        "payload": {
            "operatingMode": "active",
            "hydrogenPpm": 1.2,
            "totalHours": 1834.5
        },
        "acked": [],
        "relayState": "ON",
        "mcc": 401,
        "mnc": 1,
        "lac": 13500,
        "cellId": 123456789,
        "rssi": -85
    }
    
    response = client.post(f"/api/telemetry/{device_id}", json=telemetry_payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["interval"] == 30
    assert data["desiredPowerState"] == "ON"
    assert data["powerCommand"] == "TURN_ON"
    assert len(data["commands"]) == 0  # No commands queued yet

    # 2. Get list of devices (device should be listed with correct state)
    response = client.get("/api/devices")
    assert response.status_code == 200
    devices = response.json()
    assert len(devices) == 1
    assert devices[0]["id"] == device_id
    assert devices[0]["battery"] == 87
    assert devices[0]["relayState"] == "ON"
    assert devices[0]["reportingInterval"] == 30

    # 3. Post a command from the UI to change reporting interval to 15s
    command_payload = {
        "type": "SET_INTERVAL",
        "payload": {
            "interval": 15
        }
    }
    response = client.post(f"/api/devices/{device_id}/commands", json=command_payload)
    assert response.status_code == 200
    cmd_data = response.json()
    assert cmd_data["type"] == "SET_INTERVAL"
    assert cmd_data["payload"] == {"interval": 15}
    assert cmd_data["status"] == "PENDING"
    cmd_id = cmd_data["id"]

    # 4. Post telemetry again (server should dispatch the command)
    response = client.post(f"/api/telemetry/{device_id}", json=telemetry_payload)
    assert response.status_code == 200
    telemetry_resp = response.json()
    
    # The command should now be in the list of dispatched commands, and its status will update to SENT
    assert len(telemetry_resp["commands"]) == 1
    assert telemetry_resp["commands"][0]["id"] == cmd_id
    assert telemetry_resp["commands"][0]["type"] == "SET_INTERVAL"
    assert telemetry_resp["commands"][0]["payload"] == {"interval": 15}

    # 5. Check command status (should be SENT in DB log)
    response = client.get(f"/api/devices/{device_id}/commands")
    assert response.status_code == 200
    cmds_log = response.json()
    assert cmds_log[0]["id"] == cmd_id
    assert cmds_log[0]["status"] == "SENT"

    # 6. Post telemetry with command ID in "acked" list (device confirms execution)
    telemetry_payload_acked = telemetry_payload.copy()
    telemetry_payload_acked["acked"] = [cmd_id]
    
    response = client.post(f"/api/telemetry/{device_id}", json=telemetry_payload_acked)
    assert response.status_code == 200
    telemetry_resp_acked = response.json()
    
    # Command is now executed, so the reporting interval returned by server becomes 15, and commands queue is empty
    assert telemetry_resp_acked["interval"] == 15
    assert len(telemetry_resp_acked["commands"]) == 0

    # 7. Check command status in DB (should show ACKNOWLEDGED)
    response = client.get(f"/api/devices/{device_id}/commands")
    assert response.status_code == 200
    cmds_log = response.json()
    assert cmds_log[0]["id"] == cmd_id
    assert cmds_log[0]["status"] == "ACKNOWLEDGED"

    # 8. Check device state in DB (reportingInterval should be 15)
    response = client.get(f"/api/devices/{device_id}")
    assert response.status_code == 200
    device_state = response.json()
    assert device_state["reportingInterval"] == 15

    # 9. Verify history trace contains logs
    response = client.get(f"/api/devices/{device_id}/history")
    assert response.status_code == 200
    history = response.json()
    assert len(history) >= 2  # Telemetry was posted multiple times
    assert history[0]["lat"] == 43.238949
    assert history[0]["lng"] == 76.889709
