/**
 * NavigationRail: Nocturne Clinical Observatory Left Rail
 * Cohort search, patient list, digital twin readiness indicator, simulation controls, theme toggle.
 */

import React, { useState } from "react";
import {
  Activity,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Moon,
  Play,
  RefreshCw,
  Search,
  Sliders,
  Square,
  Sun,
  User,
  Zap,
} from "lucide-react";
import { PatientSummary, SimulationStatusResponse } from "../types";
import { useAuth } from "../context/AuthContext";

interface NavigationRailProps {
  patients: PatientSummary[];
  selectedPatientId: string;
  onSelectPatient: (patientId: string) => void;
  simulationStatus: SimulationStatusResponse | null;
  onToggleSimulation: () => void;
  onOpenSimulationModal: () => void;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  reducedMotion: boolean;
  onToggleReducedMotion: () => void;
  wsConnected: boolean;
}

export const NavigationRail: React.FC<NavigationRailProps> = ({
  patients,
  selectedPatientId,
  onSelectPatient,
  simulationStatus,
  onToggleSimulation,
  onOpenSimulationModal,
  theme,
  onToggleTheme,
  reducedMotion,
  onToggleReducedMotion,
  wsConnected,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const { user, isAuthenticated, logout, openLoginModal } = useAuth();

  const filteredPatients = patients.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.patient_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.archetype.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <aside
      className={`relative flex flex-col h-screen border-r transition-all duration-200 z-30 ${
        isExpanded ? "w-72" : "w-18"
      } ${
        theme === "dark"
          ? "bg-[#0b0f19] border-[#1e293b] text-slate-100"
          : "bg-white border-slate-200 text-slate-900"
      }`}
      aria-label="Clinical Cohort Navigation"
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between p-4 border-b border-inherit">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 flex-shrink-0">
            <Activity className="w-5 h-5 text-cyan-400" />
          </div>
          {isExpanded && (
            <div className="truncate">
              <h1 className="font-serif text-lg font-bold tracking-tight text-white flex items-center gap-2">
                NightWatch
                <span className="text-[10px] font-sans px-1.5 py-0.5 rounded uppercase font-medium bg-cyan-950 text-cyan-400 border border-cyan-800/50">
                  v1.0
                </span>
              </h1>
              <p className="text-[11px] text-slate-400 truncate">Nocturne Observatory</p>
            </div>
          )}
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
          title={isExpanded ? "Collapse rail" : "Expand rail"}
        >
          {isExpanded ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {/* Stream Readiness & Live Indicator */}
      <div className="px-3 py-2 border-b border-inherit bg-slate-900/40">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                wsConnected ? "bg-emerald-400 shadow-[0_0_8px_#10b981]" : "bg-amber-400"
              }`}
            />
            {isExpanded && (
              <span className="text-[11px] font-medium text-slate-300">
                {wsConnected ? "Twin Live Stream" : "Polling Active (3s)"}
              </span>
            )}
          </div>
          {isExpanded && simulationStatus && (
            <span className="text-[10px] tabular-nums text-slate-400 font-mono">
              Tick: #{simulationStatus.ticks_completed}
            </span>
          )}
        </div>
      </div>

      {/* Patient Search */}
      {isExpanded && (
        <div className="p-3 border-b border-inherit">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search ID, name, archetype..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs pl-8 pr-3 py-1.5 rounded-md bg-slate-900/60 border border-slate-700/60 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
            />
          </div>
        </div>
      )}

      {/* Cohort Patient List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {filteredPatients.map((patient) => {
          const isSelected = patient.patient_id === selectedPatientId;
          const isNoPrediction = patient.latest_probability == null || patient.latest_risk_level == null;
          const riskColor =
            isNoPrediction
              ? "text-slate-400 border-slate-700/60 bg-slate-800/40"
              : patient.latest_risk_level === "High"
              ? "text-rose-400 border-rose-500/40 bg-rose-950/20"
              : patient.latest_risk_level === "Moderate"
              ? "text-amber-400 border-amber-500/40 bg-amber-950/20"
              : "text-emerald-400 border-emerald-500/40 bg-emerald-950/20";

          return (
            <button
              key={patient.patient_id}
              onClick={() => onSelectPatient(patient.patient_id)}
              className={`w-full text-left rounded-lg p-2.5 transition-all text-xs flex items-center justify-between border ${
                isSelected
                  ? "bg-slate-800/90 border-cyan-500/60 shadow-sm"
                  : "bg-transparent border-transparent hover:bg-slate-800/40 hover:border-slate-700/50"
              }`}
              title={`${patient.name} (${patient.patient_id}) - ${patient.archetype}`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-full bg-slate-800 flex items-center justify-center font-semibold text-slate-300 text-[11px] flex-shrink-0 border border-slate-700">
                  {patient.name.charAt(0)}
                </div>
                {isExpanded && (
                  <div className="truncate">
                    <div className="font-medium text-slate-200 truncate flex items-center gap-1.5">
                      {patient.name}
                      {patient.open_alerts_count > 0 && (
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                      )}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono flex items-center gap-1">
                      <span>{patient.patient_id}</span>
                      <span>•</span>
                      <span className="capitalize truncate">{patient.archetype.replace(/_/g, " ")}</span>
                    </div>
                  </div>
                )}
              </div>

              {isExpanded && (
                <div className="flex flex-col items-end flex-shrink-0 ml-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono font-medium ${riskColor}`}>
                    {patient.latest_probability != null
                      ? `${Math.round(patient.latest_probability * 100)}%`
                      : "no prediction"}
                  </span>
                  {patient.data_coverage_pct != null && (
                    <span className="text-[9px] text-slate-400 font-mono mt-0.5">
                      {Math.round(patient.data_coverage_pct)}% cov
                    </span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Simulator Control Dock */}
      <div className="p-3 border-t border-inherit bg-slate-900/60 space-y-2">
        {isExpanded ? (
          <div>
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-[11px] font-medium text-slate-300 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-cyan-400" />
                Telemetry Simulator
              </span>
              <button
                onClick={onOpenSimulationModal}
                className="text-[11px] text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-1"
                title="Scenario Injection"
              >
                <Sliders className="w-3 h-3" />
                Scenarios
              </button>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={onToggleSimulation}
                className={`flex-1 py-1.5 px-3 rounded text-xs font-medium flex items-center justify-center gap-1.5 transition-colors border ${
                  simulationStatus?.is_running
                    ? "bg-rose-950/40 text-rose-300 border-rose-800/60 hover:bg-rose-900/50"
                    : "bg-emerald-950/40 text-emerald-300 border-emerald-800/60 hover:bg-emerald-900/50"
                }`}
              >
                {simulationStatus?.is_running ? (
                  <>
                    <Square className="w-3.5 h-3.5 fill-rose-400" />
                    Pause Sim
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-emerald-400" />
                    Run Stream
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={onToggleSimulation}
            className="w-full p-2 rounded text-slate-400 hover:text-white flex items-center justify-center"
            title={simulationStatus?.is_running ? "Pause simulation" : "Run simulation"}
          >
            {simulationStatus?.is_running ? <Square className="w-4 h-4 text-rose-400" /> : <Play className="w-4 h-4 text-emerald-400" />}
          </button>
        )}

        {/* Global Controls: Theme & Accessibility */}
        {isExpanded && (
          <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
            <button
              onClick={onToggleTheme}
              className="flex items-center gap-1.5 hover:text-slate-200 transition-colors"
            >
              {theme === "dark" ? <Sun className="w-3.5 h-3.5 text-amber-400" /> : <Moon className="w-3.5 h-3.5 text-indigo-400" />}
              <span>{theme === "dark" ? "Light Mode" : "Nocturne Dark"}</span>
            </button>
            <button
              onClick={onToggleReducedMotion}
              className={`px-1.5 py-0.5 rounded border text-[10px] ${
                reducedMotion ? "border-cyan-500 text-cyan-400 bg-cyan-950/30" : "border-slate-700 text-slate-400"
              }`}
              title="Toggle Reduced Motion"
            >
              Reduced Motion
            </button>
          </div>
        )}

        {/* Authenticated Clinician User Info */}
        <div className="pt-2 border-t border-slate-800/80">
          {isAuthenticated && user ? (
            <div className="flex items-center justify-between gap-2 bg-slate-950/60 p-2 rounded-xl border border-slate-800">
              <div className="flex items-center gap-2 overflow-hidden">
                <div className="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-xs font-semibold text-indigo-300 flex-shrink-0">
                  {user.full_name ? user.full_name.charAt(0) : "D"}
                </div>
                {isExpanded && (
                  <div className="truncate">
                    <p className="text-xs font-medium text-slate-200 truncate">{user.full_name}</p>
                    <p className="text-[10px] text-indigo-400 font-mono capitalize">{user.role}</p>
                  </div>
                )}
              </div>
              {isExpanded && (
                <button
                  onClick={logout}
                  className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800/60 rounded-lg transition-colors"
                  title="Sign Out"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ) : (
            <button
              onClick={openLoginModal}
              className="w-full py-1.5 px-3 bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/40 rounded-xl text-xs text-indigo-300 flex items-center justify-center gap-2 transition-all"
            >
              <User className="w-3.5 h-3.5" />
              {isExpanded && <span>Clinician Sign In</span>}
            </button>
          )}
        </div>
      </div>
    </aside>
  );
};
