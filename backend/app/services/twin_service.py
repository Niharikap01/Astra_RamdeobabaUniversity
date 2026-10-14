"""Digital Twin state orchestration and real-time live update pipeline."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.config import settings
from backend.app.models import Patient, Prediction
from backend.app.schemas import (
    DigitalTwinResponse,
    DynamicState,
    FactorChangeItem,
    PeakRiskWindow,
    PredictionResponse,
    RiskHorizonPoint,
    RiskHorizonResponse,
    SensorReadingCreate,
    StaticProfile,
    TopFactor,
    WhyRiskChangedResponse,
)
from backend.app.services.alert_service import AlertService
from backend.app.services.ehr_service import EHRService
from backend.app.services.fingerprint_service import FingerprintService
from backend.app.services.fusion_service import FusionService
from backend.app.services.prediction_service import PredictionService
from backend.app.services.sensor_service import SensorService
from backend.app.services.ws_manager import ws_manager

logger = logging.getLogger("nightwatch.twin")


class TwinService:
    """Constructs real-time patient digital twin state and coordinates live update broadcast."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.ehr_service = EHRService(db)
        self.sensor_service = SensorService(db)
        self.fusion_service = FusionService(db)
        self.pred_service = PredictionService(db)
        self.alert_service = AlertService(db)

    def build_twin(self, patient_id: str) -> Optional[DigitalTwinResponse]:
        """Construct the complete clinical Digital Twin state for a patient."""
        patient = self.ehr_service.get_patient(patient_id)
        if not patient:
            return None

        static_dict = self.ehr_service.get_patient_static_dict(patient)
        features_dict = self.fusion_service.compute_current_features(static_dict)

        # Get or generate latest prediction
        latest_pred = self.pred_service.get_latest_prediction(patient_id)
        if not latest_pred:
            latest_pred = self.pred_service.generate_and_save_prediction(patient_id, features_dict)
            self.alert_service.evaluate_and_create_alert(patient_id, latest_pred)

        # Construct sub-schemas without silent imputation
        import math
        def _safe_round(val: Any, digits: int = 1) -> Optional[float]:
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return None
            return round(float(val), digits)

        b_hrv_30d = _safe_round(static_dict.get("baseline_hrv_rmssd"), 1)
        b_sleep_30d = _safe_round(static_dict.get("baseline_sleep_hours"), 1)

        static_profile = StaticProfile(
            age=patient.age,
            sex=patient.sex,
            bmi=round(patient.bmi, 1),
            diagnoses=static_dict.get("diagnoses", []),
            medications=static_dict.get("medications", []),
            baseline_hrv_30d=b_hrv_30d,
            baseline_sleep_30d=b_sleep_30d,
        )

        steps_val = features_dict.get("steps_yesterday")
        steps_int = int(steps_val) if (steps_val is not None and not math.isnan(steps_val)) else None

        med_val = features_dict.get("medication_taken_last_night")
        med_int = int(med_val) if (med_val is not None and not math.isnan(med_val)) else None

        dynamic_state = DynamicState(
            latest_sbp=_safe_round(features_dict.get("sbp_latest"), 1),
            latest_dbp=_safe_round(features_dict.get("dbp_latest"), 1),
            sbp_7d_mean=_safe_round(features_dict.get("sbp_mean_7d"), 1),
            sleep_last_night=_safe_round(features_dict.get("sleep_duration_last_night"), 2),
            sleep_efficiency=_safe_round(features_dict.get("sleep_efficiency_last_night"), 3),
            hrv_last_night=_safe_round(features_dict.get("hrv_rmssd_last_night"), 1),
            resting_hr_last_night=_safe_round(features_dict.get("resting_hr_last_night"), 1),
            steps_yesterday=steps_int,
            medication_taken_last_night=med_int,
        )

        # Top factors and plain-language reasons
        top_factors_data = [
            TopFactor(
                feature=f.get("feature", ""),
                display_name=f.get("display_name", ""),
                value=float(f.get("value", 0.0)),
                impact=float(f.get("impact", 0.0)),
                is_risk_driver=bool(f.get("is_risk_driver", False)),
                reason=f.get("reason", ""),
            )
            for f in latest_pred.top_factors
        ]

        pred_resp = PredictionResponse(
            prediction_id=latest_pred.prediction_id,
            patient_id=patient_id,
            probability=round(latest_pred.probability, 4),
            risk_level=latest_pred.risk_level,
            model_version=latest_pred.model_version,
            generated_at=latest_pred.generated_at,
            top_factors=top_factors_data,
            feature_snapshot=latest_pred.feature_snapshot or {},
        )

        fingerprint = FingerprintService.compute_fingerprint(static_dict, features_dict)
        recommended_actions = self._generate_recommended_actions(patient, features_dict, latest_pred.probability)

        return DigitalTwinResponse(
            patient_id=patient_id,
            as_of=datetime.now(timezone.utc),
            static_profile=static_profile,
            dynamic_state=dynamic_state,
            prediction=pred_resp,
            sleep_fingerprint=fingerprint,
            top_factors=top_factors_data,
            recommended_actions=recommended_actions,
            disclaimer=settings.clinical_disclaimer,
        )

    async def process_new_reading_pipeline(
        self,
        patient_id: str,
        reading_create: SensorReadingCreate,
    ) -> DigitalTwinResponse:
        """Execute full event-driven update flow:
        persist -> fusion -> predict -> twin -> alert -> broadcast.
        """
        # 1. Idempotently persist reading
        self.sensor_service.add_reading(patient_id, reading_create)

        # 2. Recalculate fused features
        patient = self.ehr_service.get_patient(patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not found.")

        static_dict = self.ehr_service.get_patient_static_dict(patient)
        features_dict = self.fusion_service.compute_current_features(static_dict)

        # 3. Generate new prediction row
        prediction = self.pred_service.generate_and_save_prediction(patient_id, features_dict)

        # 4. Evaluate alert rule (probability >= 0.65 with cooldown)
        self.alert_service.evaluate_and_create_alert(patient_id, prediction)

        # 5. Build updated Twin state
        twin_state = self.build_twin(patient_id)
        assert twin_state is not None

        # 6. WebSocket broadcast to all connected dashboard clients
        twin_dict = twin_state.model_dump(mode="json")
        await ws_manager.broadcast_twin_update(patient_id, twin_dict)

        return twin_state

    def build_risk_horizon(self, patient_id: str) -> Optional[RiskHorizonResponse]:
        """Construct the 24-hour synchronized Risk Horizon trajectory using stored telemetry."""
        from zoneinfo import ZoneInfo
        import math
        from backend.app.models import SensorReading

        kolkata_tz = ZoneInfo("Asia/Kolkata")
        patient = self.ehr_service.get_patient(patient_id)
        if not patient:
            return None

        static_dict = self.ehr_service.get_patient_static_dict(patient)
        features_dict = self.fusion_service.compute_current_features(static_dict)

        latest_pred = self.pred_service.get_latest_prediction(patient_id)
        if not latest_pred:
            latest_pred = self.pred_service.generate_and_save_prediction(patient_id, features_dict, enforce_coverage=False)

        base_risk_pct = round(latest_pred.probability * 100.0, 1)

        # 1. Compute honest data coverage from stored readings
        overall_cov, per_source = self.fusion_service.compute_data_coverage(patient_id, days_lookback=1)

        # 2. Query stored sensor readings and past predictions in the last 24h
        now_utc = datetime.now(timezone.utc)
        start_24h_utc = now_utc - timedelta(hours=12)

        readings_24h = list(self.db.execute(
            select(SensorReading)
            .where(
                SensorReading.patient_id == patient_id,
                SensorReading.recorded_at >= start_24h_utc,
                SensorReading.recorded_at <= now_utc,
            )
            .order_by(SensorReading.recorded_at.asc())
        ).scalars().all())

        past_preds = list(self.db.execute(
            select(Prediction)
            .where(
                Prediction.patient_id == patient_id,
                Prediction.generated_at >= start_24h_utc,
                Prediction.generated_at <= now_utc,
            )
            .order_by(Prediction.generated_at.asc())
        ).scalars().all())

        series_points: List[RiskHorizonPoint] = []

        for offset in range(-12, 13):
            t_point_utc = now_utc + timedelta(hours=offset)
            t_point_kolkata = t_point_utc.astimezone(kolkata_tz)
            is_pred = offset > 0

            # Match readings within +/- 30 minutes of this hour
            window_start = t_point_utc - timedelta(minutes=30)
            window_end = t_point_utc + timedelta(minutes=30)
            slot_readings = []
            for r in readings_24h:
                r_ts = r.recorded_at if r.recorded_at.tzinfo is not None else r.recorded_at.replace(tzinfo=timezone.utc)
                if window_start <= r_ts <= window_end:
                    slot_readings.append(r)

            # Measured BP
            sbp_r = next((r.value for r in slot_readings if r.sensor_type == "home_sbp"), None)
            dbp_r = next((r.value for r in slot_readings if r.sensor_type == "home_dbp"), None)
            has_bp = sbp_r is not None

            # Medication event
            med_r = next((r for r in slot_readings if r.sensor_type == "medication_taken"), None)
            has_med = med_r is not None and med_r.value >= 1.0
            med_name = (patient.archetype.replace("_", " ").title() + " Regimen") if has_med else None

            # Sleep window detection from recorded sensor or hour
            sleep_r = next((r for r in slot_readings if r.sensor_type in ("sleep_duration", "deep_sleep", "rem_sleep")), None)
            hour_k = t_point_kolkata.hour
            is_sleep = sleep_r is not None or (23 <= hour_k or hour_k < 7)
            sleep_st = None
            if is_sleep:
                if 0 <= hour_k <= 2:
                    sleep_st = "deep"
                elif 3 <= hour_k <= 5:
                    sleep_st = "rem"
                else:
                    sleep_st = "light"

            # Risk trajectory
            if not is_pred:
                # Find closest stored prediction if any
                closest_pred = None
                min_diff = timedelta(hours=2)
                for p in past_preds:
                    p_ts = p.generated_at if p.generated_at.tzinfo is not None else p.generated_at.replace(tzinfo=timezone.utc)
                    diff = abs(p_ts - t_point_utc)
                    if diff < min_diff:
                        min_diff = diff
                        closest_pred = p

                if closest_pred is not None:
                    r_val = round(closest_pred.probability * 100.0, 1)
                else:
                    r_val = base_risk_pct

                conf_width = 3.5
                is_missing = len(slot_readings) == 0 and offset < 0
            else:
                r_val = base_risk_pct
                conf_width = min(22.0, 5.0 + (offset * 1.2))
                is_missing = False

            series_points.append(
                RiskHorizonPoint(
                    timestamp=t_point_kolkata.isoformat(),
                    hour_offset=offset,
                    is_predicted=is_pred,
                    risk_pct=round(r_val, 1),
                    confidence_lower=round(max(0.0, r_val - conf_width), 1),
                    confidence_upper=round(min(100.0, r_val + conf_width), 1),
                    is_sleep_window=is_sleep,
                    sleep_stage=sleep_st,
                    has_bp_reading=has_bp,
                    measured_sbp=round(sbp_r, 1) if sbp_r is not None else None,
                    measured_dbp=round(dbp_r, 1) if dbp_r is not None else None,
                    predicted_sbp=None,
                    has_medication_event=has_med,
                    medication_name=med_name,
                    is_missing_data=is_missing,
                )
            )

        # Peak risk window calculation
        pred_points = [p for p in series_points if p.is_predicted]
        peak_pt = max(pred_points, key=lambda x: x.risk_pct) if pred_points else series_points[-1]
        peak_window = PeakRiskWindow(
            start=peak_pt.timestamp,
            end=(datetime.fromisoformat(peak_pt.timestamp) + timedelta(hours=2)).isoformat(),
            peak_risk_pct=peak_pt.risk_pct,
            label="Anticipated Vulnerability Window",
        )

        # Morning surge magnitude computed honestly from features or 0.0
        m_sbp = features_dict.get("morning_sbp_mean_7d")
        e_sbp = features_dict.get("evening_sbp_mean_7d")
        if m_sbp is not None and e_sbp is not None and not (math.isnan(m_sbp) or math.isnan(e_sbp)):
            surge_mag = round(float(m_sbp - e_sbp), 1)
        else:
            surge_mag = 0.0

        if latest_pred.risk_level == "High":
            summary = (
                f"Elevated 24-hour hypertensive episode risk ({base_risk_pct:.0f}%). "
                f"Peak vulnerability ({peak_pt.risk_pct:.0f}%) projected over the next 12-hour horizon. "
                f"Associated with acute sleep deficit and diminished vagal HRV buffering."
            )
        elif latest_pred.risk_level == "Moderate":
            summary = (
                f"Moderate 24-hour hypertensive risk ({base_risk_pct:.0f}%). "
                f"Morning surge differential ({surge_mag:+.1f} mmHg) monitored against personal baseline."
            )
        else:
            summary = (
                f"Low 24-hour hypertensive episode risk ({base_risk_pct:.0f}%). "
                f"Stable autonomic tone and hemodynamic parameters observed."
            )

        return RiskHorizonResponse(
            patient_id=patient_id,
            as_of=now_utc.astimezone(kolkata_tz).isoformat(),
            data_coverage_pct=overall_cov,
            per_source_coverage=per_source,
            peak_risk_window=peak_window,
            series=series_points,
            nocturnal_dipping_pct=None,
            morning_surge_magnitude=surge_mag,
            risk_summary_text=summary,
        )

    def get_why_risk_changed(self, patient_id: str) -> Optional[WhyRiskChangedResponse]:
        """Produce clinician-oriented signed factor comparison by diffing two stored feature snapshots."""
        import math
        from ml.explain import FEATURE_DISPLAY_NAMES

        patient = self.ehr_service.get_patient(patient_id)
        if not patient:
            return None

        preds = self.pred_service.get_prediction_history(patient_id, limit=2)
        if not preds or len(preds) < 2:
            curr_risk = round(preds[0].probability * 100.0, 1) if preds else 0.0
            return WhyRiskChangedResponse(
                patient_id=patient_id,
                current_risk_pct=curr_risk,
                previous_risk_pct=None,
                risk_delta_pct=None,
                summary="No previous prediction exists.",
                factors=[],
                trust_statement="Attributions represent differences between stored feature snapshots and do not establish biological causality.",
            )

        curr_pred = preds[0]
        prev_pred = preds[1]

        curr_risk = round(curr_pred.probability * 100.0, 1)
        prev_risk = round(prev_pred.probability * 100.0, 1)
        delta_risk = round(curr_risk - prev_risk, 1)

        curr_snapshot = curr_pred.feature_snapshot or {}
        prev_snapshot = prev_pred.feature_snapshot or {}

        factors_list: List[FactorChangeItem] = []
        candidate_features = [k for k in curr_snapshot.keys() if not k.startswith("_")]
        diffs = []

        for feat in candidate_features:
            c_val = curr_snapshot.get(feat)
            p_val = prev_snapshot.get(feat)
            if c_val is not None and p_val is not None and not (math.isnan(c_val) or math.isnan(p_val)):
                change = float(c_val - p_val)
                if abs(change) > 1e-4:
                    diffs.append((feat, float(c_val), float(p_val), change))

        diffs.sort(key=lambda x: abs(x[3]), reverse=True)

        for feat, c_val, p_val, change in diffs[:6]:
            disp_name = FEATURE_DISPLAY_NAMES.get(feat, feat.replace("_", " ").title())
            higher_is_protective = feat in (
                "sleep_duration_last_night",
                "sleep_duration_mean_7d",
                "hrv_rmssd_last_night",
                "hrv_rmssd_mean_7d",
                "sleep_efficiency_last_night",
                "steps_mean_7d",
                "adherence_rate_30d",
            )
            if higher_is_protective:
                direction = "decreased_risk" if change > 0 else "increased_risk"
            else:
                direction = "increased_risk" if change > 0 else "decreased_risk"

            impact_score = round(abs(change) * (2.0 if "sbp" in feat else 1.0), 1)
            explanation = f"{disp_name} changed from {p_val:.1f} to {c_val:.1f} ({change:+.1f}), associated with {direction.replace('_', ' ')}."

            factors_list.append(
                FactorChangeItem(
                    feature=feat,
                    display_name=disp_name,
                    current_value=round(c_val, 2),
                    previous_value=round(p_val, 2),
                    impact_delta=impact_score,
                    direction=direction,
                    clinical_explanation=explanation,
                )
            )

        if delta_risk > 0:
            summary = f"Risk increased by {abs(delta_risk):.1f}% since previous evaluation, associated with changes in stored physiological features."
        elif delta_risk < 0:
            summary = f"Risk decreased by {abs(delta_risk):.1f}% compared to prior evaluation, associated with favorable feature trajectory."
        else:
            summary = "Risk remains unchanged from prior baseline interval."

        return WhyRiskChangedResponse(
            patient_id=patient_id,
            current_risk_pct=curr_risk,
            previous_risk_pct=prev_risk,
            risk_delta_pct=delta_risk,
            summary=summary,
            factors=factors_list,
            trust_statement="Attributions represent differences between stored feature snapshots and do not establish biological causality.",
        )

    def _generate_recommended_actions(
        self,
        patient: Patient,
        features: Dict[str, float],
        probability: float,
    ) -> List[str]:
        """Generate rule-based clinical suggestions (never autonomous prescriptions)."""
        suggestions: List[str] = []

        if probability >= settings.risk_threshold_high:
            suggestions.append("Priority: Schedule repeat home seated blood pressure measurement within 2 hours.")
            if features.get("medication_taken_last_night", 1.0) == 0.0:
                suggestions.append("Review medication compliance: Patient missed scheduled evening antihypertensive dose.")
            if features.get("sleep_duration_last_night", 7.0) < 5.5:
                suggestions.append("Autonomic caution: Documented acute sleep deficit (<5.5h) indicates heightened morning surge vulnerability.")
            suggestions.append("Consider clinician telephone outreach if daytime SBP exceeds 140 mmHg.")

        elif probability >= settings.risk_threshold_moderate:
            suggestions.append("Monitor blood pressure trend: Review evening home cuff log over the next 48 hours.")
            if features.get("sleep_debt_7d", 0.0) > 4.0:
                suggestions.append("Sleep hygiene counseling: 7-day cumulative sleep debt exceeds 4 hours.")
            if features.get("steps_yesterday", 6000.0) < 3000.0:
                suggestions.append("Activity encouragement: Sedentary pattern noted yesterday; advise light walking.")

        else:
            suggestions.append("Routine maintenance: Hemodynamic and autonomic parameters stable within personalized target bands.")
            suggestions.append("Continue current guideline-directed medical therapy and daily home cuff monitoring.")

        return suggestions
