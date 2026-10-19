/**
 * RightAlertDrawer: Nocturne Clinical Observatory Alert Feed & Action Panel
 * Categorized into Review Now (High Risk), Review Today (Moderate), and Monitor (Low).
 * Direct clinician triage: Acknowledge, Snooze with reason, False Positive audit.
 */

import React, { useState } from "react";
import {
  CheckCircle2,
  Clock,
  Eye,
  MessageSquare,
  ShieldAlert,
  X,
} from "lucide-react";
import { AlertResponse } from "../types";

interface RightAlertDrawerProps {
  alerts: AlertResponse[];
  onAcknowledge: (alertId: string) => void;
  onSnooze: (alertId: string, hours: number, reason?: string) => void;
  onFalsePositive: (alertId: string, reason?: string) => void;
  onRequestRecheck: () => void;
  onAddNote: () => void;
  isOpen: boolean;
  onToggle: () => void;
}

export const RightAlertDrawer: React.FC<RightAlertDrawerProps> = ({
  alerts,
  onAcknowledge,
  onSnooze,
  onFalsePositive,
  onRequestRecheck,
  onAddNote,
  isOpen,
  onToggle,
}) => {
  const [selectedAlertForAction, setSelectedAlertForAction] = useState<AlertResponse | null>(null);
  const [actionType, setActionType] = useState<"snooze" | "false_positive" | null>(null);
  const [snoozeHours, setSnoozeHours] = useState<number>(4);
  const [reasonText, setReasonText] = useState<string>("");

  // Categorize alerts
  const reviewNow = alerts.filter((a) => a.risk_level === "High" && a.status === "open");
  const reviewToday = alerts.filter(
    (a) => (a.risk_level === "Moderate" && a.status === "open") || a.status === "snoozed"
  );
  const monitor = alerts.filter(
    (a) => a.risk_level === "Low" || a.status === "acknowledged" || a.status === "false_positive"
  );

  const handleConfirmAction = () => {
    if (!selectedAlertForAction) return;

    if (actionType === "snooze") {
      onSnooze(
        selectedAlertForAction.alert_id,
        snoozeHours,
        reasonText.trim() || undefined
      );
    } else if (actionType === "false_positive") {
      onFalsePositive(
        selectedAlertForAction.alert_id,
        reasonText.trim() || undefined
      );
    }

    setSelectedAlertForAction(null);
    setActionType(null);
    setReasonText("");
  };

  return (
    <>
      <aside
        className={`fixed lg:static top-0 right-0 h-full w-84 bg-slate-900 border-l border-slate-800 flex flex-col z-40 transition-transform duration-200 ${
          isOpen ? "translate-x-0" : "translate-x-full lg:translate-x-0"
        }`}
        aria-label="Clinical Triage Drawer"
      >
        {/* Drawer Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-rose-950/60 text-rose-400 border border-rose-800/40">
              <ShieldAlert className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-serif font-semibold text-white text-sm">Clinical Triage & Alerts</h3>
              <p className="text-[11px] text-slate-400">Decision-Support Inbox</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">
              {reviewNow.length} Critical
            </span>
            <button
              onClick={onToggle}
              className="lg:hidden p-1 text-slate-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Alerts Feed */}
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {/* 1. Review Now (High Risk) */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] uppercase font-bold tracking-wider text-rose-400 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
                Review Now ({reviewNow.length})
              </span>
            </div>

            {reviewNow.length === 0 ? (
              <div className="p-3 rounded-lg bg-slate-950/40 border border-slate-800/60 text-slate-400 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span>No pending critical alerts for this patient.</span>
              </div>
            ) : (
              <div className="space-y-2">
                {reviewNow.map((alert) => (
                  <div
                    key={alert.alert_id}
                    className="p-3 rounded-xl bg-rose-950/20 border border-rose-800/50 hover:border-rose-700 transition-colors shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-mono font-bold text-rose-400 tabular-nums">
                        {Math.round(alert.probability * 100)}% Probability
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {new Date(alert.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>

                    <p className="text-xs text-slate-200 font-serif leading-relaxed mt-1.5">
                      {alert.message}
                    </p>

                    {/* Actions */}
                    <div className="mt-3 pt-2 border-t border-rose-900/40 flex items-center justify-between gap-1">
                      <button
                        onClick={() => onAcknowledge(alert.alert_id)}
                        className="px-2.5 py-1 rounded bg-rose-900/60 hover:bg-rose-800 text-rose-200 text-[11px] font-medium transition-colors"
                      >
                        Acknowledge
                      </button>

                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => {
                            setSelectedAlertForAction(alert);
                            setActionType("snooze");
                          }}
                          className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] transition-colors"
                          title="Snooze Alert"
                        >
                          Snooze
                        </button>
                        <button
                          onClick={() => {
                            setSelectedAlertForAction(alert);
                            setActionType("false_positive");
                          }}
                          className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 text-[11px] transition-colors"
                          title="Mark False Positive"
                        >
                          Audit FP
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 2. Review Today (Moderate / Snoozed) */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] uppercase font-bold tracking-wider text-amber-400 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                Review Today ({reviewToday.length})
              </span>
            </div>

            {reviewToday.length === 0 ? (
              <div className="p-3 rounded-lg bg-slate-950/40 border border-slate-800/60 text-slate-400 text-xs">
                No intermediate alerts scheduled for today.
              </div>
            ) : (
              <div className="space-y-2">
                {reviewToday.map((alert) => (
                  <div
                    key={alert.alert_id}
                    className="p-3 rounded-xl bg-amber-950/20 border border-amber-800/50 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-amber-400 font-bold">
                        {Math.round(alert.probability * 100)}% Risk
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono capitalize">
                        {alert.status}
                      </span>
                    </div>
                    <p className="text-slate-300 mt-1 font-serif text-[11px] leading-snug">
                      {alert.message}
                    </p>
                    {alert.status === "open" && (
                      <div className="mt-2 pt-2 border-t border-amber-900/30 flex justify-end">
                        <button
                          onClick={() => onAcknowledge(alert.alert_id)}
                          className="text-[11px] px-2 py-0.5 rounded bg-amber-900/40 text-amber-200 hover:bg-amber-800/60"
                        >
                          Acknowledge
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 3. Monitor / Resolved */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] uppercase font-bold tracking-wider text-slate-400 flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5 text-slate-400" />
                Resolved / Historical ({monitor.length})
              </span>
            </div>

            <div className="space-y-1.5">
              {monitor.slice(0, 5).map((alert) => (
                <div
                  key={alert.alert_id}
                  className="p-2.5 rounded-lg bg-slate-950/30 border border-slate-800/50 text-[11px] text-slate-400"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-slate-300">
                      {Math.round(alert.probability * 100)}% • <span className="capitalize">{alert.status}</span>
                    </span>
                    <span className="text-[10px] text-slate-400">
                      {new Date(alert.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {alert.acknowledged_by && (
                    <div className="text-[10px] text-slate-400 mt-1">
                      Ack by {alert.acknowledged_by}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom Fast Action Buttons */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/60 space-y-2">
          <button
            onClick={onRequestRecheck}
            className="w-full py-2 px-3 rounded-lg bg-indigo-950/60 hover:bg-indigo-900/70 border border-indigo-700/60 text-indigo-300 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors focus-visible:ring-2 focus-visible:ring-purple-400"
          >
            <Clock className="w-3.5 h-3.5" />
            Order Home BP Cuff Recheck
          </button>
          <button
            onClick={() => setActionType("note" as any)}
            className="w-full py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors focus-visible:ring-2 focus-visible:ring-purple-400"
          >
            <MessageSquare className="w-3.5 h-3.5 text-cyan-400" />
            Document Clinical Note
          </button>
        </div>
      </aside>

      {/* Snooze / False Positive / Note Modal Dialog */}
      {(selectedAlertForAction || actionType === ("note" as any)) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 max-w-md w-full shadow-2xl">
            <h4 className="font-serif text-base font-semibold text-white">
              {actionType === "snooze"
                ? "Snooze Clinical Alert"
                : actionType === ("note" as any)
                ? "Document Clinical Decision Note"
                : "Mark Alert as False Positive"}
            </h4>
            <p className="text-xs text-slate-400 mt-1">
              Documenting clinical rationale for decision-support audit logging.
            </p>

            {actionType === "snooze" && (
              <div className="mt-3">
                <label className="text-xs font-medium text-slate-300 block mb-1">
                  Snooze Duration (Hours):
                </label>
                <select
                  value={snoozeHours}
                  onChange={(e) => setSnoozeHours(Number(e.target.value))}
                  className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-200 focus-visible:ring-2 focus-visible:ring-purple-400"
                >
                  <option value={2}>2 Hours (Post-prandial wait)</option>
                  <option value={4}>4 Hours (Standard morning window)</option>
                  <option value={8}>8 Hours (Next shift handover)</option>
                  <option value={24}>24 Hours (Next monitoring cycle)</option>
                </select>
              </div>
            )}

            <div className="mt-3">
              <label className="text-xs font-medium text-slate-300 block mb-1">
                {actionType === "snooze" ? (
                  <span className="text-rose-400">* Documented Clinical Reason (Mandatory):</span>
                ) : actionType === ("note" as any) ? (
                  <span>Clinical Observation Note:</span>
                ) : (
                  <span>Audit Explanation:</span>
                )}
              </label>
              <textarea
                value={reasonText}
                onChange={(e) => setReasonText(e.target.value)}
                placeholder={
                  actionType === "snooze"
                    ? "Required: e.g., Patient instructed to rest seated; awaiting repeat measurement..."
                    : actionType === ("note" as any)
                    ? "Enter physician note regarding patient hypertension status or protocol..."
                    : "e.g., Patient reported transient dental pain / white-coat anxiety..."
                }
                rows={3}
                className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500 focus-visible:ring-2 focus-visible:ring-purple-400"
              />
              {actionType === "snooze" && !reasonText.trim() && (
                <span className="text-[11px] text-rose-400 mt-1 block">
                  A clinical reason must be provided before snoozing this alert.
                </span>
              )}
            </div>

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                onClick={() => {
                  setSelectedAlertForAction(null);
                  setActionType(null);
                  setReasonText("");
                }}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs hover:bg-slate-700 focus-visible:ring-2 focus-visible:ring-purple-400"
              >
                Cancel
              </button>
              <button
                disabled={actionType === "snooze" && !reasonText.trim()}
                onClick={() => {
                  if (actionType === ("note" as any)) {
                    onAddNote();
                    setActionType(null);
                    setReasonText("");
                  } else {
                    handleConfirmAction();
                  }
                }}
                className={`px-4 py-1.5 rounded-lg text-white text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-purple-400 ${
                  actionType === "snooze" && !reasonText.trim()
                    ? "bg-slate-700 text-slate-400 cursor-not-allowed"
                    : "bg-purple-600 hover:bg-purple-500"
                }`}
              >
                {actionType === ("note" as any) ? "Save Clinical Note" : "Confirm Log"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
