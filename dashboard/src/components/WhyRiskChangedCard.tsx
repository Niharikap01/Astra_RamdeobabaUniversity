/**
 * WhyRiskChangedCard: Clinical Risk Factor Attribution Waterfall
 * Explains changes in next-24h hypertensive risk between evaluation intervals
 * in plain language ("associated with") with mandatory trust statements and
 * graceful handling of initial baseline states.
 */

import React, { useMemo } from "react";
import { ArrowDownRight, ArrowUpRight, GitCommit, Info } from "lucide-react";
import { WhyRiskChangedResponse } from "../types";
import { EChart } from "./EChart";
import { DataTableToggle } from "./DataTableToggle";

interface WhyRiskChangedCardProps {
  data: WhyRiskChangedResponse | null;
  patientId: string;
}

export const WhyRiskChangedCard: React.FC<WhyRiskChangedCardProps> = ({
  data,
  patientId,
}) => {
  // Empty / No prior prediction state
  if (!data || data.previous_risk_pct == null || !data.factors || data.factors.length === 0) {
    return (
      <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 shadow-sm space-y-3">
        <div className="flex items-center gap-2">
          <GitCommit className="w-4 h-4 text-purple-400" />
          <h3 className="text-sm font-semibold text-slate-200">
            Attribution Trajectory: Why Risk Changed
          </h3>
        </div>
        <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs text-slate-400 flex items-start gap-3">
          <Info className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-slate-300">Initial Evaluation Baseline Established</p>
            <p className="mt-1 leading-relaxed">
              {data?.summary || "No previous prediction exists for this patient. Attribution deltas will generate after subsequent evaluation cycles."}
            </p>
            <p className="mt-2 text-[11px] text-slate-500 font-mono">
              Current Modeled Risk: {data?.current_risk_pct != null ? `${data.current_risk_pct}%` : "—"}
            </p>
          </div>
        </div>
        {data?.trust_statement && (
          <div className="text-[11px] text-slate-500 italic border-t border-slate-800/60 pt-2">
            <strong>Trust Statement:</strong> {data.trust_statement}
          </div>
        )}
      </div>
    );
  }

  const { factors, current_risk_pct, previous_risk_pct, risk_delta_pct, trust_statement } = data;

  // Single-line written summary generated from real data
  const oneLineSummary = useMemo(() => {
    if (
      risk_delta_pct == null ||
      previous_risk_pct == null ||
      !Number.isFinite(risk_delta_pct) ||
      !Number.isFinite(previous_risk_pct) ||
      !Number.isFinite(current_risk_pct)
    ) {
      return "Risk change is unavailable because a prior estimate is missing.";
    }
    const directionWord = risk_delta_pct >= 0 ? "increased" : "decreased";
    const deltaAbs = Math.abs(risk_delta_pct);
    const topFactor = factors[0];
    const topFactorText = topFactor ? ` primarily associated with ${topFactor.display_name.toLowerCase()}` : "";
    return `Modeled risk ${directionWord} by ${deltaAbs.toFixed(1)}% (from ${previous_risk_pct}% to ${current_risk_pct}%)${topFactorText}.`;
  }, [factors, current_risk_pct, previous_risk_pct, risk_delta_pct]);

  // Waterfall / Horizontal Diverging Bar Option
  const chartOption = useMemo(() => {
    // Reverse so top factor is on top of yAxis
    const sorted = [...factors].reverse();
    const categories = sorted.map((f) => f.display_name);
    const values = sorted.map((f) => {
      const isIncrease = f.direction === "increased_risk";
      const val = f.impact_delta;
      return {
        value: isIncrease ? val : -val,
        itemStyle: {
          color: isIncrease ? "#f43f5e" : "#10b981",
          borderRadius: isIncrease ? [0, 4, 4, 0] : [4, 0, 0, 4],
        },
      };
    });

    return {
      grid: { top: 20, right: 30, bottom: 20, left: 140, containLabel: false },
      tooltip: {
        trigger: "axis",
        formatter: (params: any[]) => {
          if (!params || !params[0]) return "";
          const idx = params[0].dataIndex;
          const factor = sorted[idx];
          if (!factor) return "";
          const isIncrease = factor.direction === "increased_risk";
          return `
            <div style="font-weight: 600; margin-bottom: 2px;">${factor.display_name}</div>
            <div style="color: ${isIncrease ? "#f43f5e" : "#10b981"}; font-weight: 600;">
              ${isIncrease ? "Associated with Increased Risk (+)" : "Associated with Decreased Risk (-)"}
            </div>
            <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
              ${factor.clinical_explanation}
            </div>
          `;
        },
      },
      xAxis: {
        type: "value",
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "#1e293b", type: "dashed" } },
        axisLabel: {
          color: "#64748b",
          fontSize: 10,
          formatter: (v: number) => (v > 0 ? `+${v}` : `${v}`),
        },
      },
      yAxis: {
        type: "category",
        data: categories,
        axisLine: { lineStyle: { color: "#334155" } },
        axisTick: { show: false },
        axisLabel: { color: "#cbd5e1", fontSize: 11 },
      },
      series: [
        {
          name: "Factor Impact",
          type: "bar",
          data: values,
          barMaxWidth: 14,
        },
      ],
    };
  }, [factors]);

  // Table columns for CSV/Tabular inspection
  const tableCols = [
    { key: "display_name", label: "Physiological Factor" },
    { key: "previous_value", label: "Prior Baseline" },
    { key: "current_value", label: "Current Telemetry" },
    { key: "impact_delta", label: "Impact Magnitude" },
    {
      key: "direction",
      label: "Direction",
      format: (v: string) => (v === "increased_risk" ? "Increased Risk" : "Decreased Risk"),
    },
    { key: "clinical_explanation", label: "Clinical Attribution" },
  ];

  return (
    <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <GitCommit className="w-4 h-4 text-purple-400" />
            Clinical Factor Attribution: Why Risk Changed
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Signed feature diffs between evaluation cycles framed as probabilistic associations.
          </p>
        </div>

        {/* Delta Badge */}
        <div className={`px-2.5 py-1 rounded-lg border text-xs font-mono font-medium self-start sm:self-auto flex items-center gap-1.5 ${
          (risk_delta_pct || 0) > 0
            ? "border-rose-500/40 bg-rose-950/30 text-rose-300"
            : (risk_delta_pct || 0) < 0
            ? "border-emerald-500/40 bg-emerald-950/30 text-emerald-300"
            : "border-slate-700 bg-slate-800/40 text-slate-400"
        }`}>
          {risk_delta_pct == null ? (
            "Risk delta: no data"
          ) : (
            <>
              {risk_delta_pct > 0 ? (
                <ArrowUpRight className="w-3.5 h-3.5 text-rose-400" />
              ) : risk_delta_pct < 0 ? (
                <ArrowDownRight className="w-3.5 h-3.5 text-emerald-400" />
              ) : null}
              Risk Delta: {risk_delta_pct > 0 ? "+" : ""}{risk_delta_pct}%
            </>
          )}
        </div>
      </div>

      {/* Main Chart wrapped with DataTableToggle */}
      <DataTableToggle
        rows={factors}
        cols={tableCols}
        title="Attribution Factor Breakdown"
        filename={`nightwatch_why_risk_changed_${patientId}.csv`}
      >
        <div className="h-48 sm:h-56 w-full">
          <EChart option={chartOption} style={{ height: "100%", width: "100%" }} />
        </div>
      </DataTableToggle>

      {/* Plain Language Explanations List */}
      <div className="space-y-1.5 pt-1">
        {factors.slice(0, 3).map((factor, idx) => (
          <div key={idx} className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300 flex items-start gap-2.5">
            <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${
              factor.direction === "increased_risk" ? "bg-rose-400" : "bg-emerald-400"
            }`} />
            <div>
              <span className="font-semibold text-slate-200">{factor.display_name}: </span>
              <span className="text-slate-300">{factor.clinical_explanation}</span>
            </div>
          </div>
        ))}
      </div>

      {/* One-Line Written Clinical Summary */}
      <div className="p-2.5 rounded-lg bg-purple-950/20 border border-purple-500/30 flex items-start gap-2 text-xs text-purple-200">
        <Info className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
        <span className="leading-relaxed">{oneLineSummary}</span>
      </div>

      {/* Mandatory Trust Statement */}
      <div className="text-[11px] text-slate-500 italic pt-1 border-t border-slate-800/60">
        <strong>Attribution Trust Statement:</strong> {trust_statement}
      </div>
    </div>
  );
};
