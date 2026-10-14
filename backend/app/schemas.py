"""Pydantic v2 schemas for NightWatch API validation and serialization."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# Base / Generic
# ==============================================================================

class MessageResponse(BaseModel):
    """Standard generic operational confirmation response."""
    status: str = "ok"
    message: str
    details: Optional[Dict[str, Any]] = None


# ==============================================================================
# Patient Schemas
# ==============================================================================

class PatientBase(BaseModel):
    name: str
    age: int = Field(ge=18, le=120)
    sex: str = Field(pattern="^(M|F)$")
    height_cm: float = Field(ge=100.0, le=250.0)
    weight_kg: float = Field(ge=30.0, le=300.0)
    bmi: float = Field(ge=10.0, le=70.0)
    archetype: str


class PatientSummary(PatientBase):
    patient_id: str
    created_at: datetime
    latest_risk_level: Optional[str] = "Low"
    latest_probability: Optional[float] = 0.15
    open_alerts_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PatientProfileDetail(PatientSummary):
    diagnoses: List[str] = []
    medications: List[str] = []
    baseline_hrv_rmssd: float = 35.0
    baseline_resting_hr: float = 68.0
    baseline_sleep_hours: float = 7.0
    baseline_sbp: float = 125.0
    baseline_dbp: float = 80.0


# ==============================================================================
# Sensor Reading Schemas
# ==============================================================================

class SensorReadingCreate(BaseModel):
    sensor_type: str = Field(description="sleep_duration, deep_sleep, rem_sleep, awakenings, sleep_efficiency, hrv_rmssd, resting_hr, steps, medication_taken, home_sbp, home_dbp")
    value: float
    unit: str
    recorded_at: datetime
    source: Optional[str] = "manual_or_wearable"


class SensorReadingResponse(SensorReadingCreate):
    reading_id: str
    patient_id: str
    ingested_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Prediction & Alert Schemas
# ==============================================================================

class TopFactor(BaseModel):
    feature: str
    display_name: str
    value: float
    impact: float
    is_risk_driver: bool
    reason: str


class PredictionResponse(BaseModel):
    prediction_id: str
    patient_id: str
    probability: float
    risk_level: str  # Low, Moderate, High
    model_version: str
    generated_at: datetime
    top_factors: List[TopFactor] = []
    feature_snapshot: Dict[str, float] = {}

    model_config = ConfigDict(from_attributes=True)


class AlertResponse(BaseModel):
    alert_id: str
    patient_id: str
    prediction_id: Optional[str] = None
    risk_level: str
    probability: float
    message: str
    created_at: datetime
    status: str  # open, acknowledged, snoozed, false_positive
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    snooze_duration_minutes: Optional[int] = None
    snooze_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AlertAcknowledgeRequest(BaseModel):
    clinician_name: str = "Dr. Clinician"
    comment: Optional[str] = None


class AlertSnoozeRequest(BaseModel):
    clinician_name: str = "Dr. Clinician"
    snooze_hours: float = Field(default=4.0, ge=0.5, le=72.0)
    reason: Optional[str] = None


class ThresholdsResponse(BaseModel):
    moderate: float
    high: float
    source: str = "validation"
    cooldown_hours: float = 24.0


class FalsePositiveRequest(BaseModel):
    clinician_name: str = "Dr. Clinician"
    reason: Optional[str] = None


class ClinicianNoteCreate(BaseModel):
    note: str
    alert_id: Optional[str] = None


class ClinicianNoteResponse(BaseModel):
    note_id: str
    patient_id: str
    alert_id: Optional[str] = None
    note: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BPRecheckRequest(BaseModel):
    instructions: Optional[str] = "Rest seated for 5 minutes and repeat seated cuff measurement"
    priority: str = "routine"  # routine, urgent


# ==============================================================================
# Risk Horizon & Why Risk Changed Schemas
# ==============================================================================

class RiskHorizonPoint(BaseModel):
    timestamp: str
    hour_offset: int
    is_predicted: bool
    risk_pct: float
    confidence_lower: float
    confidence_upper: float
    is_sleep_window: bool
    sleep_stage: Optional[str] = None
    has_bp_reading: bool = False
    measured_sbp: Optional[float] = None
    measured_dbp: Optional[float] = None
    predicted_sbp: Optional[float] = None
    has_medication_event: bool = False
    medication_name: Optional[str] = None
    is_missing_data: bool = False


class PeakRiskWindow(BaseModel):
    start: str
    end: str
    peak_risk_pct: float
    label: str


class RiskHorizonResponse(BaseModel):
    patient_id: str
    as_of: str
    data_coverage_pct: float
    per_source_coverage: Dict[str, float]
    peak_risk_window: PeakRiskWindow
    series: List[RiskHorizonPoint]
    nocturnal_dipping_pct: float
    morning_surge_magnitude: float
    risk_summary_text: str


class FactorChangeItem(BaseModel):
    feature: str
    display_name: str
    current_value: float
    previous_value: float
    impact_delta: float
    direction: str  # increased_risk, decreased_risk, neutral
    clinical_explanation: str


class WhyRiskChangedResponse(BaseModel):
    patient_id: str
    current_risk_pct: float
    previous_risk_pct: float
    risk_delta_pct: float
    summary: str
    factors: List[FactorChangeItem]
    trust_statement: str


# ==============================================================================
# Digital Twin State Schema
# ==============================================================================

class DynamicState(BaseModel):
    latest_sbp: float
    latest_dbp: float
    sbp_7d_mean: float
    sleep_last_night: float
    sleep_efficiency: float
    hrv_last_night: float
    resting_hr_last_night: float
    steps_yesterday: int
    medication_taken_last_night: int


class StaticProfile(BaseModel):
    age: int
    sex: str
    bmi: float
    diagnoses: List[str]
    medications: List[str]
    baseline_hrv_30d: float
    baseline_sleep_30d: float


class RadarAxisValue(BaseModel):
    axis: str
    display_name: str
    baseline_value: float
    current_value: float
    deviation_pct: float
    status: str


class SleepFingerprintData(BaseModel):
    sleep_duration_deviation_pct: float
    sleep_efficiency_deviation_pct: float
    hrv_deviation_pct: float
    resting_hr_deviation_pct: float
    bp_stability_deviation_pct: float
    nocturnal_dipping_deviation_pct: float
    axes: List[RadarAxisValue] = []
    status: str  # optimal, degraded, acute_deficit
    summary: str


class DigitalTwinResponse(BaseModel):
    patient_id: str
    as_of: datetime
    static_profile: StaticProfile
    dynamic_state: DynamicState
    prediction: PredictionResponse
    sleep_fingerprint: SleepFingerprintData
    top_factors: List[TopFactor]
    recommended_actions: List[str]
    disclaimer: str


# ==============================================================================
# Counterfactual What-If Schemas
# ==============================================================================

class WhatIfRequest(BaseModel):
    sleep_hours: Optional[float] = Field(default=None, ge=4.0, le=9.0)
    medication_taken: Optional[bool] = None
    steps: Optional[int] = Field(default=None, ge=1000, le=12000)
    stress_level: Optional[str] = Field(default=None, description="low, medium, high")
    delay_hours: Optional[float] = Field(default=None, ge=0.0, le=24.0)


class WhatIfResponse(BaseModel):
    patient_id: str
    baseline_probability: float
    new_probability: float
    delta: float
    baseline_risk_level: str
    new_risk_level: str
    changed_features: Dict[str, Any]
    disclaimer: str


# ==============================================================================
# Simulation Schemas
# ==============================================================================

class SimulationStartRequest(BaseModel):
    step_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    patient_ids: Optional[List[str]] = None


class ScenarioInjectRequest(BaseModel):
    scenario: str = Field(description="force_poor_sleep, force_missed_dose, force_high_stress_sedentary, restore_optimal, clear")


class SimulationStatusResponse(BaseModel):
    is_running: bool
    patient_count: int
    step_seconds: float
    current_simulated_date: Optional[str] = None
    active_scenario: Optional[str] = None
    ticks_completed: int
