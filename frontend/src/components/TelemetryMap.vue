```vue
<template>
  <div class="page">
   <header class="header">
    <div class="header-top">
      <div>
        <h1>Mission Support – Telemetry Dashboard</h1>
        <p class="subtitle">
          Live path, prediction, and environment for mission
          <strong>{{ missionLabel }}</strong>
          <span v-if="lastUpdated" class="last-updated">
            · Last updated {{ lastUpdated }}
          </span>
        </p>
      </div>

      <!-- NEW: Mission selector -->
      <div class="mission-select">
        <label for="mission" class="mission-label">Mission</label>
        <select
          id="mission"
          v-model="selectedMission"
          @change="onMissionChange"
        >
          <option v-if="!missions.length" disabled>
            No missions yet
          </option>
          <option v-for="m in missions" :key="m" :value="m">
            {{ m }}
          </option>
        </select>
        <div v-if="missionsError" class="missions-error">
          {{ missionsError }}
        </div>
      </div>
    </div>
  </header>

    <main class="layout">
      <section class="map-wrapper">
        <div id="map" class="map"></div>
      </section>

      <aside class="sidebar">
        <h2>Latest Telemetry</h2>

        <div v-if="error" class="error">
          {{ error }}
        </div>

        <div v-else-if="!latestPoints.length" class="empty">
          Waiting for telemetry…  
          <br />
          (Start the FastAPI backend and the Python sender client.)
        </div>

        <table v-else class="table">
          <thead>
            <tr>
              <th>Timestamp (UTC)</th>
              <th>Lat</th>
              <th>Lon</th>
              <th>Alt (m)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in latestPoints.slice(0, 10)" :key="p.timestamp">
              <td>{{ formatTime(p.timestamp) }}</td>
              <td>{{ p.lat.toFixed(5) }}</td>
              <td>{{ p.lon.toFixed(5) }}</td>
              <td>{{ p.altitude_m.toFixed(1) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Environment panel -->
        <section v-if="latestEnv" class="env-panel">
          <h2>Environment (latest)</h2>
          <div class="env-grid">
            <div class="env-card">
              <div class="env-label">Temperature</div>
              <div class="env-value">
                <span v-if="latestEnv.temperature_c != null">
                  {{ latestEnv.temperature_c.toFixed(1) }} °C
                </span>
                <span v-else>—</span>
              </div>
            </div>
            <div class="env-card">
              <div class="env-label">Pressure</div>
              <div class="env-value">
                <span v-if="latestEnv.pressure_hpa != null">
                  {{ latestEnv.pressure_hpa.toFixed(1) }} hPa
                </span>
                <span v-else>—</span>
              </div>
            </div>
            <div class="env-card">
              <div class="env-label">Humidity</div>
              <div class="env-value">
                <span v-if="latestEnv.humidity_pct != null">
                  {{ latestEnv.humidity_pct.toFixed(1) }} %
                </span>
                <span v-else>—</span>
              </div>
            </div>
          </div>
        </section>

        <!-- Environment history -->
        <section v-if="envHistory.length" class="env-history">
          <h3>Environment history (last {{ envHistory.length }} points)</h3>
          <table class="table small">
            <thead>
              <tr>
                <th>Time</th>
                <th>Temp (°C)</th>
                <th>Press (hPa)</th>
                <th>Hum (%)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in envHistory" :key="p.timestamp">
                <td>{{ shortTime(p.timestamp) }}</td>
                <td>{{ p.temperature_c != null ? p.temperature_c.toFixed(1) : "—" }}</td>
                <td>{{ p.pressure_hpa != null ? p.pressure_hpa.toFixed(1) : "—" }}</td>
                <td>{{ p.humidity_pct != null ? p.humidity_pct.toFixed(1) : "—" }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- Prediction panel -->
        <section v-if="prediction" class="prediction-panel">
          <h2>Prediction ({{ prediction.seconds }}s)</h2>
          <p>
            <strong>Speed:</strong>
            {{ prediction.velocity_mps.speed.toFixed(2) }} m/s<br />
            <strong>Heading:</strong>
            {{ prediction.velocity_mps.heading_deg.toFixed(1) }}°
          </p>
          <p>
            <strong>Final point:</strong><br />
            Lat {{ prediction.prediction.lat.toFixed(5) }},
            Lon {{ prediction.prediction.lon.toFixed(5) }}<br />
            Alt {{ prediction.prediction.altitude_m.toFixed(1) }} m
          </p>
        </section>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, computed } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const API_BASE = "http://127.0.0.1:8000";

const map = ref(null);
const pathLine = ref(null);
const predictedLine = ref(null);
const currentMarker = ref(null);

const latestPoints = ref([]);
const prediction = ref(null);
const error = ref(null);
const lastUpdatedRaw = ref(null);

// NEW: missions state
const missions = ref([]);
const selectedMission = ref(null);
const missionsError = ref(null);

const missionLabel = computed(() => {
  if (selectedMission.value) return selectedMission.value;
  if (!latestPoints.value.length) return "—";
  return latestPoints.value[0].mission_id ?? "Unknown";
});

const latestEnv = computed(() => {
  if (!latestPoints.value.length) return null;
  return latestPoints.value[0];
});

const envHistory = computed(() => latestPoints.value.slice(0, 10));

const lastUpdated = computed(() => {
  if (!lastUpdatedRaw.value) return "";
  return shortTime(lastUpdatedRaw.value);
});

let intervalId = null;

function formatTime(ts) {
  try {
    const d = new Date(ts);
    return d.toISOString().replace("T", " ").replace("Z", "Z");
  } catch {
    return ts;
  }
}

function shortTime(ts) {
  try {
    const d = new Date(ts);
    return d.toISOString().split("T")[1].replace("Z", "");
  } catch {
    return ts;
  }
}

// NEW: fetch missions list from backend
async function fetchMissions() {
  try {
    missionsError.value = null;
    const res = await fetch(`${API_BASE}/missions`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.status !== "ok") {
      throw new Error(`API status: ${data.status}`);
    }
    missions.value = data.missions ?? [];
    // If no mission selected yet and we have missions, pick the first one
    if (!selectedMission.value && missions.value.length > 0) {
      selectedMission.value = missions.value[0];
    }
  } catch (e) {
    console.error(e);
    missionsError.value = "Failed to load missions.";
  }
}

async function fetchTelemetry() {
  try {
    const missionQuery = selectedMission.value
      ? `&mission_id=${encodeURIComponent(selectedMission.value)}`
      : "";

    const res = await fetch(`${API_BASE}/telemetry?limit=100${missionQuery}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.status !== "ok") {
      throw new Error(`API status: ${data.status}`);
    }
    latestPoints.value = data.points ?? [];
    lastUpdatedRaw.value = new Date().toISOString();
  } catch (e) {
    console.error(e);
    error.value =
      "Failed to load telemetry. Is the FastAPI backend running on http://127.0.0.1:8000 ?";
    latestPoints.value = [];
  }
}

