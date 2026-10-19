/**
 * SleepFingerprintCard: Six-Axis Autonomic & Circadian Radar
 * Plots the six clinical axes vs personal 30-day baseline with written clinical interpretation
 * and honest units (deviation vs personal baseline).
 */

import React, { useMemo } from "react";
import { AlertTriangle, CheckCircle2, Moon } from "lucide-react";
import { SleepFingerprintData } from "../types";
import { EChart } from "./EChart";
import { DataTableToggle } from "./DataTableToggle";

interface SleepFingerprintCardProps {
  data: SleepFingerprintData | null;
  patientId: string;
}

export const SleepFingerprintCard: React.FC<SleepFingerprintCardProps> = ({
  data,
  patientId,
}) => {
  if (!data || !data.axes || data.axes.length === 0) {
    return (
      <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 text-slate-400 text-xs flex items-center gap-2">
        <Moon className="w-4 h-4 text-slate-500" />
        <span>Collecting sleep architecture and autonomic telemetry for 6-axis fingerprint...</span>
      </div>
    );
  }

  const axes = data.axes || [];
  const status = data.status || (data as any).overall_status || "optimal";
  const summary = data.summary || (data as any).written_summary || "";

  // Radar chart option
  const radarOption = useMemo(() => {
    // 6 indicators
    const indicators = axes.map((a) => ({
      name: a.display_name,
      max: 150,
      min: -150,
    }));

    // Baseline is 0% deviation (reference circle)
    const baselineSeries = axes.map(() => 0);
    // Current deviation percentages
    const currentSeries = axes.map((a) => Math.min(140, Math.max(-140, a.deviation_pct)));

    return {
      tooltip: {
        trigger: "item",
        formatter: (params: any) => {
          if (!params || !params.value) return "";
          return `
            <div style="font-weight: 600; margin-bottom: 4px; border-bottom: 1px solid #334155; padding-bottom: 4px;">
              ${params.name}
            </div>
            ${axes
              .map(
                (a, i) => `
              <div style="display: flex; justify-content: space-between; gap: 12px; font-size: 11px; margin-bottom: 2px;">
                <span style="color: #94a3b8;">${a.display_name}:</span>
                <span style="font-weight: 600; color: ${a.deviation_pct < -20 ? "#f43f5e" : a.deviation_pct > 0 ? "#10b981" : "#e2e8f0"};">
                  ${a.deviation_pct > 0 ? `+${a.deviation_pct}` : a.deviation_pct}% vs baseline
                </span>
              </div>
            `
              )
              .join("")}
          `;
        },
      },
      legend: {
        bottom: 0,
        textStyle: { color: "#94a3b8", fontSize: 11 },
        itemGap: 16,
      },
      radar: {
        indicator: indicators,
        shape: "polygon",
        splitNumber: 4,
        axisName: {
          color: "#cbd5e1",
          fontSize: 10,
          fontFamily: "Inter, sans-serif",
        },
        splitLine: {
          lineStyle: {
            color: ["#1e293b", "#334155", "#1e293b", "#334155"],
          },
        },
        splitArea: {
          show: true,
          areaStyle: {
            color: ["rgba(15, 23, 42, 0.4)", "rgba(30, 41, 59, 0.2)"],
          },
        },
        axisLine: {
          lineStyle: { color: "#334155" },
        },
      },
      series: [
        {
          name: "Six-Axis Autonomic Profile",
          type: "radar",
          data: [
            {
              value: baselineSeries,
              name: "Personal 30d Baseline (0% Ref)",
              symbol: "none",
              lineStyle: { color: "#64748b", type: "dashed", width: 1.5 },
              areaStyle: { color: "rgba(100, 116, 139, 0.08)" },
            },
            {
              value: currentSeries,
              name: "Current Telemetry State",
              symbol: "circle",
              symbolSize: 5,
              itemStyle: { color: "#38bdf8" },
              lineStyle: { color: "#38bdf8", width: 2 },
              areaStyle: { color: "rgba(56, 189, 248, 0.2)" },
            },
          ],
        },
      ],
    };
  }, [axes]);

  // Tabular columns for CSV inspection
  const tableCols = [
    { key: "display_name", label: "Circadian Axis" },
    { key: "baseline_value", label: "30-Day Personal Baseline" },
    { key: "current_value", label: "Current Observation" },
    {
      key: "deviation_pct",
      label: "Deviation vs Baseline",
      format: (v: number) => (v > 0 ? `+${v.toFixed(1)}%` : `${v.toFixed(1)}%`),
    },
    {
      key: "status",
      label: "Physiological Status",
      format: (v: string) => (v === "adverse" ? "Acute Deficit" : "Baseline Concordant"),
    },
  ];

  return (
    <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Moon className="w-4 h-4 text-sky-400" />
            Six-Axis Sleep & Autonomic Fingerprint
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Normalized deviations against personal 30-day baseline across autonomic, sleep, and hemodynamic axes.
          </p>
        </div>

        {/* Status Chip */}
        <span
          className={`text-xs px-2.5 py-1 rounded-lg border font-mono font-medium self-start sm:self-auto flex items-center gap-1.5 ${
            status === "acute_deficit"
              ? "border-rose-500/40 bg-rose-950/30 text-rose-300"
              : status === "degraded"
              ? "border-amber-500/40 bg-amber-950/30 text-amber-300"
              : "border-emerald-500/40 bg-emerald-950/30 text-emerald-300"
          }`}
        >
          {status === "acute_deficit" ? (
            <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
          ) : (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          )}
          Status: {(status || "optimal").replace("_", " ").toUpperCase()}
        </span>
      </div>

      {/* Main Radar Chart */}
      <DataTableToggle
        rows={axes}
        cols={tableCols}
        title="Six-Axis Sleep Fingerprint Metrics"
        filename={`nightwatch_sleep_fingerprint_${patientId}.csv`}
      >
        <div className="h-64 sm:h-72 w-full">
          <EChart option={radarOption} style={{ height: "100%", width: "100%" }} />
        </div>
      </DataTableToggle>

      {/* Six Axis Chips Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {axes.map((axis) => (
          <div
            key={axis.axis}
            className={`p-2.5 rounded-lg border text-xs flex flex-col justify-between ${
              axis.status === "adverse"
                ? "bg-rose-950/20 border-rose-800/40"
                : "bg-slate-950/60 border-slate-800/80"
            }`}
          >
            <div className="text-[11px] font-medium text-slate-400 truncate">
              {axis.display_name}
            </div>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="font-mono text-sm font-bold text-slate-200">
                {axis.current_value}
              </span>
              <span
                className={`text-[10px] font-mono font-medium ${
                  axis.deviation_pct < -20
                    ? "text-rose-400"
                    : axis.deviation_pct > 0
                    ? "text-emerald-400"
                    : "text-slate-400"
                }`}
              >
                {axis.deviation_pct > 0 ? `+${axis.deviation_pct}%` : `${axis.deviation_pct}%`}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Written Clinical Interpretation Box */}
      <div className="p-3 rounded-lg bg-sky-950/20 border border-sky-500/30 text-xs text-sky-200 leading-relaxed font-serif">
        <span className="font-sans font-semibold text-sky-400 uppercase text-[10px] tracking-wider block mb-1">
          Automated Circadian Phenotype Assessment
        </span>
        {summary}
      </div>
    </div>
  );
};
