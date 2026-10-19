/**
 * CircadianWavesCard: Stacked Sleep / Autonomic / Hemodynamic Biomarkers
 * Synchronized via echarts.connect with personal 30-day baseline reference bands
 * and dynamically generated clinical summaries.
 */

import React, { useMemo } from "react";
import { Heart, Moon, Zap } from "lucide-react";
import { DailyReadingItem, PersonalBaseline30d } from "../types";
import { EChart } from "./EChart";
import { DataTableToggle } from "./DataTableToggle";

interface CircadianWavesCardProps {
  series: DailyReadingItem[];
  baseline: PersonalBaseline30d;
  patientId: string;
}

export const CircadianWavesCard: React.FC<CircadianWavesCardProps> = ({
  series,
  baseline,
  patientId,
}) => {
  const dates = useMemo(() => series.map((d) => d.date), [series]);

  // Derived metrics and dynamic written summaries
  const { sleepSummary, hrvSummary, hrSummary } = useMemo(() => {
    const validSleep = series.filter((d) => d.sleep_duration != null);
    const validHrv = series.filter((d) => d.hrv_rmssd != null);
    const validHr = series.filter((d) => d.resting_hr != null);

    const avgSleep = validSleep.length
      ? (validSleep.reduce((acc, d) => acc + (d.sleep_duration || 0), 0) / validSleep.length).toFixed(1)
      : null;
    const baseSleep = baseline.sleep_duration ? baseline.sleep_duration.toFixed(1) : null;
    const sleepDiff = avgSleep && baseSleep ? (parseFloat(avgSleep) - parseFloat(baseSleep)).toFixed(1) : null;

    const sleepText = avgSleep
      ? `Mean sleep duration is ${avgSleep}h${baseSleep ? ` vs 30d personal baseline ${baseSleep}h (${Number(sleepDiff) >= 0 ? `+${sleepDiff}` : sleepDiff}h)` : ""}.`
      : "Insufficient sleep architecture telemetry.";

    const avgHrv = validHrv.length
      ? Math.round(validHrv.reduce((acc, d) => acc + (d.hrv_rmssd || 0), 0) / validHrv.length)
      : null;
    const baseHrv = baseline.hrv_rmssd ? Math.round(baseline.hrv_rmssd) : null;
    const hrvDiff = avgHrv && baseHrv ? avgHrv - baseHrv : null;

    const hrvText = avgHrv
      ? `Autonomic tone (HRV RMSSD) averaged ${avgHrv} ms${baseHrv ? ` vs 30d personal baseline ${baseHrv} ms (${hrvDiff && hrvDiff >= 0 ? `+${hrvDiff}` : hrvDiff} ms)` : ""}.`
      : "No resting HRV telemetry available.";

    const avgHr = validHr.length
      ? Math.round(validHr.reduce((acc, d) => acc + (d.resting_hr || 0), 0) / validHr.length)
      : null;
    const baseHr = baseline.resting_hr ? Math.round(baseline.resting_hr) : null;

    const hrText = avgHr
      ? `Mean nocturnal resting HR is ${avgHr} bpm${baseHr ? ` vs 30d baseline ${baseHr} bpm` : ""}.`
      : "No resting heart rate data recorded.";

    return { sleepSummary: sleepText, hrvSummary: hrvText, hrSummary: hrText };
  }, [series, baseline]);

  // Common shared grid and axis styling
  const commonXAxis = {
    type: "category",
    data: dates,
    axisLine: { lineStyle: { color: "#334155" } },
    axisLabel: { color: "#64748b", fontSize: 10 },
    splitLine: { show: false },
  };

  // 1. Sleep Chart Option
  const sleepOption = useMemo(() => {
    return {
      grid: { top: 25, right: 20, bottom: 25, left: 45, containLabel: true },
      tooltip: {
        trigger: "axis",
        formatter: (params: any[]) => {
          if (!params || !params[0]) return "";
          const idx = params[0].dataIndex;
          const pt = series[idx];
          return `
            <div style="font-weight: 600; margin-bottom: 2px;">${pt.date} • Sleep Analysis</div>
            <div style="color: #38bdf8;">Duration: ${pt.sleep_duration ? `${pt.sleep_duration.toFixed(1)} hrs` : "—"}</div>
            <div style="color: #818cf8;">Efficiency: ${pt.sleep_efficiency ? `${Math.round(pt.sleep_efficiency * 100)}%` : "—"}</div>
          `;
        },
      },
      xAxis: commonXAxis,
      yAxis: {
        type: "value",
        min: 0,
        max: 12,
        interval: 3,
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "#1e293b", type: "dashed" } },
        axisLabel: { color: "#64748b", fontSize: 9, formatter: "{value}h" },
      },
      series: [
        ...(baseline.sleep_duration
          ? [
              {
                name: "30d Baseline Sleep",
                type: "line",
                markLine: {
                  silent: true,
                  symbol: "none",
                  data: [{ yAxis: baseline.sleep_duration }],
                  lineStyle: { color: "#38bdf8", type: "dotted", width: 1.5 },
                  label: { formatter: `Baseline: ${baseline.sleep_duration.toFixed(1)}h`, color: "#38bdf8", fontSize: 9, position: "insideEndTop" },
                },
              },
            ]
          : []),
        {
          name: "Sleep Duration",
          type: "bar",
          data: series.map((d) => d.sleep_duration ?? null),
          itemStyle: {
            color: "#38bdf8",
            borderRadius: [3, 3, 0, 0],
          },
          barMaxWidth: 16,
        },
      ],
    };
  }, [series, baseline, commonXAxis]);

  // 2. HRV Chart Option
  const hrvOption = useMemo(() => {
    return {
      grid: { top: 25, right: 20, bottom: 25, left: 45, containLabel: true },
      tooltip: {
        trigger: "axis",
        formatter: (params: any[]) => {
          if (!params || !params[0]) return "";
          const idx = params[0].dataIndex;
          const pt = series[idx];
          return `
            <div style="font-weight: 600; margin-bottom: 2px;">${pt.date} • Autonomic Tone</div>
            <div style="color: #06b6d4;">HRV RMSSD: ${pt.hrv_rmssd ? `${pt.hrv_rmssd.toFixed(1)} ms` : "—"}</div>
          `;
        },
      },
      xAxis: commonXAxis,
      yAxis: {
        type: "value",
        min: 0,
        max: 80,
        interval: 20,
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "#1e293b", type: "dashed" } },
        axisLabel: { color: "#64748b", fontSize: 9, formatter: "{value} ms" },
      },
      series: [
        ...(baseline.hrv_rmssd
          ? [
              {
                name: "30d Baseline HRV",
                type: "line",
                markLine: {
                  silent: true,
                  symbol: "none",
                  data: [{ yAxis: baseline.hrv_rmssd }],
                  lineStyle: { color: "#06b6d4", type: "dotted", width: 1.5 },
                  label: { formatter: `Baseline: ${baseline.hrv_rmssd.toFixed(0)} ms`, color: "#06b6d4", fontSize: 9, position: "insideEndTop" },
                },
              },
            ]
          : []),
        {
          name: "HRV (RMSSD)",
          type: "line",
          data: series.map((d) => d.hrv_rmssd ?? null),
          itemStyle: { color: "#06b6d4" },
          lineStyle: { color: "#06b6d4", width: 2 },
          areaStyle: {
            color: "rgba(6, 182, 212, 0.12)",
          },
          connectNulls: true,
          symbolSize: 4,
        },
      ],
    };
  }, [series, baseline, commonXAxis]);

  // 3. Resting HR Chart Option
  const hrOption = useMemo(() => {
    return {
      grid: { top: 25, right: 20, bottom: 25, left: 45, containLabel: true },
      tooltip: {
        trigger: "axis",
        formatter: (params: any[]) => {
          if (!params || !params[0]) return "";
          const idx = params[0].dataIndex;
          const pt = series[idx];
          return `
            <div style="font-weight: 600; margin-bottom: 2px;">${pt.date} • Resting Heart Rate</div>
            <div style="color: #f43f5e;">Resting HR: ${pt.resting_hr ? `${pt.resting_hr} bpm` : "—"}</div>
          `;
        },
      },
      xAxis: commonXAxis,
      yAxis: {
        type: "value",
        min: 40,
        max: 110,
        interval: 20,
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "#1e293b", type: "dashed" } },
        axisLabel: { color: "#64748b", fontSize: 9, formatter: "{value} bpm" },
      },
      series: [
        ...(baseline.resting_hr
          ? [
              {
                name: "30d Baseline HR",
                type: "line",
                markLine: {
                  silent: true,
                  symbol: "none",
                  data: [{ yAxis: baseline.resting_hr }],
                  lineStyle: { color: "#f43f5e", type: "dotted", width: 1.5 },
                  label: { formatter: `Baseline: ${baseline.resting_hr} bpm`, color: "#f43f5e", fontSize: 9, position: "insideEndTop" },
                },
              },
            ]
          : []),
        {
          name: "Resting HR",
          type: "line",
          data: series.map((d) => d.resting_hr ?? null),
          itemStyle: { color: "#f43f5e" },
          lineStyle: { color: "#f43f5e", width: 2 },
          connectNulls: true,
          symbolSize: 4,
        },
      ],
    };
  }, [series, baseline, commonXAxis]);

  // Data table columns
  const tableCols = [
    { key: "date", label: "Date" },
    { key: "sleep_duration", label: "Sleep (h)", format: (v: any) => (v != null ? `${v.toFixed(1)}` : "—") },
    { key: "sleep_efficiency", label: "Efficiency", format: (v: any) => (v != null ? `${Math.round(v * 100)}%` : "—") },
    { key: "hrv_rmssd", label: "HRV (ms)", format: (v: any) => (v != null ? `${v.toFixed(1)}` : "—") },
    { key: "resting_hr", label: "Resting HR (bpm)", format: (v: any) => (v != null ? `${v}` : "—") },
    { key: "steps", label: "Steps", format: (v: any) => (v != null ? `${v.toLocaleString()}` : "—") },
  ];

  return (
    <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 shadow-sm space-y-5">
      <div>
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <Moon className="w-4 h-4 text-sky-400" />
          Circadian Autonomic Waves (Linked Scrubbing)
        </h3>
        <p className="text-xs text-slate-400 mt-0.5">
          Synchronized nocturnal sleep architecture, vagal tone (HRV), and resting heart rate trajectories.
        </p>
      </div>

      <DataTableToggle
        rows={series}
        cols={tableCols}
        title="Circadian Biomarker Waves"
        filename={`nightwatch_circadian_waves_${patientId}.csv`}
      >
        <div className="space-y-4">
          {/* Subplot 1: Sleep Architecture */}
          <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold text-sky-400 flex items-center gap-1.5">
                <Moon className="w-3.5 h-3.5" /> Sleep Duration
              </span>
              <span className="text-[11px] text-slate-400">{sleepSummary}</span>
            </div>
            <div className="h-32 w-full">
              <EChart option={sleepOption} group="circadianGroup" style={{ height: "100%", width: "100%", minHeight: "128px" }} />
            </div>
          </div>

          {/* Subplot 2: HRV RMSSD */}
          <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold text-cyan-400 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5" /> Parasympathetic Tone (HRV RMSSD)
              </span>
              <span className="text-[11px] text-slate-400">{hrvSummary}</span>
            </div>
            <div className="h-32 w-full">
              <EChart option={hrvOption} group="circadianGroup" style={{ height: "100%", width: "100%", minHeight: "128px" }} />
            </div>
          </div>

          {/* Subplot 3: Resting Heart Rate */}
          <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold text-rose-400 flex items-center gap-1.5">
                <Heart className="w-3.5 h-3.5" /> Nocturnal Resting Heart Rate
              </span>
              <span className="text-[11px] text-slate-400">{hrSummary}</span>
            </div>
            <div className="h-32 w-full">
              <EChart option={hrOption} group="circadianGroup" style={{ height: "100%", width: "100%", minHeight: "128px" }} />
            </div>
          </div>
        </div>
      </DataTableToggle>
    </div>
  );
};