async function fetchPrediction() {
  try {
    const missionQuery = selectedMission.value
      ? `&mission_id=${encodeURIComponent(selectedMission.value)}`
      : "";

    const res = await fetch(
      `${API_BASE}/trajectory/predict?seconds=60&steps=4&limit=10${missionQuery}`
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.status !== "ok") {
      prediction.value = null; // e.g., not enough data
      return;
    }
    prediction.value = data;
  } catch (e) {
    console.error(e);
    // do not show as UI error; telemetry panel already handles backend status
  }
}

function updateMapFromData() {
  if (!map.value) return;

  // Actual path
  if (pathLine.value) {
    pathLine.value.remove();
    pathLine.value = null;
  }

  if (latestPoints.value.length >= 2) {
    const coords = [...latestPoints.value]
      .reverse()
      .map((p) => [p.lat, p.lon]);
    pathLine.value = L.polyline(coords).addTo(map.value);

    if (coords.length > 1) {
      const bounds = L.latLngBounds(coords);
      map.value.fitBounds(bounds, { padding: [20, 20] });
    }
  }

  // Current marker
  if (currentMarker.value) {
    currentMarker.value.remove();
    currentMarker.value = null;
  }

  const current = latestPoints.value[0];
  if (current) {
    currentMarker.value = L.circleMarker([current.lat, current.lon], {
      radius: 6,
    }).addTo(map.value);
  }

  // Predicted path
  if (predictedLine.value) {
    predictedLine.value.remove();
    predictedLine.value = null;
  }

  if (prediction.value && prediction.value.path?.length) {
    const coords = prediction.value.path.map((p) => [p.lat, p.lon]);
    predictedLine.value = L.polyline(coords, { dashArray: "4 4" }).addTo(
      map.value
    );
  }
}

