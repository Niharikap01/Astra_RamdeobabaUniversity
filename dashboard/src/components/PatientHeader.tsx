/**
 * PatientHeader: Nocturne Clinical Observatory Patient Context Bar
 * Identity, archetype, 30d baseline parameters, Twin readiness status, and quick clinical actions.
 */

import React from "react";
import {
  Activity,
  Clock,
  FileText,
  Heart,
  Moon,
  RotateCcw,
  Sparkles,
  Table,
} from "lucide-react";
import { DigitalTwinResponse, PatientProfileDetail } from "../types";
import { useAuth } from "../context/AuthContext";

interface PatientHeaderProps {
  patient: PatientProfileDetail | null;
  twin: DigitalTwinResponse | null;
  onRequestRecheck: () => void;
  onAddNote: () => void;
  onOpenWhatIf: () => void;
  onToggleTableView: () => void;
  isTableView: boolean;
}

export const PatientHeader: React.FC<PatientHeaderProps> = ({
  patient,
  twin,
  onRequestRecheck,
  onAddNote,
  onOpenWhatIf,
  onToggleTableView,
  isTableView,
}) => {
  const { user } = useAuth();
  const isViewer = user?.role === "viewer";
  if (!patient) return null;

  const archetypeDisplay = patient.archetype.replace(/_/g, " ").toUpperCase();
  const bmiCategory =
    patient.bmi < 18.5
      ? "Underweight"
      : patient.bmi < 25
      ? "Normal weight"
      : patient.bmi < 30
      ? "Overweight"
      : "Class I/II Obesity";

  return (
    <header className="bg-slate-900/90 border-b border-slate-800 p-4 md:px-6 md:py-4">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        {/* Left Identity & Demographics */}
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-900/60 to-slate-800 border border-indigo-500/30 flex items-center justify-center text-lg font-serif font-bold text-slate-100 flex-shrink-0 shadow-sm">
            {patient.name.charAt(0)}
          </div>
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-xl font-serif font-semibold text-white tracking-tight">
                {patient.name}
              </h2>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                {patient.patient_id}
              </span>
              <span className="text-xs px-2.5 py-0.5 rounded-full font-medium tracking-wide bg-indigo-950/70 text-indigo-300 border border-indigo-700/50">
                {archetypeDisplay}
              </span>
              <div className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-medium text-[11px]">Digital Twin Active</span>
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs text-slate-400 mt-1.5 flex-wrap">
              <span>{patient.age} yrs • {patient.sex === "M" ? "Male" : "Female"}</span>
              <span>•</span>
              <span className="tabular-nums">
                BMI {patient.bmi.toFixed(1)} kg/m² ({bmiCategory})
              </span>
              <span>•</span>
              <span className="tabular-nums">{patient.height_cm.toFixed(0)} cm / {patient.weight_kg.toFixed(1)} kg</span>
              {twin && (
                <>
                  <span>•</span>
                  <span className="flex items-center gap-1 text-slate-400 font-mono text-[11px]">
                    <Clock className="w-3 h-3 text-cyan-400" />
                    Synced {new Date(twin.as_of).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap self-start lg:self-auto">
          <button
            onClick={onToggleTableView}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition-colors ${
              isTableView
                ? "bg-cyan-950 text-cyan-300 border-cyan-700"
                : "bg-slate-800/60 text-slate-300 border-slate-700 hover:bg-slate-800"
            }`}
            title="Toggle Tabular Data Alternative"
          >
            <Table className="w-3.5 h-3.5" />
            <span>{isTableView ? "Observatory View" : "Data Tables"}</span>
          </button>

          <button
            onClick={onOpenWhatIf}
            className="px-3 py-1.5 rounded-lg text-xs font-medium border bg-indigo-950/50 text-indigo-300 border-indigo-700/60 hover:bg-indigo-900/60 flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Simulate What-If</span>
          </button>

          {!isViewer && (
            <>
              <button
                onClick={onRequestRecheck}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700 flex items-center gap-1.5 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />
                <span>Order BP Recheck</span>
              </button>

              <button
                onClick={onAddNote}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700 flex items-center gap-1.5 transition-colors"
              >
                <FileText className="w-3.5 h-3.5 text-slate-400" />
                <span>Add Note</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Baseline Physiology Sub-Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3.5 pt-3 border-t border-slate-800/80">
        <div className="bg-slate-950/40 rounded-lg p-2 border border-slate-800/60">
          <div className="text-[10px] uppercase font-semibold text-slate-400 flex items-center gap-1">
            <Heart className="w-3 h-3 text-purple-400" />
            30d Baseline BP
          </div>
          <div className="text-sm font-semibold text-slate-200 tabular-nums mt-0.5">
            {patient.baseline_sbp.toFixed(0)}/{patient.baseline_dbp.toFixed(0)}{" "}
            <span className="text-[10px] text-slate-400 font-normal">mmHg</span>
          </div>
        </div>

        <div className="bg-slate-950/40 rounded-lg p-2 border border-slate-800/60">
          <div className="text-[10px] uppercase font-semibold text-slate-400 flex items-center gap-1">
            <Moon className="w-3 h-3 text-blue-400" />
            30d Baseline Sleep
          </div>
          <div className="text-sm font-semibold text-slate-200 tabular-nums mt-0.5">
            {patient.baseline_sleep_hours.toFixed(1)}{" "}
            <span className="text-[10px] text-slate-400 font-normal">hours/night</span>
          </div>
        </div>

        <div className="bg-slate-950/40 rounded-lg p-2 border border-slate-800/60">
          <div className="text-[10px] uppercase font-semibold text-slate-400 flex items-center gap-1">
            <Activity className="w-3 h-3 text-cyan-400" />
            30d Baseline HRV
          </div>
          <div className="text-sm font-semibold text-slate-200 tabular-nums mt-0.5">
            {patient.baseline_hrv_rmssd.toFixed(1)}{" "}
            <span className="text-[10px] text-slate-400 font-normal">ms (RMSSD)</span>
          </div>
        </div>

        <div className="bg-slate-950/40 rounded-lg p-2 border border-slate-800/60">
          <div className="text-[10px] uppercase font-semibold text-slate-400 flex items-center gap-1">
            <Heart className="w-3 h-3 text-rose-400" />
            30d Resting HR
          </div>
          <div className="text-sm font-semibold text-slate-200 tabular-nums mt-0.5">
            {patient.baseline_resting_hr.toFixed(0)}{" "}
            <span className="text-[10px] text-slate-400 font-normal">bpm</span>
          </div>
        </div>
      </div>
    </header>
  );
};
