// Global App State
const state = {
    devices: {},
    selectedDeviceId: null,
    map: null,
    deviceMarkers: {},
    pollingTimer: null,
    historyTimer: null,
    commandsTimer: null,
    searchQuery: ""
};

// Config: Default Almaty coords
const DEFAULT_LAT = 43.238949;
const DEFAULT_LNG = 76.889709;
const POLLING_INTERVAL_MS = 3000;

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    setupEventListeners();
    startPolling();
});

// ==========================================================================
// MAP FUNCTIONS
// ==========================================================================
function initMap() {
    // Instantiate map pointing to Almaty
    state.map = L.map("map", {
        zoomControl: true,
        maxZoom: 19
    }).setView([DEFAULT_LAT, DEFAULT_LNG], 12);

    // Apply CartoDB Dark Matter tiles for modern premium dark theme
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(state.map);
}

// Custom Leaflet Pulsing DivIcon
function createDeviceMarkerIcon(isActive) {
    const color = isActive ? '#6366f1' : '#10b981'; // Indigo for selected, Emerald for others
    const htmlContent = `
        <div class="custom-pin">
            <div class="pin-pulse" style="background-color: ${color}"></div>
            <div class="pin-center" style="background-color: ${color}"></div>
        </div>
    `;
    return L.divIcon({
        html: htmlContent,
        className: 'custom-leaflet-pin',
        iconSize: [32, 32],
        iconAnchor: [16, 16]
    });
}

function updateMapMarkers() {
    // Add/Update markers for each device in state
    Object.values(state.devices).forEach(device => {
        if (!device.lat || !device.lng) return;

        const isSelected = device.id === state.selectedDeviceId;
        const latlng = [device.lat, device.lng];

        if (state.deviceMarkers[device.id]) {
            // Update existing marker position and icon
            state.deviceMarkers[device.id].setLatLng(latlng);
            state.deviceMarkers[device.id].setIcon(createDeviceMarkerIcon(isSelected));
        } else {
            // Create a new marker
            const marker = L.marker(latlng, {
                icon: createDeviceMarkerIcon(isSelected),
                title: device.id
            }).addTo(state.map);

            // Click listener on marker selects the device
            marker.on("click", () => selectDevice(device.id));
            state.deviceMarkers[device.id] = marker;
        }
    });

    // Remove any markers for devices that are no longer in the state list
    Object.keys(state.deviceMarkers).forEach(deviceId => {
        if (!state.devices[deviceId]) {
            state.map.removeLayer(state.deviceMarkers[deviceId]);
            delete state.deviceMarkers[deviceId];
        }
    });
}

function centerMapOnDevice(deviceId) {
    const device = state.devices[deviceId];
    if (device && device.lat && device.lng) {
        if (state.map) {
            state.map.invalidateSize();
        }
        state.map.setView([device.lat, device.lng], 15, {
            animate: true,
            duration: 1.0
        });
    }
}

// ==========================================================================
// TELEMETRY & DEVICE FETCHING
// ==========================================================================
function startPolling() {
    fetchDevices();
    state.pollingTimer = setInterval(fetchDevices, POLLING_INTERVAL_MS);
}

async function fetchDevices() {
    try {
        const response = await fetch("/api/devices");
        if (!response.ok) throw new Error("Could not fetch devices list");
        const deviceList = await response.json();
        
        // Convert array to dictionary
        const newDevices = {};
        deviceList.forEach(device => {
            newDevices[device.id] = device;
        });

        state.devices = newDevices;
        
        // Render/update DOM elements
        renderDeviceList();
        updateMapMarkers();

        // Update selected device info if one is active
        if (state.selectedDeviceId) {
            if (state.devices[state.selectedDeviceId]) {
                updateDeviceMetricsDisplay(state.devices[state.selectedDeviceId]);
            } else {
                // Selected device deleted/vanished, reset UI
                selectDevice(null);
            }
        }
        
        // Update database connection status indicator
        document.getElementById("db-status").style.display = "flex";
    } catch (error) {
        console.error("Error fetching devices:", error);
        document.getElementById("db-status").style.display = "none";
    }
}

async function fetchSelectedDeviceDetails() {
    if (!state.selectedDeviceId) return;
    
    // Concurrently fetch telemetry history trace and command history queue
    fetchDeviceHistory();
    fetchDeviceCommands();
}

