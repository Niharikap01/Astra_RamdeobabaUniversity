/**
 * TwinSummaryCard: Digital Twin Physiological State Comparison
 * Compares current physiological values against the patient's personal 30-day baseline
 * with explicit written delta statements and clinical status chips.
 */

import React from "react";
import { Activity, Clock, Heart, Moon, Pill, Shield, TrendingDown, TrendingUp, Zap } from "lucide-react";
import { DynamicState, PersonalBaseline30d, StaticProfile } from "../types";

interface TwinSummaryCardProps {
  dynamicState?: DynamicState | null;
  baseline: PersonalBaseline30d;
  patientId: string;
}

export const TwinSummaryCard: React.FC<TwinSummaryCardProps> = ({
  dynamicState,
  baseline,
}) => {
  if (!dynamicState) {
    return (
      <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 text-slate-400 text-xs">
        No active physiological state available for twin comparison.
      </div>
    );
  }

  // Format deltas
  const formatDelta = (current: number | null | undefined, base: number | null | undefined, unit: string, higherIsBad = true) => {
    if (current == null || base == null) return { text: "No baseline available", status: "neutral" as const };
    const diff = current - base;
    const absDiff = Math.abs(diff);
    if (absDiff < 0.05) return { text: "Matches 30-day baseline", status: "neutral" as const };

    const isWorse = higherIsBad ? diff > 0 : diff < 0;
    const sign = diff > 0 ? "+" : "-";
    const status = isWorse ? ("warning" as const) : ("favorable" as const);
    return {
      text: `${sign}${absDiff.toFixed(1)} ${unit} vs 30d baseline (${base.toFixed(1)} ${unit})`,
      status,
    };
  };

  const sbpDelta = formatDelta(dynamicState.latest_sbp, baseline.sbp, "mmHg", true);
  const dbpDelta = formatDelta(dynamicState.latest_dbp, baseline.dbp, "mmHg", true);
  const sleepDelta = formatDelta(dynamicState.sleep_last_night, baseline.sleep_duration, "h", false);
  const hrvDelta = formatDelta(dynamicState.hrv_last_night, baseline.hrv_rmssd, "ms", false);
  const rhrDelta = formatDelta(dynamicState.resting_hr_last_night, baseline.resting_hr, "bpm", true);
  const stepsDelta = formatDelta(dynamicState.steps_yesterday, baseline.steps, "steps", false);

  const getStatusBadge = (status: "favorable" | "warning" | "neutral") => {
    if (status === "warning") {
      return (
        <span className="text-[10px] px-1.5 py-0.5 rounded border border-rose-500/40 bg-rose-950/30 text-rose-300 font-medium">
          Elevated / Deficit
        </span>
      );
    }
    if (status === "favorable") {
      return (
        <span className="text-[10px] px-1.5 py-0.5 rounded border border-emerald-500/40 bg-emerald-950/30 text-emerald-300 font-medium">
          Favorable / Protected
        </span>
      );
    }
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded border border-slate-700 bg-slate-800/40 text-slate-400 font-medium">
        Baseline Concordant
      </span>
    );
  };

  return (
    <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-400" />
            Digital Twin Hemodynamic & Autonomic Baseline Delta
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time biometric comparison against individual 30-day running physiological baselines.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {/* SBP Card */}
        <div className="p-3.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-purple-400" /> Home Systolic BP
              </span>
              {getStatusBadge(sbpDelta.status)}
            </div>
            <div className="text-xl font-bold font-mono text-slate-100 mt-2">
              {dynamicState.latest_sbp != null ? `${Math.round(dynamicState.latest_sbp)}` : "—"}
              <span className="text-xs font-normal text-slate-400 ml-1">mmHg</span>
            </div>
          </div>
          <div className="text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-800/60 leading-tight">
            {sbpDelta.text}
          </div>
        </div>

        {/* DBP Card */}
        <div className="p-3.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-purple-400" /> Home Diastolic BP
              </span>
              {getStatusBadge(dbpDelta.status)}
            </div>
            <div className="text-xl font-bold font-mono text-slate-100 mt-2">
              {dynamicState.latest_dbp != null ? `${Math.round(dynamicState.latest_dbp)}` : "—"}
              <span className="text-xs font-normal text-slate-400 ml-1">mmHg</span>
            </div>
          </div>
          <div className="text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-800/60 leading-tight">
            {dbpDelta.text}
          </div>
        </div>

        {/* Sleep Duration Card */}
        <div className="p-3.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <Moon className="w-3.5 h-3.5 text-sky-400" /> Sleep Last Night
              </span>
              {getStatusBadge(sleepDelta.status)}
            </div>
            <div className="text-xl font-bold font-mono text-slate-100 mt-2">
              {dynamicState.sleep_last_night != null ? `${dynamicState.sleep_last_night.toFixed(1)}` : "—"}
              <span className="text-xs font-normal text-slate-400 ml-1">hrs</span>
            </div>
          </div>
          <div className="text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-800/60 leading-tight">
            {sleepDelta.text}
          </div>
        </div>

        {/* HRV RMSSD Card */}
        <div className="p-3.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-cyan-400" /> Autonomic HRV (RMSSD)
              </span>
              {getStatusBadge(hrvDelta.status)}
            </div>
            <div className="text-xl font-bold font-mono text-slate-100 mt-2">
              {dynamicState.hrv_last_night != null ? `${Math.round(dynamicState.hrv_last_night)}` : "—"}
              <span className="text-xs font-normal text-slate-400 ml-1">ms</span>
            </div>
          </div>
          <div className="text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-800/60 leading-tight">
            {hrvDelta.text}
          </div>
        </div>

        {/* Resting HR Card */}
        <div className="p-3.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <Heart className="w-3.5 h-3.5 text-rose-400" /> Resting Heart Rate
              </span>
              {getStatusBadge(rhrDelta.status)}
            </div>
            <div className="text-xl font-bold font-mono text-slate-100 mt-2">
              {dynamicState.resting_hr_last_night != null ? `${Math.round(dynamicState.resting_hr_last_night)}` : "—"}
              <span className="text-xs font-normal text-slate-400 ml-1">bpm</span>
            </div>
          </div>
          <div className="text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-800/60 leading-tight">
            {rhrDelta.text}
          </div>
        </div>

        {/* Medication Adherence Card */}
        <div className="p-3.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                <Pill className="w-3.5 h-3.5 text-pink-400" /> Medication Adherence
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded border border-pink-500/40 bg-pink-950/30 text-pink-300 font-medium">
                {baseline.medication_adherence != null && baseline.medication_adherence >= 0.8 ? "Adherent" : "Sub-optimal"}
              </span>
            </div>
            <div className="text-xl font-bold font-mono text-slate-100 mt-2">
              {baseline.medication_adherence != null ? `${Math.round(baseline.medication_adherence * 100)}%` : "—"}
              <span className="text-xs font-normal text-slate-400 ml-1">30d rate</span>
            </div>
          </div>
          <div className="text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-800/60 leading-tight">
            Last dose: {dynamicState.medication_taken_last_night ? "Recorded taken" : "Missed or unrecorded"}
          </div>
        </div>
      </div>
    </div>
  );
};
