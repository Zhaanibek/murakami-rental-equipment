import os
import sys
import time
import random
import requests
from datetime import datetime

# ANSI Colors for beautiful logging
CLR_HEADER = '\033[95m'
CLR_BLUE = '\033[94m'
CLR_CYAN = '\033[96m'
CLR_GREEN = '\033[92m'
CLR_YELLOW = '\033[93m'
CLR_RED = '\033[91m'
CLR_RESET = '\033[0m'
CLR_BOLD = '\033[1m'

def log_info(msg):
    print(f"{CLR_CYAN}[INFO] {msg}{CLR_RESET}")

def log_send(msg):
    print(f"{CLR_BLUE}[SEND] {msg}{CLR_RESET}")

def log_recv(msg):
    print(f"{CLR_GREEN}[RECV] {msg}{CLR_RESET}")

def log_cmd(msg):
    print(f"{CLR_YELLOW}{CLR_BOLD}[CMD]  {msg}{CLR_RESET}")

def log_err(msg):
    print(f"{CLR_RED}[ERR]  {msg}{CLR_RESET}", file=sys.stderr)

# Pre-defined route coordinates in Almaty (cloesd-loop)
ROUTE = [
    (43.238949, 76.889709), # Abay / Altynsarin (Metro Moscow)
    (43.239250, 76.879500), # Abay / Momyshuly
    (43.238900, 76.860000), # Abay / Sain
    (43.244000, 76.859500), # Sain / Shalyapin
    (43.245000, 76.875000), # Shalyapin / Altynsarin
    (43.243500, 76.890000), # Shalyapin / Rozybakiev
    (43.239800, 76.900000), # Abay / Rozybakiev
]

def wait_for_backend(base_url, max_retries=30, delay=2):
    """Wait until the backend API is reachable before starting telemetry."""
    health_url = f"{base_url.rstrip('/')}/api/health"
    log_info(f"Waiting for backend at {health_url} ...")
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(health_url, timeout=3)
            if resp.status_code == 200:
                log_info(f"Backend is ready! (attempt {attempt})")
                return True
        except requests.exceptions.RequestException:
            pass
        log_info(f"Backend not ready, retrying in {delay}s ... (attempt {attempt}/{max_retries})")
        time.sleep(delay)
    log_err("Backend did not become available in time. Starting anyway...")
    return False