async function fetchDeviceHistory() {
    const deviceId = state.selectedDeviceId;
    if (!deviceId) return;

    try {
        const response = await fetch(`/api/devices/${deviceId}/history`);
        if (!response.ok) throw new Error("Could not fetch device history");
        const history = await response.json();

        // Stop updates if the selected device changed during the fetch promise
        if (state.selectedDeviceId !== deviceId) return;

        // 1. Render history list table rows
        renderHistoryTable(history);

        // 3. Render JSON Inspector viewer with the most recent telemetry packet
        if (history.length > 0) {
            // Build raw JSON telemetry payload matching the device upload format
            const latest = history[0];
            const rawPayload = {
                recordedAt: latest.recordedAt,
                lat: latest.lat,
                lng: latest.lng,
                battery: latest.battery,
                powerSource: latest.powerSource,
                isCharging: latest.isCharging,
                speed: latest.speed,
                accuracy: latest.accuracy,
                payload: latest.operatingMode || latest.hydrogenPpm || latest.totalHours ? {
                    operatingMode: latest.operatingMode,
                    hydrogenPpm: latest.hydrogenPpm,
                    totalHours: latest.totalHours
                } : null,
                acked: [], // simulator will set this dynamically
                relayState: latest.relayState,
                mcc: latest.mcc,
                mnc: latest.mnc,
                lac: latest.lac,
                cellId: latest.cellId,
                rssi: latest.rssi
            };
            document.getElementById("raw-json-viewer").textContent = JSON.stringify(rawPayload, null, 2);
        } else {
            document.getElementById("raw-json-viewer").textContent = JSON.stringify({ message: "Нет данных телеметрии для этого устройства." }, null, 2);
        }
    } catch (error) {
        console.error("Error fetching device history:", error);
    }
}

async function fetchDeviceCommands() {
    const deviceId = state.selectedDeviceId;
    if (!deviceId) return;

    try {
        const response = await fetch(`/api/devices/${deviceId}/commands`);
        if (!response.ok) throw new Error("Could not fetch commands list");
        const commands = await response.json();

        if (state.selectedDeviceId !== deviceId) return;

        renderCommandsLog(commands);
    } catch (error) {
        console.error("Error fetching commands list:", error);
    }
}

// ==========================================================================
// UI RENDERING & ACTIONS
// ==========================================================================
function selectDevice(deviceId) {
    if (state.selectedDeviceId === deviceId) {
        // Already selected, just focus map
        if (deviceId) centerMapOnDevice(deviceId);
        return;
    }

    state.selectedDeviceId = deviceId;
    
    // Clear previous history/command timers
    if (state.historyTimer) clearInterval(state.historyTimer);
    if (state.commandsTimer) clearInterval(state.commandsTimer);

    const noSelectionCard = document.getElementById("no-device-selected");
    const activeDashboard = document.getElementById("active-dashboard");

    if (!deviceId) {
        // Reset view to no-selection
        noSelectionCard.style.display = "block";
        activeDashboard.style.display = "none";
        document.getElementById("selected-device-title").textContent = "Выберите устройство";
        document.getElementById("selected-device-status-desc").textContent = "Панель управления оборудованием в реальном времени";
        return;
    }

    // Switch visible containers
    noSelectionCard.style.display = "none";
    activeDashboard.style.display = "flex";

    // Set header titles
    document.getElementById("selected-device-title").textContent = `Оборудование: ${deviceId}`;
    
    // Highlight list item in sidebar
    renderDeviceList();
    
    // Focus map on the device coordinates
    centerMapOnDevice(deviceId);
    
    // Instantly load device metadata and logs
    fetchSelectedDeviceDetails();
    
    // Set periodic sync timers for selected device detail panels
    state.historyTimer = setInterval(fetchDeviceHistory, POLLING_INTERVAL_MS);
    state.commandsTimer = setInterval(fetchDeviceCommands, POLLING_INTERVAL_MS);
}