async function refreshAll() {
  error.value = null;
  await fetchTelemetry();
  await fetchPrediction();
  updateMapFromData();
}

// NEW: when mission changes (dropdown), refresh telemetry/prediction
async function onMissionChange() {
  await refreshAll();
}

onMounted(async () => {
  map.value = L.map("map").setView([18.22, -66.59], 8);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map.value);

  await fetchMissions();
  await refreshAll();

  intervalId = window.setInterval(() => {
    refreshAll();
  }, 5000);
});

onBeforeUnmount(() => {
  if (intervalId !== null) {
    window.clearInterval(intervalId);
  }
  if (map.value) {
    map.value.remove();
    map.value = null;
  }
});
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;

  /* Make text clearly visible */
  color: #111;
  background-color: #fafafa;
}

.header {
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #ddd;
}

/* NEW: header layout */
.header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 1rem;
}

.header h1 {
  margin: 0;
  font-size: 1.25rem;
}

.subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.9rem;
  color: #555;
}

.last-updated {
  font-size: 0.8rem;
  color: #777;
  margin-left: 0.35rem;
}

/* NEW: mission selector styling */
.mission-select {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
}

.mission-label {
  font-size: 0.75rem;
  color: #555;
}

.mission-select select {
  font-size: 0.85rem;
  padding: 0.2rem 0.4rem;
}

.missions-error {
  font-size: 0.75rem;
  color: #b00020;
}

.layout {
  flex: 1;
  display: grid;
  grid-template-columns: 2fr 1fr;
  min-height: 0;
}

.map-wrapper {
  position: relative;
}

.map {
  width: 100%;
  height: 100%;
}

.sidebar {
  border-left: 1px solid #ddd;
  padding: 0.75rem;
  overflow-y: auto;
  background: #fafafa;
}

.sidebar h2,
.sidebar h3 {
  margin-top: 0.75rem;
  margin-bottom: 0.4rem;
}

.error {
  color: #b00020;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}

.empty {
  font-size: 0.9rem;
  color: #666;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
  margin-bottom: 0.75rem;
}

.table.small {
  font-size: 0.75rem;
}

.table th,
.table td {
  border-bottom: 1px solid #e1e1e1;
  padding: 0.25rem 0.35rem;
  text-align: left;
}

.table th {
  font-weight: 600;
}

.env-panel {
  margin-top: 0.5rem;
  padding-top: 0.4rem;
  border-top: 1px solid #ddd;
}

.env-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.4rem;
}

.env-card {
  background: #fff;
  border: 1px solid #e2e2e2;
  border-radius: 6px;
  padding: 0.4rem 0.5rem;
}

.env-label {
  font-size: 0.7rem;
  color: #777;
  margin-bottom: 0.2rem;
}

.env-value {
  font-size: 0.9rem;
  font-weight: 600;
}

.env-history {
  margin-top: 0.5rem;
}

.prediction-panel {
  font-size: 0.85rem;
  border-top: 1px solid #ddd;
  margin-top: 0.5rem;
  padding-top: 0.5rem;
}
</style>