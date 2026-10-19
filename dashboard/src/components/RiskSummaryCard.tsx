/**
 * RiskSummaryCard: Executive Clinical Risk Assessment
 * Displays 0-100 calibrated episode risk score, risk band badge, and plain-language driver overview.
 */

import React from "react";
import { AlertTriangle, CheckCircle2, ChevronRight, Info, ShieldAlert, TrendingUp } from "lucide-react";
import { PredictionResponse } from "../types";

interface RiskSummaryCardProps {
  prediction: PredictionResponse | null;
  recommendedActions: string[];
  thresholds?: { moderate: number; high: number };
}

export const RiskSummaryCard: React.FC<RiskSummaryCardProps> = ({
  prediction,
  recommendedActions,
  thresholds,
}) => {
  if (!prediction || prediction.probability === null || prediction.probability === undefined) {
    return (
      <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 text-slate-400 text-sm flex items-center justify-between">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
            Executive Assessment
          </span>
          <h3 className="font-serif text-lg font-semibold text-white tracking-tight mt-0.5">
            24h Hypertensive Episode Risk
          </h3>
        </div>
        <span className="px-2.5 py-1 rounded-full text-xs font-semibold border bg-slate-800 text-slate-400 border-slate-700 font-mono">
          no prediction
        </span>
      </div>
    );
  }

  const riskPct = Math.round(prediction.probability * 100);
  const isHigh = prediction.risk_level === "High";
  const isModerate = prediction.risk_level === "Moderate";

  const badgeColor = isHigh
    ? "bg-rose-950/70 text-rose-300 border-rose-700/60"
    : isModerate
    ? "bg-amber-950/70 text-amber-300 border-amber-700/60"
    : "bg-emerald-950/70 text-emerald-300 border-emerald-700/60";

  const arcColor = isHigh ? "#ef4444" : isModerate ? "#f59e0b" : "#10b981";

  return (
    <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 shadow-sm flex flex-col justify-between">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block">
            Executive Assessment
          </span>
          <h3 className="font-serif text-lg font-semibold text-white tracking-tight mt-0.5">
            24h Hypertensive Episode Risk
          </h3>
        </div>
        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${badgeColor}`}>
          {prediction.risk_level} Risk Tier
        </span>
      </div>

      {/* Center: Probability Dial & Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-12 gap-4 my-4 items-center">
        {/* Calibrated Risk Dial (Semi-Circular Arc) */}
        <div className="sm:col-span-5 flex flex-col items-center justify-center p-3 rounded-xl bg-slate-950/50 border border-slate-800/80">
          <div className="relative w-32 h-20 flex items-end justify-center overflow-hidden">
            <svg viewBox="0 0 100 55" className="w-full h-full">
              {/* Background Arc */}
              <path
                d="M 10 50 A 40 40 0 0 1 90 50"
                fill="none"
                stroke="#1e293b"
                strokeWidth="9"
                strokeLinecap="round"
              />
              {/* Filled Risk Arc */}
              <path
                d="M 10 50 A 40 40 0 0 1 90 50"
                fill="none"
                stroke={arcColor}
                strokeWidth="9"
                strokeLinecap="round"
                strokeDasharray="125.6"
                strokeDashoffset={125.6 * (1 - Math.min(100, Math.max(0, riskPct)) / 100)}
                className="transition-all duration-700 ease-out"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
              <span className="text-3xl font-bold font-mono tracking-tight text-white tabular-nums">
                {riskPct}%
              </span>
            </div>
          </div>
          <span className="text-[11px] text-slate-400 font-mono mt-1">Calibrated Likelihood</span>
        </div>

        {/* Narrative & Clinical Threshold Guidance */}
        <div className="sm:col-span-7 space-y-2">
          <div className="text-xs text-slate-300 leading-relaxed font-serif">
            {isHigh ? (
              <p>
                Next-day SBP $\ge 140$ or DBP $\ge 90$ mmHg excursion is <strong>probable ({riskPct}%)</strong>.
                Sympathetic drive and nocturnal vascular stiffness suggest active morning surge vulnerability.
              </p>
            ) : isModerate ? (
              <p>
                Patient displays <strong>intermediate risk ({riskPct}%)</strong>. Hemodynamics remain sensitive to
                sub-optimal sleep architecture and oral medication delays.
              </p>
            ) : (
              <p>
                Low risk profile (<strong>{riskPct}%</strong>). Circadian autonomic tone and home cuff measurements
                remain aligned within personal 30-day baseline boundaries.
              </p>
            )}
          </div>

          <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono pt-1">
            <span>Model v{prediction.model_version}</span>
            <span>•</span>
            <span>
              Bands: Low &lt;{Math.round((thresholds?.moderate ?? 0.34) * 100)}% | Mod {Math.round((thresholds?.moderate ?? 0.34) * 100)}-{Math.round((thresholds?.high ?? 0.47) * 100) - 1}% | High &ge;{Math.round((thresholds?.high ?? 0.47) * 100)}%
            </span>
          </div>
        </div>
      </div>

      {/* Suggested Actions Snippet */}
      {recommendedActions.length > 0 && (
        <div className="pt-3 border-t border-slate-800/80">
          <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider block mb-1.5">
            Guideline-Directed Clinical Suggestions
          </span>
          <div className="space-y-1">
            {recommendedActions.slice(0, 2).map((action, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs text-slate-300">
                <ChevronRight className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0 mt-0.5" />
                <span>{action}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