function renderDeviceList() {
    const container = document.getElementById("device-list-container");
    const countSpan = document.getElementById("device-count");
    
    // Filter devices based on search query input
    const filteredDevices = Object.values(state.devices).filter(device => {
        return device.id.toLowerCase().includes(state.searchQuery.toLowerCase());
    });

    countSpan.textContent = filteredDevices.length;

    if (filteredDevices.length === 0) {
        container.innerHTML = `
            <div class="empty-list-message">
                ${state.searchQuery ? "Нет устройств, соответствующих фильтру" : "Нет активных устройств."}
            </div>
        `;
        return;
    }

    let html = "";
    filteredDevices.forEach(device => {
        const isSelected = device.id === state.selectedDeviceId;
        const isOnline = isDeviceOnline(device.lastSeen);
        const statusClass = isOnline ? "online" : "";
        const batteryIcon = getBatteryIconClass(device.battery);
        const timeAgoStr = formatTimeAgo(device.lastSeen);

        html += `
            <div class="device-item ${isSelected ? 'active' : ''}" onclick="selectDevice('${device.id}')">
                <div class="device-item-header">
                    <div class="device-name-wrapper">
                        <i class="fa-solid fa-hard-drive"></i>
                        <span class="device-title">${device.id}</span>
                    </div>
                    <span class="status-indicator ${statusClass}"></span>
                </div>
                <div class="device-item-details">
                    <div class="device-meta-item">
                        <i class="fa-solid ${batteryIcon}"></i>
                        <span>${device.battery !== null ? device.battery + '%' : '--'}</span>
                    </div>
                    <div class="device-meta-item">
                        <i class="fa-solid fa-power-off"></i>
                        <span>${device.relayState || '--'}</span>
                    </div>
                    <span class="device-item-time">${timeAgoStr}</span>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function updateDeviceMetricsDisplay(device) {
    const isOnline = isDeviceOnline(device.lastSeen);
    const statusDesc = isOnline ? "В сети (Онлайн)" : "Вне сети (Офлайн)";
    const timeAgoStr = formatTimeAgo(device.lastSeen);
    document.getElementById("selected-device-status-desc").textContent = `${statusDesc} — Последняя активность ${timeAgoStr}`;

    // 1. Battery display card
    const batteryVal = device.battery !== null ? device.battery : "--";
    document.getElementById("metric-battery-val").textContent = batteryVal;
    
    const progress = document.getElementById("battery-progress");
    progress.style.width = `${device.battery || 0}%`;
    
    // Set battery bar color based on level
    if (device.battery >= 70) {
        progress.style.backgroundColor = "var(--success)";
    } else if (device.battery >= 20) {
        progress.style.backgroundColor = "var(--warning)";
    } else {
        progress.style.backgroundColor = "var(--danger)";
    }
    
    const chargingText = device.isCharging ? "Заряжается" : "Не заряжается";
    document.getElementById("metric-battery-sub").textContent = `${chargingText} (${device.powerSource || 'battery'})`;

    // 2. Power source card
    let powerSrcLabel = "Автономное";
    if (device.powerSource === "usb") powerSrcLabel = "Сетевой (USB)";
    else if (device.powerSource === "ac") powerSrcLabel = "Сетевой (AC)";
    else if (device.powerSource === "solar") powerSrcLabel = "Солнечная панель";
    
    document.getElementById("metric-power-source").textContent = powerSrcLabel;
    document.getElementById("metric-charging-status").innerHTML = device.isCharging 
        ? `<i class="fa-solid fa-bolt" style="color: var(--success);"></i> Идет зарядка` 
        : `<i class="fa-solid fa-battery-half"></i> Работа от батареи`;

    // 3. Relay state card
    const badge = document.getElementById("relay-status-badge");
    badge.textContent = device.relayState || "--";
    badge.className = "relay-badge"; // reset classes
    
    if (device.relayState === "ON") {
        badge.classList.add("on");
        document.getElementById("metric-relay-sub").textContent = `Desired State: ${device.desiredPowerState}`;
    } else if (device.relayState === "OFF") {
        badge.classList.add("off");
        document.getElementById("metric-relay-sub").textContent = `Desired State: ${device.desiredPowerState}`;
    } else {
        document.getElementById("metric-relay-sub").textContent = "Состояние неопределенно";
    }

    // Update power switch control button active layouts based on user desired state
    const btnOn = document.getElementById("btn-relay-on");
    const btnOff = document.getElementById("btn-relay-off");
    
    if (device.desiredPowerState === "ON") {
        btnOn.classList.add("active");
        btnOff.classList.remove("active");
    } else {
        btnOff.classList.add("active");
        btnOn.classList.remove("active");
    }

    // Update default selected interval dropdown value if it is not currently focused by user
    const selectInterval = document.getElementById("select-interval");
    if (document.activeElement !== selectInterval) {
        selectInterval.value = device.reportingInterval || 30;
    }

    // 4. RSSI Wifi signal strength
    const rssiVal = device.rssi !== null ? device.rssi : "--";
    document.getElementById("metric-rssi-val").textContent = rssiVal;
    
    // Set cells signal indicators bars
    updateSignalBars(device.rssi);
    document.getElementById("metric-cell-info").textContent = `MCC: ${device.mcc || '--'} | MNC: ${device.mnc || '--'} | LAC: ${device.lac || '--'}`;

    // 5. Speed card
    const speedVal = device.speed !== null ? device.speed.toFixed(1) : "--";
    document.getElementById("metric-speed-val").textContent = speedVal;
    
    const accuracyVal = device.accuracy !== null ? device.accuracy.toFixed(1) : "--";
    document.getElementById("metric-accuracy-val").textContent = `Точность GPS: ±${accuracyVal} м`;

    // 6. Extra payload parameters
    document.getElementById("metric-hydrogen").textContent = device.hydrogenPpm !== null ? device.hydrogenPpm.toFixed(2) : "--";
    document.getElementById("metric-hours").textContent = device.totalHours !== null ? device.totalHours.toFixed(1) : "--";
    
    let modeText = "Неизвестно";
    if (device.operatingMode === "active") modeText = "Активный (Active)";
    else if (device.operatingMode === "standby") modeText = "Ожидание (Standby)";
    else if (device.operatingMode === "eco") modeText = "Энергосберегающий";
    document.getElementById("metric-opmode").textContent = `Режим: ${modeText}`;
}

function updateSignalBars(rssi) {
    // Reset bar states
    for (let i = 1; i <= 5; i++) {
        document.getElementById(`sig-${i}`).classList.remove("active");
    }

    if (rssi === null || rssi === undefined) return;

    // Map RSSI (typically -113 to -50) to 1-5 signal bars
    let bars = 0;
    if (rssi > -70) bars = 5;       // Excellent
    else if (rssi > -85) bars = 4;  // Good
    else if (rssi > -95) bars = 3;  // Fair
    else if (rssi > -105) bars = 2; // Weak
    else if (rssi > -115) bars = 1; // Extremely weak
    
    for (let i = 1; i <= bars; i++) {
        document.getElementById(`sig-${i}`).classList.add("active");
    }
}

function renderHistoryTable(history) {
    const tbody = document.getElementById("telemetry-history-rows");
    
    if (history.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">История перемещений отсутствует.</td></tr>`;
        return;
    }

    let html = "";
    // Show only the 5 most recent records in details panel table
    history.slice(0, 5).forEach(row => {
        const timeStr = formatDateTime(row.recordedAt);
        const coordsStr = `${row.lat.toFixed(6)}, ${row.lng.toFixed(6)}`;
        const chargeIcon = row.isCharging ? `<i class="fa-solid fa-bolt" style="color: var(--success);" title="Заряжается"></i>` : `<i class="fa-solid fa-battery-half" title="Разряжается"></i>`;
        const relayBadge = row.relayState === "ON" 
            ? `<span class="relay-badge on" style="font-size: 0.65rem; padding: 2px 6px;">ON</span>` 
            : `<span class="relay-badge off" style="font-size: 0.65rem; padding: 2px 6px;">OFF</span>`;

        html += `
            <tr>
                <td>${timeStr}</td>
                <td style="font-family: var(--font-mono);">${coordsStr}</td>
                <td>${row.battery || 0}%</td>
                <td class="text-center">${chargeIcon}</td>
                <td>${relayBadge}</td>
                <td>${row.speed !== null ? row.speed.toFixed(1) + ' км/ч' : '0.0'}</td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

function renderCommandsLog(commands) {
    const tbody = document.getElementById("commands-log-body");

    if (commands.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-muted text-center">Нет отправленных команд</td></tr>`;
        return;
    }

    let html = "";
    commands.forEach(cmd => {
        let payloadStr = "--";
        if (cmd.type === "SET_INTERVAL" && cmd.payload) {
            payloadStr = `${cmd.payload.interval} сек`;
        } else if (cmd.type === "SET_RELAY" && cmd.payload) {
            payloadStr = `Реле: ${cmd.payload.state}`;
        }

        const statusClass = cmd.status.toLowerCase();
        let statusLabel = cmd.status;
        if (cmd.status === "PENDING") statusLabel = "Ожидает (Pending)";
        else if (cmd.status === "SENT") statusLabel = "Отправлено (Sent)";
        else if (cmd.status === "ACKNOWLEDGED") statusLabel = "Выполнено (Acked)";

        html += `
            <tr>
                <td style="font-family: var(--font-mono); font-size: 0.72rem;">${cmd.id}</td>
                <td><strong>${cmd.type}</strong></td>
                <td>${payloadStr}</td>
                <td><span class="cmd-status ${statusClass}">${statusLabel}</span></td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

// ==========================================================================
// CONTROLLER EVENT HANDLING
// ==========================================================================
function setupEventListeners() {
    // Search input typing filter
    document.getElementById("device-search").addEventListener("input", (e) => {
        state.searchQuery = e.target.value;
        renderDeviceList();
    });

    // Fit Map viewport bounds to center around active device
    document.getElementById("btn-fit-map").addEventListener("click", () => {
        if (state.selectedDeviceId) {
            centerMapOnDevice(state.selectedDeviceId);
        }
    });

    // Refresh history button click action
    document.getElementById("btn-refresh-history").addEventListener("click", () => {
        fetchSelectedDeviceDetails();
    });

    // Toggle Relay buttons actions
    document.getElementById("btn-relay-on").addEventListener("click", () => triggerRelayChange("ON"));
    document.getElementById("btn-relay-off").addEventListener("click", () => triggerRelayChange("OFF"));

    // Set interval button click action
    document.getElementById("btn-send-interval").addEventListener("click", triggerIntervalChange);

    // Raw JSON copy clipboard utility
    document.getElementById("btn-copy-raw").addEventListener("click", () => {
        const jsonText = document.getElementById("raw-json-viewer").textContent;
        navigator.clipboard.writeText(jsonText)
            .then(() => {
                const btn = document.getElementById("btn-copy-raw");
                btn.innerHTML = `<i class="fa-solid fa-check" style="color: var(--success);"></i> Скопировано!`;
                setTimeout(() => {
                    btn.innerHTML = `<i class="fa-regular fa-copy"></i> Копировать`;
                }, 2000);
            })
            .catch(err => {
                alert("Ошибка копирования в буфер.");
            });
    });
}

async function triggerRelayChange(targetState) {
    const deviceId = state.selectedDeviceId;
    if (!deviceId) return;

    try {
        const response = await fetch(`/api/devices/${deviceId}/commands`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                type: "SET_RELAY",
                payload: { state: targetState }
            })
        });

        if (!response.ok) throw new Error("Could not send relay command");
        
        // Success: Instantly load updated list
        fetchDeviceCommands();
        
        // Update model state in UI instantly to make it feel responsive
        if (state.devices[deviceId]) {
            state.devices[deviceId].desiredPowerState = targetState;
            updateDeviceMetricsDisplay(state.devices[deviceId]);
        }
    } catch (error) {
        alert(`Ошибка при отправке команды реле: ${error.message}`);
    }
}

async function triggerIntervalChange() {
    const deviceId = state.selectedDeviceId;
    if (!deviceId) return;

    const select = document.getElementById("select-interval");
    const intervalVal = parseInt(select.value);

    try {
        const btn = document.getElementById("btn-send-interval");
        btn.disabled = true;
        btn.textContent = "Отправка...";

        const response = await fetch(`/api/devices/${deviceId}/commands`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                type: "SET_INTERVAL",
                payload: { interval: intervalVal }
            })
        });

        btn.disabled = false;
        btn.innerHTML = `Отправить`;

        if (!response.ok) throw new Error("Could not queue interval command");

        fetchDeviceCommands();
    } catch (error) {
        alert(`Ошибка при изменении интервала: ${error.message}`);
    }
}

// ==========================================================================
// UTILITY FUNCTIONS
// ==========================================================================
function isDeviceOnline(lastSeenIso) {
    if (!lastSeenIso) return false;
    const lastSeen = new Date(lastSeenIso);
    const diffSeconds = (new Date() - lastSeen) / 1000;
    // Consider online if telemetry packet received within last 90 seconds
    return diffSeconds < 90;
}

function getBatteryIconClass(battery) {
    if (battery === null || battery === undefined) return "fa-battery-empty";
    if (battery > 85) return "fa-battery-full";
    if (battery > 60) return "fa-battery-three-quarters";
    if (battery > 35) return "fa-battery-half";
    if (battery > 15) return "fa-battery-quarter";
    return "fa-battery-empty";
}

function formatDateTime(isoString) {
    if (!isoString) return "--";
    const date = new Date(isoString);
    return date.toLocaleString("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        day: "2-digit",
        month: "2-digit",
        year: "numeric"
    });
}

function formatTimeAgo(isoString) {
    if (!isoString) return "никогда";
    const date = new Date(isoString);
    const seconds = Math.floor((new Date() - date) / 1000);
    
    if (seconds < 5) return "только что";
    if (seconds < 60) return `${seconds} сек назад`;
    
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} мин назад`;
    
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} ч назад`;
    
    return date.toLocaleDateString("ru-RU");
}