def main():
    # Read configurations from environment variables (or command arguments)
    server_base_url = os.getenv("SERVER_URL", "http://localhost:8080")
    device_id = os.getenv("DEVICE_ID", "velo_almaty_001")
    
    endpoint_url = f"{server_base_url.rstrip('/')}/api/telemetry/{device_id}"
    
    print(f"{CLR_HEADER}=====================================================")
    print(f" AeroTrack IoT Equipment Simulator v1.0")
    print(f" Target Endpoint: {endpoint_url}")
    print(f" Device ID:       {device_id}")
    print(f"====================================================={CLR_RESET}")

    # Wait for backend to be fully available before starting telemetry loop
    wait_for_backend(server_base_url)

    # Device Local State
    battery = 87
    relay_state = "ON"
    reporting_interval = 10  # Start with 10s for interactive feel, server will override
    is_charging = True
    power_source = "usb"
    total_hours = 1834.5
    acked_queue = []
    
    current_segment = 0
    progress = 0.0
    
    while True:
        try:
            # 1. Coordinate calculation (interpolation)
            p1 = ROUTE[current_segment]
            p2 = ROUTE[(current_segment + 1) % len(ROUTE)]
            lat = p1[0] + progress * (p2[0] - p1[0])
            lng = p1[1] + progress * (p2[1] - p1[1])
            
            # Step size: advance progress. Higher step = faster movement
            progress += 0.05
            if progress >= 1.0:
                progress = 0.0
                current_segment = (current_segment + 1) % len(ROUTE)
            
            # 2. Emulate physics (battery, speed, operating metrics)
            if relay_state == "ON":
                # Battery drain/charge loop
                if is_charging:
                    battery = min(100, battery + random.choice([1, 2]))
                    power_source = random.choice(["usb", "ac"])
                else:
                    battery = max(3, battery - random.choice([0, 1]))
                    power_source = "battery"
                
                # Speed simulation (randomized to match bike/scooter speed)
                speed = round(random.uniform(10.5, 18.0), 1)
                operating_mode = "active"
                hydrogen_ppm = round(random.uniform(0.8, 1.6), 2)
                # Accumulate operation time
                total_hours += (reporting_interval / 3600.0)
            else:
                # Device is off (relay state OFF)
                speed = 0.0
                operating_mode = "standby"
                hydrogen_ppm = 0.0
                is_charging = False
                power_source = "battery"
                battery = max(5, battery - random.choice([0, 1])) # slow idle drain
                
            accuracy = random.choice([4, 6, 8, 10, 12])
            rssi = random.randint(-95, -70)
            
            # Build Telemetry JSON
            payload = {
                "recordedAt": datetime.utcnow().isoformat() + "Z",
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "battery": battery,
                "powerSource": power_source,
                "isCharging": is_charging,
                "speed": speed,
                "accuracy": accuracy,
                "payload": {
                    "operatingMode": operating_mode,
                    "hydrogenPpm": hydrogen_ppm,
                    "totalHours": round(total_hours, 2)
                },
                "acked": acked_queue.copy(),
                "relayState": relay_state,
                "mcc": 401,
                "mnc": 1,
                "lac": 13500,
                "cellId": 123456789,
                "rssi": rssi
            }
            
            # Clear acked queue as we are posting them now
            acked_queue.clear()
            
            log_send(f"Uploading coordinates [{payload['lat']}, {payload['lng']}] (Battery: {battery}%, Relay: {relay_state})")
            
            # 3. HTTP Post telemetry to server
            start_time = time.time()
            response = requests.post(endpoint_url, json=payload, timeout=5)
            rtt = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                log_recv(f"HTTP 200 OK (RTT: {rtt}ms) Response: {data}")
                
                # 4. Handle Server Response configs & commands
                
                # Check desired relay/power state
                server_desired_power = data.get("desiredPowerState")
                if server_desired_power and server_desired_power != relay_state:
                    log_cmd(f"Power command received! Action: {data.get('powerCommand')}. Transitioning relay {relay_state} -> {server_desired_power}")
                    relay_state = server_desired_power
                    # If turning ON, turn charging back on too
                    if relay_state == "ON":
                        is_charging = True
                        power_source = "usb"
                    else:
                        is_charging = False
                        power_source = "battery"

                # Parse server's response command lists
                commands = data.get("commands", [])
                for cmd in commands:
                    cmd_id = cmd.get("id")
                    cmd_type = cmd.get("type")
                    cmd_payload = cmd.get("payload", {})
                    
                    log_cmd(f"Command fetched from queue: ID={cmd_id}, TYPE={cmd_type}, Payload={cmd_payload}")
                    
                    if cmd_type == "SET_INTERVAL":
                        target_interval = int(cmd_payload.get("interval", 30))
                        log_cmd(f"Adjusting local telemetry upload interval to {target_interval} seconds")
                        reporting_interval = target_interval
                    
                    elif cmd_type == "SET_RELAY":
                        # Relay was already handled via desiredPowerState, but we acknowledge it here
                        target_relay = cmd_payload.get("state")
                        if target_relay and target_relay != relay_state:
                            log_cmd(f"Adjusting relay via specific command to {target_relay}")
                            relay_state = target_relay
                    
                    # Queue ID to send confirmation back on next telemetry loop
                    if cmd_id not in acked_queue:
                        acked_queue.append(cmd_id)
                        
                # Update current reporting interval from server's base setting
                server_interval = data.get("interval")
                if server_interval and server_interval != reporting_interval:
                    reporting_interval = int(server_interval)
                    log_info(f"Interval updated from server configuration: {reporting_interval}s")
            
            else:
                log_err(f"Server responded with error status: {response.status_code}. Response: {response.text}")
                
        except requests.exceptions.RequestException as e:
            log_err(f"Connection failure to {endpoint_url}: {e}")
            
        # 5. Sleep based on local state configuration
        log_info(f"Sleeping for {reporting_interval} seconds before next report...\n")
        time.sleep(reporting_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{CLR_RED}Simulator interrupted. Exiting...{CLR_RESET}")
        sys.exit(0)
