/**
 * NightWatch API Service Layer
 * Connects to FastAPI backend with WebSocket stream & polling fallback.
 */

import {
  AlertResponse,
  AuthUser,
  DigitalTwinResponse,
  OperatingThresholdsResponse,
  PatientProfileDetail,
  PatientSummary,
  PredictionResponse,
  RiskHorizonResponse,
  SensorReadingItem,
  SimulationStatusResponse,
  SleepFingerprintData,
  TokenResponse,
  WhatIfRequest,
  WhatIfResponse,
  WhyRiskChangedResponse,
} from "../types";

// Prefer relative path which Vite proxies to localhost:8000, or direct env variable
const API_BASE = import.meta.env.VITE_API_URL || "";

const TOKEN_KEY = "nightwatch_auth_token";
const USER_KEY = "nightwatch_auth_user";

export function getAuthToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string | null): void {
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token);
  } else {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

export function getStoredUser(): AuthUser | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: AuthUser | null): void {
  if (user) {
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    sessionStorage.removeItem(USER_KEY);
  }
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> || {}),
  };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent("nightwatch:unauthorized"));
    }
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

  getReadingsSeries: (id: string, days = 30) =>
    fetchJson<import("../types").ReadingsSeriesResponse>(`/api/patients/${id}/readings-series?days=${days}`),

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

  postWhatIf: (patientId: string, request: WhatIfRequest) =>
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

  // Health & System
  getHealth: () => fetchJson<{ status: string }>(`/health`),

  // Authentication & RBAC
  login: (username: string, password: string) =>
    fetchJson<TokenResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  getMe: () => fetchJson<AuthUser>("/api/auth/me"),
};

/**
 * WebSocket Connection with automatic reconnection, JWT token injection, and live twin stream
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
    const token = getAuthToken();
    // Connect through Vite proxy /ws/twin/{id} or direct 8000 with JWT token
    const wsUrl = `${protocol}//${host}/ws/twin/${patientId}${token ? `?token=${encodeURIComponent(token)}` : ""}`;

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

      ws.onclose = (event) => {
        onStatusChange?.(false);
        // Do not auto-reconnect if closed manually or policy violation (unauthorized 1008/4401)
        if (!closedManually && event?.code !== 1008 && event?.code !== 4401) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };

      ws.onerror = () => {
        onStatusChange?.(false);
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
    try {
      ws?.close();
    } catch {
      // ignore
    }
  };
}
