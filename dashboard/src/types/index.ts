/**
 * NightWatch Frontend TypeScript Interface Definitions
 */

export interface PatientSummary {
  patient_id: string;
  name: string;
  age: number;
  sex: string;
  height_cm: number;
  weight_kg: number;
  bmi: number;
  archetype: string;
  created_at: string;
  latest_risk_level: "Low" | "Moderate" | "High" | null;
  latest_probability: number | null;
  open_alerts_count: number;
  data_coverage_pct?: number | null;
}

export interface PatientProfileDetail extends PatientSummary {
  diagnoses: string[];
  medications: string[];
  baseline_hrv_rmssd: number;
  baseline_resting_hr: number;
  baseline_sleep_hours: number;
  baseline_sbp: number;
  baseline_dbp: number;
}

export interface TopFactor {
  feature: string;
  display_name: string;
  value: number;
  impact: number;
  is_risk_driver: boolean;
  reason: string;
}

export interface PredictionResponse {
  prediction_id: string;
  patient_id: string;
  probability: number;
  risk_level: "Low" | "Moderate" | "High";
  model_version: string;
  generated_at: string;
  top_factors: TopFactor[];
  feature_snapshot: Record<string, number>;
}

export interface RadarAxisValue {
  axis: string;
  display_name: string;
  baseline_value: number;
  current_value: number;
  deviation_pct: number;
  status: string;
}

export interface SleepFingerprintData {
  nocturnal_bp_stability_pct: number;
  autonomic_resilience_pct: number;
  sleep_continuity_pct: number;
  morning_surge_control_pct: number;
  medication_coverage_pct: number;
  recovery_capacity_pct: number;
  sleep_duration_deviation_pct?: number;
  sleep_efficiency_deviation_pct?: number;
  hrv_deviation_pct?: number;
  resting_hr_deviation_pct?: number;
  bp_stability_deviation_pct?: number;
  nocturnal_dipping_deviation_pct?: number;
  axes: RadarAxisValue[];
  status: "optimal" | "degraded" | "acute_deficit";
  summary: string;
}

export interface StaticProfile {
  age: number;
  sex: string;
  bmi: number;
  diagnoses: string[];
  medications: string[];
  baseline_hrv_30d?: number | null;
  baseline_sleep_30d?: number | null;
}

export interface DynamicState {
  latest_sbp?: number | null;
  latest_dbp?: number | null;
  sbp_7d_mean?: number | null;
  sleep_last_night?: number | null;
  sleep_efficiency?: number | null;
  hrv_last_night?: number | null;
  resting_hr_last_night?: number | null;
  steps_yesterday?: number | null;
  medication_taken_last_night?: number | null;
}

export interface DigitalTwinResponse {
  patient_id: string;
  as_of: string;
  static_profile: StaticProfile;
  dynamic_state: DynamicState;
  prediction?: PredictionResponse | null;
  sleep_fingerprint: SleepFingerprintData;
  top_factors: TopFactor[];
  recommended_actions: string[];
  disclaimer: string;
}

export interface RiskHorizonPoint {
  timestamp: string;
  hour_offset: number;
  is_predicted: boolean;
  risk_pct: number;
  confidence_lower: number;
  confidence_upper: number;
  is_sleep_window: boolean;
  sleep_stage?: "awake" | "deep" | "rem" | "light" | null;
  has_bp_reading: boolean;
  measured_sbp?: number | null;
  measured_dbp?: number | null;
  predicted_sbp?: number | null;
  has_medication_event: boolean;
  medication_name?: string | null;
  is_missing_data: boolean;
}

export interface PeakRiskWindow {
  start: string;
  end: string;
  peak_risk_pct: number;
  label: string;
}

export interface RiskHorizonResponse {
  patient_id: string;
  as_of: string;
  data_coverage_pct: number;
  per_source_coverage: Record<string, number>;
  peak_risk_window: PeakRiskWindow;
  series: RiskHorizonPoint[];
  nocturnal_dipping_pct?: number | null;
  morning_surge_magnitude: number;
  risk_summary_text: string;
}

export interface FactorChangeItem {
  feature: string;
  display_name: string;
  current_value: number;
  previous_value: number;
  impact_delta: number;
  direction: "increased_risk" | "decreased_risk" | "neutral";
  clinical_explanation: string;
}

export interface WhyRiskChangedResponse {
  patient_id: string;
  current_risk_pct: number;
  previous_risk_pct?: number | null;
  risk_delta_pct?: number | null;
  summary: string;
  factors: FactorChangeItem[];
  trust_statement: string;
}

export interface AlertResponse {
  alert_id: string;
  patient_id: string;
  prediction_id?: string | null;
  risk_level: "High" | "Moderate" | "Low";
  probability: number;
  message: string;
  created_at: string;
  status: "open" | "acknowledged" | "snoozed" | "false_positive";
  acknowledged_by?: string | null;
  acknowledged_at?: string | null;
  snoozed_until?: string | null;
  snooze_duration_minutes?: number | null;
  snooze_reason?: string | null;
}

export interface OperatingThresholdsResponse {
  moderate: number;
  high: number;
  source: string;
  cooldown_hours: number;
}

export interface WhatIfRequest {
  sleep_hours?: number;
  medication_taken?: boolean;
  steps?: number;
  stress_level?: "low" | "medium" | "high";
  delay_hours?: number;
}

export interface WhatIfResponse {
  patient_id: string;
  baseline_probability: number;
  new_probability: number;
  delta: number;
  baseline_risk_level: string;
  new_risk_level: string;
  new_band?: string;
  changed_features: Record<string, any>;
  effect_note?: string;
  disclaimer: string;
}

export interface SimulationStatusResponse {
  is_running: boolean;
  patient_count: number;
  step_seconds: number;
  current_simulated_date?: string | null;
  active_scenario?: string | null;
  ticks_completed: number;
  last_tick_duration_seconds?: number | null;
}

export interface SensorReadingItem {
  reading_id: string;
  patient_id: string;
  sensor_type: string;
  value: number;
  unit: string;
  recorded_at: string;
  ingested_at: string;
  source: string;
}

export interface DailyReadingItem {
  date: string;
  timestamp: string;
  sbp?: number | null;
  dbp?: number | null;
  sleep_duration?: number | null;
  sleep_efficiency?: number | null;
  hrv_rmssd?: number | null;
  resting_hr?: number | null;
  steps?: number | null;
  medication_taken?: number | null;
}

export interface PersonalBaseline30d {
  sbp?: number | null;
  dbp?: number | null;
  sleep_duration?: number | null;
  sleep_efficiency?: number | null;
  hrv_rmssd?: number | null;
  resting_hr?: number | null;
  steps?: number | null;
  medication_adherence?: number | null;
}

export interface ReadingsSeriesResponse {
  patient_id: string;
  days: number;
  timezone: string;
  baseline_30d: PersonalBaseline30d;
  series: DailyReadingItem[];
}

export interface FactorChangeItem {
  feature: string;
  display_name: string;
  current_value: number;
  previous_value: number;
  impact_delta: number;
  direction: "increased_risk" | "decreased_risk" | "neutral" | string;
  clinical_explanation: string;
}

export interface WhyRiskChangedResponse {
  patient_id: string;
  current_risk_pct: number;
  previous_risk_pct?: number | null;
  risk_delta_pct?: number | null;
  summary: string;
  factors: FactorChangeItem[];
  trust_statement: string;
}

