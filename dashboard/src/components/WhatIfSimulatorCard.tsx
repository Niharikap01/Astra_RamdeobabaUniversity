/**
 * WhatIfSimulatorCard: Interactive Counterfactual Digital Twin Simulation
 * Presets, granular sliders, side-by-side current vs simulated comparison,
 * ghosted curve sync to Risk Horizon, up to 3 saved scenarios,
 * and mandatory clinical decision-support disclaimers.
 */

import React, { useState, useEffect, useCallback } from "react";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  BookmarkCheck,
  CheckCircle2,
  Clock,
  HelpCircle,
  Info,
  Moon,
  Pill,
  RefreshCw,
  RotateCcw,
  Sliders,
  Sparkles,
  Trash2,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { api } from "../services/api";
import { WhatIfResponse } from "../types";

interface WhatIfSimulatorCardProps {
  patientId: string;
  currentRiskPct?: number | null;
  onSimulatedRiskChange?: (simulatedRiskPct: number | null) => void;
}

interface SavedScenario {
  id: string;
  name: string;
  sleepDelta: number;
  medicationTaken: number;
  stepsDelta: number;
  sbpDelta: number;
  simulatedRiskPct: number;
  deltaPct: number;
}

export const WhatIfSimulatorCard: React.FC<WhatIfSimulatorCardProps> = ({
  patientId,
  currentRiskPct,
  onSimulatedRiskChange,
}) => {
  // Slider states
  const [sleepDelta, setSleepDelta] = useState<number>(0);
  const [medicationTaken, setMedicationTaken] = useState<number>(1);
  const [stepsDelta, setStepsDelta] = useState<number>(0);
  const [sbpDelta, setSbpDelta] = useState<number>(0);

  // Simulation response state
  const [simulationResult, setSimulationResult] = useState<WhatIfResponse | null>(null);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [savedScenarios, setSavedScenarios] = useState<SavedScenario[]>([]);

  // Presets definition
  const presets = [
    {
      name: "Sleep Extension (+1.5h)",
      icon: Moon,
      apply: () => {
        setSleepDelta(1.5);
        setMedicationTaken(1);
        setStepsDelta(0);
        setSbpDelta(0);
      },
    },
    {
      name: "Strict Adherence (Dose Taken)",
      icon: Pill,
      apply: () => {
        setSleepDelta(0);
        setMedicationTaken(1);
        setStepsDelta(0);
        setSbpDelta(0);
      },
    },
    {
      name: "Daily Activity (+4,000 Steps)",
      icon: TrendingUp,
      apply: () => {
        setSleepDelta(0);
        setMedicationTaken(1);
        setStepsDelta(4000);
        setSbpDelta(0);
      },
    },
    {
      name: "Comprehensive Lifestyle Plan",
      icon: Sparkles,
      apply: () => {
        setSleepDelta(1.5);
        setMedicationTaken(1);
        setStepsDelta(3000);
        setSbpDelta(-5);
      },
    },
  ];

  // Execute simulation
  const runSimulation = useCallback(async () => {
    if (!patientId) return;
    setIsSimulating(true);
    try {
      const overrides: Record<string, any> = {};
      if (sleepDelta !== 0) overrides.sleep_duration_delta = sleepDelta;
      if (medicationTaken !== undefined) overrides.medication_taken = medicationTaken;
      if (stepsDelta !== 0) overrides.steps_delta = stepsDelta;
      if (sbpDelta !== 0) overrides.sbp_delta = sbpDelta;

      const res = await api.postWhatIf(patientId, overrides);
      setSimulationResult(res);

      if (onSimulatedRiskChange) {
        onSimulatedRiskChange(Math.round(res.new_probability * 100));
      }
    } catch (err) {
      console.error("What-If simulation failed:", err);
    } finally {
      setIsSimulating(false);
    }
  }, [patientId, sleepDelta, medicationTaken, stepsDelta, sbpDelta, onSimulatedRiskChange]);

  useEffect(() => {
    runSimulation();
  }, [runSimulation]);

  // Reset sliders
  const handleReset = () => {
    setSleepDelta(0);
    setMedicationTaken(1);
    setStepsDelta(0);
    setSbpDelta(0);
    if (onSimulatedRiskChange) {
      onSimulatedRiskChange(null);
    }
  };

  // Save scenario (up to 3)
  const handleSaveScenario = () => {
    if (!simulationResult || savedScenarios.length >= 3) return;
    const simPct = Math.round(simulationResult.new_probability * 100);
    const deltaPct = Math.round(simulationResult.delta * 100);
    const newScenario: SavedScenario = {
      id: Date.now().toString(),
      name: `Scenario ${savedScenarios.length + 1} (${simPct}%)`,
      sleepDelta,
      medicationTaken,
      stepsDelta,
      sbpDelta,
      simulatedRiskPct: simPct,
      deltaPct,
    };
    setSavedScenarios([...savedScenarios, newScenario]);
  };

  const handleDeleteScenario = (id: string) => {
    setSavedScenarios(savedScenarios.filter((s) => s.id !== id));
  };

  const handleApplyScenario = (s: SavedScenario) => {
    setSleepDelta(s.sleepDelta);
    setMedicationTaken(s.medicationTaken);
    setStepsDelta(s.stepsDelta);
    setSbpDelta(s.sbpDelta);
  };

  const currentRisk = simulationResult ? Math.round(simulationResult.baseline_probability * 100) : currentRiskPct ?? 35;
  const simulatedRisk = simulationResult ? Math.round(simulationResult.new_probability * 100) : currentRisk;
  const deltaRisk = simulatedRisk - currentRisk;

  return (
    <div className="bg-slate-900/90 rounded-xl p-5 border border-slate-800 shadow-sm space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Sliders className="w-4 h-4 text-purple-400" />
            Counterfactual What-If Simulator
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Model sustained lifestyle or pharmacological interventions over the coming week.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={handleReset}
            className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs flex items-center gap-1.5 transition-colors focus-visible:ring-2 focus-visible:ring-purple-500"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </button>
        </div>
      </div>

      {/* Preset Action Chips */}
      <div>
        <span className="text-[11px] uppercase font-semibold text-slate-400 tracking-wider block mb-2">
          Clinical Scenario Presets
        </span>
        <div className="flex flex-wrap gap-2">
          {presets.map((preset) => {
            const Icon = preset.icon;
            return (
              <button
                key={preset.name}
                onClick={preset.apply}
                className="px-3 py-1.5 rounded-lg bg-slate-950/80 hover:bg-purple-950/40 border border-slate-800 hover:border-purple-600/50 text-slate-300 hover:text-purple-200 text-xs font-medium flex items-center gap-2 transition-all focus-visible:ring-2 focus-visible:ring-purple-500"
              >
                <Icon className="w-3.5 h-3.5 text-purple-400" />
                {preset.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Side-by-Side Current vs Simulated Risk Comparison Card */}
      <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800/90 grid grid-cols-1 sm:grid-cols-3 gap-4 items-center">
        {/* Baseline State */}
        <div className="text-center sm:text-left">
          <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Current Baseline Risk</span>
          <div className="text-2xl font-bold font-mono text-slate-200 mt-1">
            {currentRisk}%
          </div>
          <span className="text-[10px] text-slate-500 font-mono mt-0.5 block">
            Band: {simulationResult?.baseline_risk_level || "Observed"}
          </span>
        </div>

        {/* Transition Arrow & Delta */}
        <div className="flex flex-col items-center justify-center border-y sm:border-y-0 sm:border-x border-slate-800/80 py-2 sm:py-0">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 text-xs">Simulated Shift</span>
            <ArrowRight className="w-4 h-4 text-purple-400" />
          </div>
          <div
            className={`text-sm font-mono font-bold mt-1 flex items-center gap-1 ${
              deltaRisk < 0
                ? "text-emerald-400"
                : deltaRisk > 0
                ? "text-rose-400"
                : "text-slate-400"
            }`}
          >
            {deltaRisk < 0 ? (
              <ArrowDownRight className="w-4 h-4" />
            ) : deltaRisk > 0 ? (
              <ArrowUpRight className="w-4 h-4" />
            ) : null}
            {deltaRisk > 0 ? `+${deltaRisk}%` : `${deltaRisk}%`}
          </div>
        </div>

        {/* Simulated State */}
        <div className="text-center sm:text-right">
          <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Simulated 24h Risk</span>
          <div
            className={`text-2xl font-bold font-mono mt-1 ${
              simulatedRisk >= 65
                ? "text-rose-400"
                : simulatedRisk >= 35
                ? "text-amber-400"
                : "text-emerald-400"
            }`}
          >
            {simulatedRisk}%
          </div>
          <span className="text-[10px] text-slate-400 font-mono mt-0.5 block">
            New Band: {simulationResult?.new_band || simulationResult?.new_risk_level || "Simulated"}
          </span>
        </div>
      </div>

      {/* Interactive Parameter Sliders */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Slider 1: Sleep Extension */}
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300 font-medium flex items-center gap-1.5">
              <Moon className="w-3.5 h-3.5 text-sky-400" /> Sleep Duration Change
            </span>
            <span className="font-mono text-purple-300 font-semibold">
              {sleepDelta > 0 ? `+${sleepDelta}h` : `${sleepDelta}h`}
            </span>
          </div>
          <input
            type="range"
            min={-3}
            max={3}
            step={0.5}
            value={sleepDelta}
            onChange={(e) => setSleepDelta(parseFloat(e.target.value))}
            className="w-full accent-purple-500 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400"
          />
          <div className="flex justify-between text-[10px] text-slate-500 font-mono">
            <span>-3.0h (Acute deficit)</span>
            <span>0h (Baseline)</span>
            <span>+3.0h (Restorative)</span>
          </div>
        </div>

        {/* Slider 2: Medication Adherence */}
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300 font-medium flex items-center gap-1.5">
              <Pill className="w-3.5 h-3.5 text-pink-400" /> Prescribed Antihypertensive
            </span>
            <span className="font-mono text-pink-300 font-semibold">
              {medicationTaken === 1 ? "Dose Taken (100%)" : "Missed Dose (0%)"}
            </span>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={() => setMedicationTaken(1)}
              className={`flex-1 py-1.5 text-xs rounded font-medium transition-colors ${
                medicationTaken === 1
                  ? "bg-pink-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              Dose Taken
            </button>
            <button
              onClick={() => setMedicationTaken(0)}
              className={`flex-1 py-1.5 text-xs rounded font-medium transition-colors ${
                medicationTaken === 0
                  ? "bg-rose-700 text-white"
                  : "bg-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              Missed Dose
            </button>
          </div>
          <p className="text-[10px] text-slate-500">
            Simulates sustained daily compliance vs omitted doses across 7-day memory.
          </p>
        </div>

        {/* Slider 3: Daily Steps Delta */}
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300 font-medium flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> Physical Activity Shift
            </span>
            <span className="font-mono text-purple-300 font-semibold">
              {stepsDelta > 0 ? `+${stepsDelta.toLocaleString()}` : stepsDelta.toLocaleString()} steps
            </span>
          </div>
          <input
            type="range"
            min={-4000}
            max={6000}
            step={1000}
            value={stepsDelta}
            onChange={(e) => setStepsDelta(parseInt(e.target.value, 10))}
            className="w-full accent-purple-500 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400"
          />
          <div className="flex justify-between text-[10px] text-slate-500 font-mono">
            <span>-4,000 steps</span>
            <span>Baseline</span>
            <span>+6,000 steps</span>
          </div>
        </div>

        {/* Slider 4: Cuff SBP Target Reduction */}
        <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300 font-medium flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-purple-400" /> Seated SBP Target Change
            </span>
            <span className="font-mono text-purple-300 font-semibold">
              {sbpDelta > 0 ? `+${sbpDelta} mmHg` : `${sbpDelta} mmHg`}
            </span>
          </div>
          <input
            type="range"
            min={-15}
            max={15}
            step={2}
            value={sbpDelta}
            onChange={(e) => setSbpDelta(parseInt(e.target.value, 10))}
            className="w-full accent-purple-500 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400"
          />
          <div className="flex justify-between text-[10px] text-slate-500 font-mono">
            <span>-15 mmHg</span>
            <span>0 mmHg</span>
            <span>+15 mmHg</span>
          </div>
        </div>
      </div>

      {/* Real Effect Note (Even when effect size is small) */}
      {simulationResult?.effect_note && (
        <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 flex items-start gap-2.5 text-xs text-slate-300">
          <Info className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
          <div className="leading-relaxed">
            <strong className="text-purple-300 font-sans">Empirical Effect Analysis: </strong>
            {simulationResult.effect_note}
          </div>
        </div>
      )}

      {/* Saved Scenarios Strip (Up to 3 saved scenarios) */}
      <div className="pt-2 border-t border-slate-800/80">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] uppercase font-semibold text-slate-400 tracking-wider">
            Saved Decision Scenarios ({savedScenarios.length}/3)
          </span>
          {savedScenarios.length < 3 && (
            <button
              onClick={handleSaveScenario}
              className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-purple-400 rounded"
            >
              <Bookmark className="w-3.5 h-3.5" />
              Save Current Simulation
            </button>
          )}
        </div>

        {savedScenarios.length === 0 ? (
          <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60 text-slate-500 text-xs">
            Save up to 3 intervention scenarios to compare simulated outcomes side-by-side.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {savedScenarios.map((scenario) => (
              <div
                key={scenario.id}
                className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-slate-700 flex items-center justify-between text-xs"
              >
                <button
                  onClick={() => handleApplyScenario(scenario)}
                  className="flex-1 text-left"
                >
                  <div className="font-medium text-slate-200">{scenario.name}</div>
                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                    Risk: <strong className="text-purple-300">{scenario.simulatedRiskPct}%</strong> ({scenario.deltaPct > 0 ? `+${scenario.deltaPct}%` : `${scenario.deltaPct}%`})
                  </div>
                </button>
                <button
                  onClick={() => handleDeleteScenario(scenario.id)}
                  className="text-slate-500 hover:text-rose-400 p-1"
                  title="Remove Scenario"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Mandatory Clinical Decision Support Disclaimer */}
      <div className="p-2.5 rounded-lg bg-amber-950/20 border border-amber-500/30 text-[11px] text-amber-200/90 leading-relaxed font-sans">
        <strong>Clinical Advisory:</strong> Modeled estimate, not a treatment recommendation.
        Simulations reflect synthetic mathematical projections of dependent feature modifications and do not represent validated pharmacological clinical trials or physician treatment directives.
      </div>
    </div>
  );
};
