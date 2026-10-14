/**
 * NightWatch API Service Layer
 * Connects to FastAPI backend with WebSocket stream & polling fallback.
 */

import {
  AlertResponse,
  DigitalTwinResponse,
  OperatingThresholdsResponse,
  PatientProfileDetail,
  PatientSummary,
  PredictionResponse,
  RiskHorizonResponse,
  SensorReadingItem,
  SimulationStatusResponse,
  SleepFingerprintData,
  WhatIfRequest,
  WhatIfResponse,
  WhyRiskChangedResponse,
} from "../types";

// Prefer relative path which Vite proxies to localhost:8000, or direct env variable
const API_BASE = import.meta.env.VITE_API_URL || "";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API Error [${res.status}]: ${errorText || res.statusText}`);
  }

  return res.json();
}

export const api = {
  // Patients
  getPatients: (limit = 100, offset = 0) =>
    fetchJson<PatientSummary[]>(`/api/patients?limit=${limit}&offset=${offset}`),

  getPatientProfile: (id: string) =>
    fetchJson<PatientProfileDetail>(`/api/patients/${id}/profile`),

  // Digital Twin
  getPatientTwin: (id: string) =>
    fetchJson<DigitalTwinResponse>(`/api/patients/${id}/twin`),

  getRiskHorizon: (id: string) =>
    fetchJson<RiskHorizonResponse>(`/api/patients/${id}/risk-horizon`),

  getSleepFingerprint: (id: string) =>
    fetchJson<SleepFingerprintData>(`/api/patients/${id}/sleep-fingerprint`),

  getWhyRiskChanged: (id: string) =>
    fetchJson<WhyRiskChangedResponse>(`/api/patients/${id}/why-risk-changed`),

  getPatientRisk: (id: string) =>
    fetchJson<PredictionResponse>(`/api/patients/${id}/risk`),

  getPatientRiskHistory: (id: string, limit = 30) =>
    fetchJson<PredictionResponse[]>(`/api/patients/${id}/risk-history?limit=${limit}`),

  getPatientReadings: (id: string, sensorType?: string, limit = 50) => {
    const query = sensorType ? `?sensor_type=${sensorType}&limit=${limit}` : `?limit=${limit}`;
    return fetchJson<SensorReadingItem[]>(`/api/patients/${id}/sensor-readings${query}`);
  },

  postSensorReading: (id: string, reading: { sensor_type: string; value: number; unit: string; recorded_at: string; source?: string }) =>
    fetchJson<SensorReadingItem>(`/api/patients/${id}/sensor-readings`, {
      method: "POST",
      body: JSON.stringify(reading),
    }),

  // Thresholds
  getOperatingThresholds: () =>
    fetchJson<OperatingThresholdsResponse>("/api/thresholds"),

  // Alerts & Triage
  getPatientAlerts: (id: string) =>
    fetchJson<AlertResponse[]>(`/api/patients/${id}/alerts`),

  acknowledgeAlert: (alertId: string, clinicianName = "Dr. Clinician", comment?: string) =>
    fetchJson<AlertResponse>(`/api/alerts/${alertId}/acknowledge`, {
      method: "POST",
      body: JSON.stringify({ clinician_name: clinicianName, comment }),
    }),

  snoozeAlert: (alertId: string, clinicianName = "Dr. Clinician", snoozeHours = 4.0, reason?: string) =>
    fetchJson<AlertResponse>(`/api/alerts/${alertId}/snooze`, {
      method: "POST",
      body: JSON.stringify({ clinician_name: clinicianName, snooze_hours: snoozeHours, reason: reason || null }),
    }),

  markFalsePositive: (alertId: string, clinicianName = "Dr. Clinician", reason?: string) =>
    fetchJson<AlertResponse>(`/api/alerts/${alertId}/false-positive`, {
      method: "POST",
      body: JSON.stringify({ clinician_name: clinicianName, reason: reason || null }),
    }),

  addClinicianNote: (patientId: string, note: string, alertId?: string) =>
    fetchJson<{ note_id: string }>(`/api/patients/${patientId}/notes`, {
      method: "POST",
      body: JSON.stringify({ note, alert_id: alertId }),
    }),

  requestBpRecheck: (patientId: string, priority = "routine", instructions = "Rest seated for 5 minutes and repeat seated cuff measurement") =>
    fetchJson<{ status: string; message: string }>(`/api/patients/${patientId}/request-bp-recheck`, {
      method: "POST",
      body: JSON.stringify({ priority, instructions }),
    }),

  // Simulator & What-If
  runWhatIf: (patientId: string, request: WhatIfRequest) =>
    fetchJson<WhatIfResponse>(`/api/patients/${patientId}/what-if`, {
      method: "POST",
      body: JSON.stringify(request),
    }),

  getSimulationStatus: () =>
    fetchJson<SimulationStatusResponse>(`/api/simulation/status`),

  startSimulation: (stepSeconds = 10.0) =>
    fetchJson<{ status: string; message: string }>(`/api/simulation/start`, {
      method: "POST",
      body: JSON.stringify({ step_seconds: stepSeconds }),
    }),

  stopSimulation: () =>
    fetchJson<{ status: string; message: string }>(`/api/simulation/stop`, {
      method: "POST",
    }),

  injectScenario: (patientId: string, scenario: string) =>
    fetchJson<{ status: string; message: string }>(`/api/simulation/scenario/${patientId}`, {
      method: "POST",
      body: JSON.stringify({ scenario }),
    }),

  // Health
  getHealth: () => fetchJson<{ status: string }>(`/health`),
};

/**
 * WebSocket Connection with automatic reconnection and live twin stream
 */
export function createTwinWebSocket(
  patientId: string,
  onMessage: (twin: DigitalTwinResponse) => void,
  onStatusChange?: (connected: boolean) => void
): () => void {
  let ws: WebSocket | null = null;
  let closedManually = false;
  let reconnectTimer: any = null;

  const connect = () => {
    if (closedManually) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    // Connect through Vite proxy /ws/twin/{id} or direct 8000
    const wsUrl = `${protocol}//${host}/ws/twin/${patientId}`;

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        onStatusChange?.(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.patient_id) {
            onMessage(data as DigitalTwinResponse);
          }
        } catch (e) {
          console.warn("Failed to parse incoming WS message:", e);
        }
      };

      ws.onclose = () => {
        onStatusChange?.(false);
        if (!closedManually) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        ws?.close();
      };
    } catch {
      onStatusChange?.(false);
      if (!closedManually) {
        reconnectTimer = setTimeout(connect, 3000);
      }
    }
  };

  connect();

  return () => {
    closedManually = true;
    clearTimeout(reconnectTimer);
    ws?.close();
  };
}
