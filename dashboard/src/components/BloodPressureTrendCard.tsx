/**
 * BloodPressureTrendCard: Longitudinal Hemodynamic Trajectory
 * 7/30/90-day toggle, shaded normotensive target band, measured vs predicted differentiation,
 * interactive reading inspection modal, and dynamic clinical summary.
 */

import React, { useState, useMemo } from "react";
import { Activity, Calendar, CheckCircle2, ChevronRight, Info, X } from "lucide-react";
import { DailyReadingItem, PersonalBaseline30d } from "../types";
import { EChart } from "./EChart";
import { DataTableToggle } from "./DataTableToggle";
import { TOKENS } from "../styles/tokens";

interface BloodPressureTrendCardProps {
  series: DailyReadingItem[];
  baseline: PersonalBaseline30d;
  patientId: string;
  selectedDays: number;
  onDaysChange: (days: number) => void;
  isLoading?: boolean;
}

interface SelectedReadingDetail {
  date: string;
  timestamp: string;
  sbp: number;
  dbp: number;
  isPredicted: boolean;
}

export const BloodPressureTrendCard: React.FC<BloodPressureTrendCardProps> = ({
  series,
  baseline,
  patientId,
  selectedDays,
  onDaysChange,
  isLoading = false,
}) => {
  const [selectedReading, setSelectedReading] = useState<SelectedReadingDetail | null>(null);

  // Filter series with BP readings
  const bpData = useMemo(() => {
    return series.filter((d) => d.sbp != null && d.dbp != null);
  }, [series]);

  // Dynamic clinical summary generated from real data
  const summaryText = useMemo(() => {
    if (bpData.length === 0) return "No stored blood pressure cuff measurements available for this window.";
    const total = bpData.length;
    const avgSbp = Math.round(bpData.reduce((acc, d) => acc + (d.sbp || 0), 0) / total);
    const avgDbp = Math.round(bpData.reduce((acc, d) => acc + (d.dbp || 0), 0) / total);
    const elevatedCount = bpData.filter((d) => (d.sbp || 0) >= 140 || (d.dbp || 0) >= 90).length;
    const elevatedPct = Math.round((elevatedCount / total) * 100);

    return `Across ${total} cuff measurements (${selectedDays}d window), average BP is ${avgSbp}/${avgDbp} mmHg. ${elevatedCount} of ${total} readings (${elevatedPct}%) exceeded the stage-2 hypertensive threshold (≥140/90 mmHg).`;
  }, [bpData, selectedDays]);

  // ECharts Option
  const chartOption = useMemo(() => {
    const dates = series.map((d) => d.date);
    const sbpMeasured = series.map((d) => d.sbp ?? null);
    const dbpMeasured = series.map((d) => d.dbp ?? null);

    return {
      grid: {
        top: 36,
        right: 24,
        bottom: 30,
        left: 48,
        containLabel: true,
      },
      legend: {
        top: 0,
        right: 10,
        textStyle: { color: "#94a3b8", fontSize: 11 },
        itemGap: 16,
      },
      tooltip: {
        trigger: "axis",
        formatter: (params: any[]) => {
          if (!params || params.length === 0) return "";
          const idx = params[0].dataIndex;
          const pt = series[idx];
          if (!pt || (pt.sbp == null && pt.dbp == null)) return `<div style="font-size: 11px;">${series[idx]?.date}: No BP Reading</div>`;

          const sbp = pt.sbp ?? "—";
          const dbp = pt.dbp ?? "—";
          const pp = pt.sbp != null && pt.dbp != null ? pt.sbp - pt.dbp : "—";
          return `
            <div style="font-weight: 600; margin-bottom: 4px; border-bottom: 1px solid #334155; padding-bottom: 4px;">
              ${pt.date} • Home BP Cuff
            </div>
            <div style="color: #a855f7; font-weight: 700; font-size: 13px;">
              ${sbp} / ${dbp} mmHg
            </div>
            <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
              Pulse Pressure: ${pp} mmHg
            </div>
          `;
        },
      },
      xAxis: {
        type: "category",
        data: dates,
        axisLine: { lineStyle: { color: "#334155" } },
        axisLabel: { color: "#64748b", fontSize: 10, rotate: selectedDays > 30 ? 45 : 0 },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: 50,
        max: 200,
        interval: 25,
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "#1e293b", type: "dashed" } },
        axisLabel: { color: "#64748b", fontSize: 10, formatter: "{value} mmHg" },
      },
      series: [
        // Normotensive Target Band (markArea covering 90-130 SBP and 60-80 DBP)
        {
          name: "Normotensive Target Zone",
          type: "line",
          markArea: {
            silent: true,
            itemStyle: {
              color: "rgba(16, 185, 129, 0.07)",
            },
            data: [
              [
                { yAxis: 60, name: "Target Zone (60–130 mmHg)" },
                { yAxis: 130 },
              ],
            ],
            label: {
              position: "insideTopRight",
              color: "rgba(16, 185, 129, 0.4)",
              fontSize: 10,
            },
          },
        },
        // Baseline 30d SBP Reference Line
        ...(baseline.sbp
          ? [
              {
                name: "30d Baseline SBP",
                type: "line",
                markLine: {
                  silent: true,
                  symbol: "none",
                  data: [{ yAxis: baseline.sbp, name: `Baseline SBP (${baseline.sbp} mmHg)` }],
                  lineStyle: { color: "#c084fc", type: "dotted", width: 1.5 },
                  label: { formatter: `Baseline SBP: ${baseline.sbp}`, color: "#c084fc", fontSize: 10, position: "insideEndTop" },
                },
              },
            ]
          : []),
        // Measured Systolic BP
        {
          name: "Measured SBP",
          type: "line",
          data: sbpMeasured,
          symbol: "diamond",
          symbolSize: 8,
          itemStyle: { color: "#a855f7" },
          lineStyle: { width: 2, color: "#a855f7" },
          connectNulls: true,
        },
        // Measured Diastolic BP
        {
          name: "Measured DBP",
          type: "line",
          data: dbpMeasured,
          symbol: "circle",
          symbolSize: 6,
          itemStyle: { color: "#06b6d4" },
          lineStyle: { width: 2, color: "#06b6d4" },
          connectNulls: true,
        },
      ],
    };
  }, [series, baseline, selectedDays]);

  // Click event handler for reading details
  const handleChartEvents = useMemo(() => {
    return {
      click: (params: any) => {
        if (!params || params.dataIndex == null) return;
        const pt = series[params.dataIndex];
        if (pt && pt.sbp != null && pt.dbp != null) {
          setSelectedReading({
            date: pt.date,
            timestamp: pt.timestamp,
            sbp: pt.sbp,
            dbp: pt.dbp,
            isPredicted: false,
          });
        }
      },
    };
  }, [series]);

  // Table columns for CSV/Tabular inspection
  const tableColumns = [
    { key: "date", label: "Date" },
    { key: "sbp", label: "Systolic (mmHg)", format: (v: any) => (v != null ? `${v}` : "—") },
    { key: "dbp", label: "Diastolic (mmHg)", format: (v: any) => (v != null ? `${v}` : "—") },
    {
      key: "status",
      label: "Clinical Band",
      format: (_: any, row: DailyReadingItem) => {
        if (row.sbp == null || row.dbp == null) return "Missing";
        if (row.sbp >= 140 || row.dbp >= 90) return "Hypertensive (Stage 2)";
        if (row.sbp >= 130 || row.dbp >= 80) return "Elevated (Stage 1)";
        return "Normal / Controlled";
      },
    },
  ];

  return (
    <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 shadow-sm relative">
      {/* Header with Time Horizon Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Activity className="w-4 h-4 text-purple-400" />
            Longitudinal Blood Pressure Trajectory
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Gold-standard home cuff readings vs target zone and 30-day baseline.
          </p>
        </div>

        {/* 7/30/90 Days Toggle */}
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 self-start sm:self-auto">
          {[7, 30, 90].map((days) => (
            <button
              key={days}
              onClick={() => onDaysChange(days)}
              className={`px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors ${
                selectedDays === days
                  ? "bg-purple-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
              }`}
            >
              {days}d
            </button>
          ))}
        </div>
      </div>

      {/* Main Chart wrapped with DataTableToggle */}
      <DataTableToggle
        rows={series}
        cols={tableColumns}
        title={`Blood Pressure Series (${selectedDays} Days)`}
        filename={`nightwatch_bp_series_${patientId}_${selectedDays}d.csv`}
      >
        <div className="h-64 sm:h-72 w-full">
          <EChart
            option={chartOption}
            onEvents={handleChartEvents}
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      </DataTableToggle>

      {/* One-Line Written Clinical Summary */}
      <div className="mt-3 p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80 flex items-start gap-2 text-xs text-slate-300">
        <Info className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
        <span className="leading-relaxed">{summaryText}</span>
      </div>

      {/* Reading Detail Modal/Popover when clicked */}
      {selectedReading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 max-w-sm w-full shadow-2xl relative">
            <button
              onClick={() => setSelectedReading(null)}
              className="absolute top-3 right-3 text-slate-400 hover:text-slate-200 p-1 rounded-md hover:bg-slate-800"
            >
              <X className="w-4 h-4" />
            </button>

            <h4 className="text-sm font-semibold text-slate-100 flex items-center gap-2 mb-3">
              <Calendar className="w-4 h-4 text-purple-400" />
              Reading Inspection: {selectedReading.date}
            </h4>

            <div className="space-y-3 text-xs">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 flex justify-between items-center">
                <span className="text-slate-400">Blood Pressure:</span>
                <span className="text-base font-bold text-purple-300 font-mono">
                  {selectedReading.sbp} / {selectedReading.dbp} <span className="text-xs font-normal text-slate-400">mmHg</span>
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                  <div className="text-[10px] text-slate-400 uppercase tracking-wider">Pulse Pressure</div>
                  <div className="text-sm font-semibold text-slate-200 mt-0.5">
                    {selectedReading.sbp - selectedReading.dbp} mmHg
                  </div>
                </div>
                <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                  <div className="text-[10px] text-slate-400 uppercase tracking-wider">Mean Arterial (MAP)</div>
                  <div className="text-sm font-semibold text-slate-200 mt-0.5">
                    {Math.round((selectedReading.sbp + 2 * selectedReading.dbp) / 3)} mmHg
                  </div>
                </div>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/50">
                <div className="text-[10px] text-slate-400 uppercase tracking-wider">Classification</div>
                <div className={`text-xs font-medium mt-0.5 ${
                  selectedReading.sbp >= 140 || selectedReading.dbp >= 90
                    ? "text-rose-400"
                    : selectedReading.sbp >= 130 || selectedReading.dbp >= 80
                    ? "text-amber-400"
                    : "text-emerald-400"
                }`}>
                  {selectedReading.sbp >= 140 || selectedReading.dbp >= 90
                    ? "Stage 2 Hypertensive (Modeled episode threshold)"
                    : selectedReading.sbp >= 130 || selectedReading.dbp >= 80
                    ? "Stage 1 Elevated"
                    : "Normal / Controlled"}
                </div>
              </div>

              <div className="text-[11px] text-slate-500 italic">
                Source: Validated home oscillometric cuff. Recorded in Asia/Kolkata timezone.
              </div>
            </div>

            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setSelectedReading(null)}
                className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium"
              >
                Close Inspection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
