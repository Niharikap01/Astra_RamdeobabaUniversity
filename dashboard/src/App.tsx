/**
 * NightWatch Dashboard — Clinical Decision Support Observatory
 * Tier 1: Three-zone layout, Risk Horizon trajectory, live WebSocket stream,
 * alert triage, and clinical safety guardrails.
 */

import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Layers,
  RefreshCw,
  Sliders,
  Sparkles,
  Wifi,
  WifiOff,
} from "lucide-react";
import { api, createTwinWebSocket } from "./services/api";
import {
  AlertResponse,
  DigitalTwinResponse,
  OperatingThresholdsResponse,
  PatientProfileDetail,
  PatientSummary,
  RiskHorizonResponse,
  SimulationStatusResponse,
} from "./types";
import { NavigationRail } from "./components/NavigationRail";
import { PatientHeader } from "./components/PatientHeader";
import { RightAlertDrawer } from "./components/RightAlertDrawer";
import { RiskHorizonChart } from "./components/RiskHorizonChart";
import { RiskSummaryCard } from "./components/RiskSummaryCard";
import { DataTableToggle } from "./components/DataTableToggle";

export default function App() {
  // Theme & Accessibility
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [reducedMotion, setReducedMotion] = useState<boolean>(false);

  // Cohort & Selection
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const [patientProfile, setPatientProfile] = useState<PatientProfileDetail | null>(null);

  // Live Twin & Telemetry
  const [twin, setTwin] = useState<DigitalTwinResponse | null>(null);
  const [riskHorizon, setRiskHorizon] = useState<RiskHorizonResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertResponse[]>([]);
  const [thresholds, setThresholds] = useState<OperatingThresholdsResponse | null>(null);
  const [simulationStatus, setSimulationStatus] = useState<SimulationStatusResponse | null>(null);

  // Connection & Lifecycle States
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isOffline, setIsOffline] = useState<boolean>(false);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [lastUpdatedTime, setLastUpdatedTime] = useState<Date>(new Date());
  const [timeAgoText, setTimeAgoText] = useState<string>("just now");
  const [isAlertDrawerOpen, setIsAlertDrawerOpen] = useState<boolean>(true);
  const [isTableView, setIsTableView] = useState<boolean>(false);

  // Ref for polling interval
  const pollingRef = useRef<any>(null);

  // Time-ago formatting ticker
  useEffect(() => {
    const timer = setInterval(() => {
      const seconds = Math.floor((new Date().getTime() - lastUpdatedTime.getTime()) / 1000);
      if (seconds < 5) setTimeAgoText("just now");
      else if (seconds < 60) setTimeAgoText(`${seconds}s ago`);
      else if (seconds < 3600) setTimeAgoText(`${Math.floor(seconds / 60)}m ago`);
      else setTimeAgoText(`${Math.floor(seconds / 3600)}h ago`);
    }, 1000);
    return () => clearInterval(timer);
  }, [lastUpdatedTime]);

  // Initial Load: Cohort & Thresholds
  const loadInitialData = useCallback(async () => {
    setIsLoading(true);
    setIsOffline(false);
    try {
      const [pts, thresh, simStatus] = await Promise.all([
        api.getPatients(100),
        api.getOperatingThresholds().catch(() => ({ moderate: 0.35, high: 0.65, source: "fallback", cooldown_hours: 24 })),
        api.getSimulationStatus().catch(() => null),
      ]);

      setPatients(pts);
      setThresholds(thresh);
      setSimulationStatus(simStatus);

      if (pts.length > 0 && !selectedPatientId) {
        setSelectedPatientId(pts[0].patient_id);
      }
    } catch (err) {
      console.error("Initial load failed:", err);
      setIsOffline(true);
    } finally {
      setIsLoading(false);
    }
  }, [selectedPatientId]);

  useEffect(() => {
    loadInitialData();
  }, []);

  // Load Selected Patient Data
  const loadPatientData = useCallback(
    async (patientId: string) => {
      if (!patientId) return;
      try {
        const [profile, twinData, horizonData, alertsData] = await Promise.all([
          api.getPatientProfile(patientId),
          api.getPatientTwin(patientId).catch(() => null),
          api.getRiskHorizon(patientId).catch(() => null),
          api.getPatientAlerts(patientId).catch(() => []),
        ]);

        setPatientProfile(profile);
        if (twinData) setTwin(twinData);
        if (horizonData) setRiskHorizon(horizonData);
        setAlerts(alertsData);
        setLastUpdatedTime(new Date());
        setIsOffline(false);
      } catch (err) {
        console.error(`Failed to load telemetry for patient ${patientId}:`, err);
        setIsOffline(true);
      }
    },
    []
  );

  useEffect(() => {
    if (selectedPatientId) {
      loadPatientData(selectedPatientId);
    }
  }, [selectedPatientId, loadPatientData]);

  // WebSocket Live Stream with 5s Polling Fallback
  useEffect(() => {
    if (!selectedPatientId) return;

    let cleanupWs: (() => void) | null = null;

    try {
      cleanupWs = createTwinWebSocket(
        selectedPatientId,
        (updatedTwin) => {
          setTwin(updatedTwin);
          setLastUpdatedTime(new Date());
          // Refresh horizon and alerts concurrently
          api.getRiskHorizon(selectedPatientId).then(setRiskHorizon).catch(() => {});
          api.getPatientAlerts(selectedPatientId).then(setAlerts).catch(() => {});
        },
        (connected) => {
          setWsConnected(connected);
        }
      );
    } catch (e) {
      console.warn("WebSocket init error:", e);
      setWsConnected(false);
    }

    // Polling fallback when WS is inactive
    pollingRef.current = setInterval(() => {
      if (!wsConnected && selectedPatientId) {
        api.getPatientTwin(selectedPatientId).then((t) => {
          setTwin(t);
          setLastUpdatedTime(new Date());
        }).catch(() => {});
        api.getRiskHorizon(selectedPatientId).then(setRiskHorizon).catch(() => {});
        api.getPatientAlerts(selectedPatientId).then(setAlerts).catch(() => {});
      }
    }, 5000);

    return () => {
      if (cleanupWs) cleanupWs();
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [selectedPatientId, wsConnected]);

  // Simulation Controls
  const handleToggleSimulation = async () => {
    try {
      if (simulationStatus?.is_running) {
        await api.stopSimulation();
      } else {
        await api.startSimulation(10.0);
      }
      const st = await api.getSimulationStatus();
      setSimulationStatus(st);
    } catch (e) {
      console.error("Simulation toggle error:", e);
    }
  };

  // Alert Actions
  const handleAcknowledgeAlert = async (alertId: string) => {
    try {
      await api.acknowledgeAlert(alertId, "Dr. Clinician", "Reviewed telemetry");
      const updated = await api.getPatientAlerts(selectedPatientId);
      setAlerts(updated);
    } catch (e) {
      console.error("Failed to acknowledge alert:", e);
    }
  };

  const handleSnoozeAlert = async (alertId: string, hours: number, reason?: string) => {
    try {
      await api.snoozeAlert(alertId, "Dr. Clinician", hours, reason || "Awaiting repeat seated home BP reading");
      const updated = await api.getPatientAlerts(selectedPatientId);
      setAlerts(updated);
    } catch (e) {
      console.error("Failed to snooze alert:", e);
    }
  };

  const handleFalsePositiveAlert = async (alertId: string, reason?: string) => {
    try {
      await api.markFalsePositive(alertId, "Dr. Clinician", reason || "Uncalibrated cuff or acute non-hypertensive excursion");
      const updated = await api.getPatientAlerts(selectedPatientId);
      setAlerts(updated);
    } catch (e) {
      console.error("Failed to mark false positive:", e);
    }
  };

  // Risk Horizon Table Columns for CSV / Tabular View
  const horizonColumns = [
    { key: "timestamp", label: "Time (IST)", format: (val: string) => new Date(val).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) },
    { key: "hour_offset", label: "Hour Offset", format: (v: number) => (v === 0 ? "0 [NOW]" : v > 0 ? `+${v}h` : `${v}h`) },
    { key: "risk_pct", label: "Episode Risk", format: (v: number) => (v != null ? `${v}%` : "—") },
    { key: "is_predicted", label: "Type", format: (v: boolean) => (v ? "Modeled Forecast" : "Ground Truth History") },
    { key: "measured_sbp", label: "Measured SBP", format: (v: number) => (v ? `${v} mmHg` : "—") },
    { key: "measured_dbp", label: "Measured DBP", format: (v: number) => (v ? `${v} mmHg` : "—") },
    { key: "sleep_stage", label: "Sleep Window", format: (v: string, row: any) => (row.is_sleep_window ? v || "Sleep" : "Awake") },
    { key: "has_medication_event", label: "Medication Event", format: (v: boolean, row: any) => (v ? row.medication_name || "Dose Taken" : "None") },
  ];

  // Coverage check
  const dataCoverage = riskHorizon?.data_coverage_pct ?? patientProfile?.data_coverage_pct ?? 100;
  const isCoverageWithheld = dataCoverage < 50;

  return (
    <div className={`min-h-screen bg-[#0b0f19] text-slate-100 font-sans flex flex-col ${theme === "light" ? "theme-light" : ""}`}>
      {/* Top Telemetry Status Bar */}
      <div className="h-8 bg-slate-950/80 border-b border-slate-800/80 px-4 flex items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-slate-300 font-serif tracking-wider uppercase text-[10px]">
            NightWatch Clinical Observatory
          </span>
          <span className="text-slate-600">•</span>
          <span className="flex items-center gap-1.5 font-mono text-[11px]">
            {wsConnected ? (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-emerald-400 font-medium">LIVE STREAM (WS)</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-amber-400" />
                <span className="text-amber-400 font-medium">FALLBACK POLLING (5s)</span>
              </>
            )}
          </span>
          <span className="text-slate-600">•</span>
          <span className="font-mono text-[11px] text-slate-400">Updated {timeAgoText}</span>
        </div>

        <div className="flex items-center gap-4 text-[11px] font-mono">
          {simulationStatus && (
            <span className="flex items-center gap-1.5 text-cyan-400">
              <span className={`w-1.5 h-1.5 rounded-full ${simulationStatus.is_running ? "bg-cyan-400 animate-ping" : "bg-slate-600"}`} />
              Simulator: {simulationStatus.is_running ? "Active" : "Paused"} ({simulationStatus.ticks_completed} ticks)
            </span>
          )}
          <span>Timezone: Asia/Kolkata (UTC+05:30)</span>
        </div>
      </div>

      {/* Main 3-Zone Architecture */}
      <div className="flex-1 flex overflow-hidden">
        {/* Zone 1: Navigation Rail (Left) */}
        <NavigationRail
          patients={patients}
          selectedPatientId={selectedPatientId}
          onSelectPatient={(id) => setSelectedPatientId(id)}
          simulationStatus={simulationStatus}
          onToggleSimulation={handleToggleSimulation}
          onOpenSimulationModal={() => {}}
          theme={theme}
          onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
          reducedMotion={reducedMotion}
          onToggleReducedMotion={() => setReducedMotion(!reducedMotion)}
          wsConnected={wsConnected}
        />

        {/* Zone 2: Clinical Workspace (Center) */}
        <main className="flex-1 flex flex-col min-w-0 overflow-y-auto bg-slate-950/40">
          {/* Patient Header */}
          {patientProfile && (
            <PatientHeader
              patient={patientProfile}
              twin={twin}
              onRequestRecheck={() => api.requestBpRecheck(selectedPatientId)}
              onAddNote={() => {}}
              onOpenWhatIf={() => {}}
              onToggleTableView={() => setIsTableView(!isTableView)}
              isTableView={isTableView}
            />
          )}

          {/* Offline Warning Banner */}
          {isOffline && (
            <div className="m-4 p-3 bg-rose-950/40 border border-rose-500/50 rounded-xl flex items-center justify-between text-xs text-rose-300">
              <div className="flex items-center gap-2">
                <AlertOctagon className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>Backend communication interrupted. Retrying live connection...</span>
              </div>
              <button
                onClick={() => loadPatientData(selectedPatientId)}
                className="px-2.5 py-1 rounded bg-rose-900/60 hover:bg-rose-800 border border-rose-700/60 font-medium flex items-center gap-1.5 transition-colors"
              >
                <RefreshCw className="w-3 h-3" />
                Retry
              </button>
            </div>
          )}

          {/* Low Coverage Refusal Banner */}
          {isCoverageWithheld && (
            <div className="m-4 p-3 bg-amber-950/40 border border-amber-500/50 rounded-xl flex items-center gap-3 text-xs text-amber-200">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
              <div>
                <p className="font-semibold text-amber-300">Prediction Refused: Insufficient Sensor Telemetry</p>
                <p className="text-amber-200/80 mt-0.5">
                  Available coverage ({Math.round(dataCoverage)}%) is below the mandatory 50% clinical safety threshold.
                  NightWatch will not fabricate forecasts. A verified home blood pressure cuff measurement is required to resume prediction.
                </p>
              </div>
            </div>
          )}

          {/* Content Body */}
          <div className="p-4 md:p-6 space-y-6 flex-1">
            {isLoading ? (
              /* Loading Skeleton */
              <div className="space-y-6 animate-pulse">
                <div className="h-44 bg-slate-900/80 rounded-xl border border-slate-800" />
                <div className="h-96 bg-slate-900/80 rounded-xl border border-slate-800" />
              </div>
            ) : !selectedPatientId ? (
              /* Empty State */
              <div className="h-96 flex flex-col items-center justify-center text-slate-500 border border-dashed border-slate-800 rounded-xl">
                <Layers className="w-10 h-10 mb-2 stroke-1" />
                <p className="text-sm">Select a monitored patient from the left rail to initialize digital twin.</p>
              </div>
            ) : (
              <>
                {/* Executive Risk Dial Card */}
                <RiskSummaryCard
                  prediction={twin?.prediction || null}
                  recommendedActions={twin?.recommended_actions || []}
                  thresholds={thresholds ? { moderate: thresholds.moderate, high: thresholds.high } : undefined}
                />

                {/* Signature Risk Horizon Chart with Table/CSV Toggle */}
                <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 shadow-sm">
                  <DataTableToggle
                    rows={riskHorizon?.series || []}
                    cols={horizonColumns}
                    title="24-Hour Synchronized Risk Horizon Trajectory"
                    filename={`nightwatch_risk_horizon_${selectedPatientId}.csv`}
                  >
                    <RiskHorizonChart
                      horizon={riskHorizon}
                      theme={theme}
                      thresholds={thresholds ? { moderate: thresholds.moderate, high: thresholds.high } : undefined}
                    />
                  </DataTableToggle>
                </div>
              </>
            )}
          </div>

          {/* Persistent Clinical Disclaimer Footer */}
          <footer className="p-4 bg-slate-950 border-t border-slate-800/80 text-[11px] text-slate-500 leading-relaxed font-sans">
            <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <p>
                <strong>Clinical Decision Support Disclaimer:</strong> NightWatch is an assistive research prototype.
                Home blood pressure cuff readings constitute ground truth; wearable sensors provide behavioral and autonomic context only.
                NightWatch does not diagnose hypertension, replace validated cuff measurements, prescribe medication, or provide autonomous medical treatment recommendations.
              </p>
              <span className="font-mono text-slate-600 flex-shrink-0">Research Edition v1.1</span>
            </div>
          </footer>
        </main>

        {/* Zone 3: Alert Drawer (Right) */}
        <RightAlertDrawer
          alerts={alerts}
          onAcknowledge={handleAcknowledgeAlert}
          onSnooze={handleSnoozeAlert}
          onFalsePositive={handleFalsePositiveAlert}
          onRequestRecheck={() => api.requestBpRecheck(selectedPatientId)}
          onAddNote={() => {}}
          isOpen={isAlertDrawerOpen}
          onToggle={() => setIsAlertDrawerOpen(!isAlertDrawerOpen)}
        />
      </div>
    </div>
  );
}
