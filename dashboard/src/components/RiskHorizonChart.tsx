/**
 * RiskHorizonChart: Nocturne Clinical Observatory Signature Visualization
 * 24-Hour continuous trajectory (Observed 12h + Predicted 12h) with shaded confidence bands,
 * sleep architecture backdrop, BP cuff reading diamonds, medication capsules, and dynamic NOW line.
 */

import React, { useMemo } from "react";
import { EChart } from "./EChart";
import { AlertCircle, Clock, Sparkles } from "lucide-react";
import { RiskHorizonResponse } from "../types";
import { TOKENS } from "../styles/tokens";

interface RiskHorizonChartProps {
  horizon: RiskHorizonResponse | null;
  theme: "dark" | "light";
  whatIfSimulatedRisk?: number | null;
  onSelectTimePoint?: (offset: number) => void;
  thresholds?: { moderate: number; high: number };
}

export const RiskHorizonChart: React.FC<RiskHorizonChartProps> = ({
  horizon,
  theme,
  whatIfSimulatedRisk,
  onSelectTimePoint,
  thresholds,
}) => {
  if (!horizon || !horizon.series || horizon.series.length === 0) {
    return (
      <div className="h-80 flex flex-col items-center justify-center bg-slate-900/50 rounded-xl border border-slate-800 text-slate-400">
        <Clock className="w-8 h-8 text-slate-500 mb-2 animate-pulse" />
        <p className="text-sm">Synthesizing 24-hour Risk Horizon trajectory...</p>
      </div>
    );
  }

  const series = horizon.series;
  const isDark = theme === "dark";
  const palette = isDark ? TOKENS.colors.dark : TOKENS.colors.light;

  // Confidence Interval Band: only if valid interval can be derived
  const hasValidConfidence = series.some(
    (p) => (p.confidence_lower != null && p.confidence_upper != null) ||
           (p.uncertainty_lower != null && p.uncertainty_upper != null)
  );

  const option = useMemo(() => {
    const nowIdx = series.findIndex((p) => p.is_predicted);
    const validNowIdx = nowIdx >= 0 ? nowIdx : series.length - 1;

    const xLabels = series.map((p) => {
      const d = new Date(p.timestamp);
      const dateStr = d.toLocaleDateString([], { month: "short", day: "numeric" });
      if (p.is_predicted) return `${dateStr}\n[+24h Pred]`;
      if (p.hour_offset === 0) return `${dateStr}\n[Today]`;
      return dateStr;
    });

    // Series arrays: Past stored model estimates and future prediction
    const observedData = series.map((p, idx) => (idx <= (validNowIdx > 0 ? validNowIdx - 1 : validNowIdx) ? p.risk_pct : null));
    const predictedData = series.map((p, idx) => (idx >= Math.max(0, validNowIdx - 1) ? p.risk_pct : null));
    const confLower = hasValidConfidence
      ? series.map((p, idx) => (idx >= Math.max(0, validNowIdx - 1) ? (p.confidence_lower ?? p.uncertainty_lower) : null))
      : [];
    const confRange = hasValidConfidence
      ? series.map((p, idx) => {
          if (idx < Math.max(0, validNowIdx - 1)) return null;
          const low = p.confidence_lower ?? p.uncertainty_lower;
          const high = p.confidence_upper ?? p.uncertainty_upper;
          return low != null && high != null ? Math.max(0, high - low) : null;
        })
      : [];

    // Ghosted What-If curve if active
    const whatIfCurve = whatIfSimulatedRisk != null
      ? series.map((p, idx) => {
          if (idx < validNowIdx) return null;
          const factor = (idx - validNowIdx) / (series.length - validNowIdx);
          return Math.round(p.risk_pct + (whatIfSimulatedRisk - p.risk_pct) * factor);
        })
      : null;

    // BP cuff readings (diamond markers)
    const bpScatterData = series
      .map((p, idx) => {
        if (p.has_bp_reading && p.measured_sbp) {
          return {
            coord: [idx, p.risk_pct],
            value: `${p.measured_sbp}/${p.measured_dbp} mmHg`,
            sbp: p.measured_sbp,
            dbp: p.measured_dbp,
          };
        }
        return null;
      })
      .filter(Boolean);

    // Medication capsules
    const medScatterData = series
      .map((p, idx) => {
        if (p.has_medication_event) {
          return {
            coord: [idx, p.risk_pct + 4],
            name: p.medication_name || "Antihypertensive Dose",
          };
        }
        return null;
      })
      .filter(Boolean);

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: {
          type: "cross",
          lineStyle: {
            color: palette.borderActive,
            width: 1,
            type: "dashed",
          },
        },
        backgroundColor: isDark ? "rgba(17, 24, 39, 0.95)" : "rgba(255, 255, 255, 0.95)",
        borderColor: palette.borderActive,
        textStyle: {
          color: palette.textPrimary,
          fontSize: 12,
          fontFamily: TOKENS.typography.fontSans,
        },
        formatter: (params: any[]) => {
          if (!params || params.length === 0) return "";
          const idx = params[0].dataIndex;
          const pt = series[idx];
          if (!pt) return "";

          const time = new Date(pt.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          });
          const status = pt.is_predicted ? "Predicted Forecast" : "Model estimate (past)";
          const riskBand = pt.risk_pct >= 65 ? "High Risk" : pt.risk_pct >= 35 ? "Moderate Risk" : "Low Risk";
          const riskColor = pt.risk_pct >= 65 ? palette.riskHigh : pt.risk_pct >= 35 ? palette.riskModerate : palette.riskLow;

          let html = `
            <div style="font-weight: 600; margin-bottom: 4px; border-bottom: 1px solid ${palette.borderSubtle}; padding-bottom: 4px;">
              ${time} • <span style="color: ${pt.is_predicted ? palette.predictedBand : palette.observedBand};">${status}</span>
            </div>
            <div style="margin-bottom: 3px;">
              24h Risk Forecast: <span style="font-weight: 700; color: ${riskColor}; font-size: 14px;">${pt.risk_pct}%</span>
              <span style="font-size: 11px; color: ${palette.textMuted};">(${riskBand})</span>
            </div>
          `;

          if (pt.is_predicted) {
            html += `
              <div style="font-size: 11px; color: ${palette.textSecondary}; margin-bottom: 4px;">
                95% Confidence Band: ${pt.confidence_lower}% – ${pt.confidence_upper}%
              </div>
            `;
          }

          if (pt.is_sleep_window) {
            html += `
              <div style="font-size: 11px; color: ${palette.circadianSleep}; display: flex; align-items: center; gap: 4px;">
                <span>🌙 Sleep Stage:</span> <strong>${(pt.sleep_stage || "Light").toUpperCase()}</strong>
              </div>
            `;
          }

          if (pt.has_bp_reading && pt.measured_sbp) {
            html += `
              <div style="font-size: 11px; color: ${palette.circadianBp}; margin-top: 3px;">
                ◆ Home Cuff Reading: <strong>${pt.measured_sbp}/${pt.measured_dbp} mmHg</strong>
              </div>
            `;
          }

          if (pt.has_medication_event) {
            html += `
              <div style="font-size: 11px; color: ${palette.circadianMed}; margin-top: 3px;">
                💊 Medication Logged: <strong>${pt.medication_name || "Daily Regimen"}</strong>
              </div>
            `;
          }

          return html;
        },
      },
      grid: {
        left: "3.5%",
        right: "3%",
        top: "14%",
        bottom: "16%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: xLabels,
        axisLine: { lineStyle: { color: palette.borderSubtle } },
        axisLabel: {
          color: palette.textMuted,
          fontSize: 10,
          interval: 2,
        },
        splitLine: {
          show: true,
          lineStyle: { color: isDark ? "rgba(30, 41, 59, 0.4)" : "rgba(226, 232, 240, 0.6)", type: "dashed" },
        },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        interval: 20,
        name: "Episode Probability (%)",
        nameTextStyle: {
          color: palette.textMuted,
          fontSize: 11,
          padding: [0, 0, 6, 0],
        },
        axisLabel: {
          color: palette.textMuted,
          fontSize: 10,
          formatter: "{value}%",
        },
        splitLine: {
          lineStyle: {
            color: isDark ? "rgba(30, 41, 59, 0.4)" : "rgba(226, 232, 240, 0.6)",
          },
        },
      },
      series: [
        // 1 & 2. Shaded Confidence Interval Band (only if valid interval derived)
        ...(hasValidConfidence
          ? [
              {
                name: "Confidence Lower",
                type: "line",
                data: confLower,
                lineStyle: { opacity: 0 },
                stack: "confidence-band",
                symbol: "none",
              },
              {
                name: "95% Confidence Band",
                type: "line",
                data: confRange,
                lineStyle: { opacity: 0 },
                areaStyle: {
                  color: isDark ? "rgba(245, 158, 11, 0.12)" : "rgba(217, 119, 6, 0.14)",
                },
                stack: "confidence-band",
                symbol: "none",
              },
            ]
          : []),
        // 3. Model Estimate Trajectory (Past Stored Model Estimates)
        {
          name: "Model estimate (past)",
          type: "line",
          data: observedData,
          smooth: true,
          lineStyle: {
            width: 2.8,
            color: palette.observedBand,
          },
          symbol: "circle",
          symbolSize: 4,
          itemStyle: { color: palette.observedBand },
          markLine: {
            symbol: ["none", "none"],
            data: [
              // Dynamic "NOW" Marker
              {
                xAxis: validNowIdx,
                lineStyle: {
                  color: "#38bdf8",
                  width: 2,
                  type: "dashed",
                },
                label: {
                  formatter: "NOW",
                  position: "end",
                  color: "#38bdf8",
                  fontWeight: "bold",
                  fontSize: 10,
                },
              },
              // High Risk Threshold
              {
                yAxis: Math.round((thresholds?.high ?? 0.47) * 100),
                lineStyle: {
                  color: palette.riskHigh,
                  width: 1.2,
                  type: "dashed",
                },
                label: {
                  formatter: `High Risk Threshold (${Math.round((thresholds?.high ?? 0.47) * 100)}%)`,
                  position: "insideEndTop",
                  color: palette.riskHigh,
                  fontSize: 10,
                },
              },
            ],
          },
        },
        // 4. Predicted Trajectory (Now to +12h)
        {
          name: "Predicted Risk",
          type: "line",
          data: predictedData,
          smooth: true,
          lineStyle: {
            width: 2.8,
            color: palette.predictedBand,
            type: "dashed",
          },
          symbol: "circle",
          symbolSize: 5,
          itemStyle: { color: palette.predictedBand },
        },
        // 5. What-If Counterfactual Simulated Ghost Line
        ...(whatIfCurve
          ? [
              {
                name: "Simulated What-If",
                type: "line",
                data: whatIfCurve,
                smooth: true,
                lineStyle: {
                  width: 2.2,
                  color: "#ec4899",
                  type: "dotted",
                },
                symbol: "emptyCircle",
                symbolSize: 4,
                itemStyle: { color: "#ec4899" },
              },
            ]
          : []),
        // 6. BP Cuff Readings (Diamonds)
        {
          name: "BP Cuff Measurement",
          type: "scatter",
          data: bpScatterData.map((d: any) => d.coord),
          symbol: "diamond",
          symbolSize: 13,
          itemStyle: {
            color: palette.circadianBp,
            borderColor: "#ffffff",
            borderWidth: 1.5,
          },
        },
        // 7. Medication Events (Capsules)
        {
          name: "Medication Dose",
          type: "scatter",
          data: medScatterData.map((d: any) => d.coord),
          symbol: "roundRect",
          symbolSize: [12, 18],
          itemStyle: {
            color: palette.circadianMed,
            borderColor: "#ffffff",
            borderWidth: 1.2,
          },
        },
      ],
    };
  }, [series, theme, whatIfSimulatedRisk]);

  return (
    <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 shadow-sm relative">
      {/* Header bar with Peak Window Badge & Coverage */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-serif text-base font-semibold text-white tracking-tight flex items-center gap-2">
              The Risk Horizon (Model estimate (past) vs Predicted Forecast)
            </h3>
            {whatIfSimulatedRisk != null && (
              <span className="text-[11px] px-2 py-0.5 rounded-full font-medium bg-pink-950/70 text-pink-300 border border-pink-700/50 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-pink-400" />
                What-If Active
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Synchronized hemodynamic risk trajectory, sleep architecture, home BP cuff readings, and medication events.
          </p>
        </div>

        {/* Badges: Peak Vulnerability + Data Coverage */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-950/50 border border-amber-800/60 text-amber-300 text-xs">
            <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
            <span className="font-medium text-[11px]">{horizon.peak_risk_window.label}:</span>
            <span className="font-bold tabular-nums font-mono text-[11px]">
              {horizon.peak_risk_window.peak_risk_pct}%
            </span>
          </div>

          <div className="px-2.5 py-1 rounded-lg bg-slate-800/80 border border-slate-700/80 text-slate-300 text-[11px] font-mono">
            Coverage: <span className="text-emerald-400 font-semibold">{horizon.data_coverage_pct}%</span>
          </div>
        </div>
      </div>

      {/* Main ECharts Canvas */}
      <div className="w-full h-80">
        <EChart
          option={option}
          style={{ height: "100%", width: "100%" }}
          notMerge={true}
        />
      </div>

      {/* Sleep Stage Legend & Circadian Markers */}
      <div className="mt-2 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-4 text-xs">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-1 rounded bg-[#38bdf8]" />
            <span className="text-slate-300 text-[11px]">Model estimate (past)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-1 rounded border-b-2 border-dashed border-[#f59e0b]" />
            <span className="text-slate-300 text-[11px]">Predicted Forecast</span>
          </div>
          {hasValidConfidence ? (
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-2 rounded bg-amber-500/20 border border-amber-500/40" />
              <span className="text-slate-400 text-[11px]">95% Confidence Band</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400 text-[11px]">Confidence Band: interval not available</span>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rotate-45 bg-purple-500 border border-white" />
            <span className="text-slate-300 text-[11px]">Home Cuff BP</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-3 rounded-full bg-pink-500 border border-white" />
            <span className="text-slate-300 text-[11px]">Medication Event</span>
          </div>
        </div>

        <div className="text-[11px] text-slate-400 font-mono flex items-center gap-3">
          <span>Morning Surge: <strong className="text-slate-200">+{horizon.morning_surge_magnitude} mmHg</strong></span>
          <span>•</span>
          <span>Nocturnal Dip: <strong className="text-slate-200">{horizon.nocturnal_dipping_pct != null ? `${horizon.nocturnal_dipping_pct}%` : "N/A (Requires ABPM)"}</strong></span>
        </div>
      </div>

      {/* Written Clinical Summary Box */}
      <div className="mt-3 p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300 leading-relaxed font-serif">
        <span className="font-sans font-semibold text-slate-400 uppercase text-[10px] tracking-wider block mb-1">
          Trajectory Rationale & Diurnal Assessment
        </span>
        {horizon.risk_summary_text}
      </div>
    </div>
  );
};
