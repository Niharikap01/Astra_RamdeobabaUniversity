"""Counterfactual What-If Simulation Engine for NightWatch."""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.schemas import WhatIfRequest, WhatIfResponse
from backend.app.services.prediction_service import PredictionService

logger = logging.getLogger("nightwatch.whatif")


class WhatIfService:
    """Simulates counterfactual clinical interventions with consistent dependent feature recomputation."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.pred_service = PredictionService(db)

    def run_counterfactual(
        self,
        patient_id: str,
        baseline_features: Dict[str, float],
        request: WhatIfRequest,
    ) -> WhatIfResponse:
        """Evaluate outcome probability under counterfactual parameter interventions."""
        # Baseline prediction
        base_prob, base_risk_level, _ = self.pred_service.score_features(baseline_features)

        # Clone feature vector for counterfactual overrides
        cf_features = copy.deepcopy(baseline_features)
        changed_features: Dict[str, Any] = {}

        # 1. Sleep Hours Override (4.0 to 9.0)
        if request.sleep_hours is not None:
            old_sleep = cf_features.get("sleep_duration_last_night", 7.0)
            target_sleep = float(request.sleep_hours)
            cf_features["sleep_duration_last_night"] = target_sleep
            cf_features["sleep_duration_mean_7d"] = target_sleep

            old_eff = cf_features.get("sleep_efficiency_last_night", 0.88)
            new_eff = float(min(0.96, max(0.60, 0.85 + (target_sleep - 7.0) * 0.03)))
            cf_features["sleep_efficiency_last_night"] = round(new_eff, 3)
            cf_features["sleep_efficiency_mean_7d"] = round(new_eff, 3)

            cf_features["deep_sleep_last_night"] = round(target_sleep * 0.20, 2)
            cf_features["rem_sleep_last_night"] = round(target_sleep * 0.22, 2)
            cf_features["awakenings_last_night"] = float(max(1.0, 4.0 - (target_sleep - 6.0)))

            b_sleep = baseline_features.get("baseline_sleep_hours", 7.0)
            cf_features["sleep_debt_7d"] = float(max(0.0, (b_sleep - target_sleep) * 7.0))
            cf_features["poor_sleep_streak"] = 0.0 if target_sleep >= 6.5 else 7.0
            cf_features["sleep_duration_zscore_30d"] = float((target_sleep - b_sleep) / 0.8)
            cf_features["sleep_efficiency_zscore_30d"] = float((new_eff - 0.85) / 0.08)

            b_hrv = baseline_features.get("baseline_hrv_rmssd", 35.0)
            b_rhr = baseline_features.get("baseline_resting_hr", 68.0)
            hrv_boost = (target_sleep - b_sleep) * 2.0
            new_hrv = float(max(10.0, b_hrv + hrv_boost))
            cf_features["hrv_rmssd_last_night"] = new_hrv
            cf_features["hrv_rmssd_mean_7d"] = new_hrv
            cf_features["hrv_zscore_30d"] = float((new_hrv - b_hrv) / 8.0)
            cf_features["hrv_drop_from_personal_baseline"] = float(max(0.0, b_hrv - new_hrv))

            new_rhr = float(max(48.0, b_rhr - (hrv_boost * 0.3)))
            cf_features["resting_hr_last_night"] = new_rhr
            cf_features["resting_hr_mean_7d"] = new_rhr
            cf_features["resting_hr_zscore_30d"] = float((new_rhr - b_rhr) / 5.0)

            changed_features["sleep_duration_last_night"] = {
                "before": round(old_sleep, 2),
                "after": round(target_sleep, 2),
                "sustained_7d_mean": round(target_sleep, 2),
            }
            changed_features["sleep_hours"] = changed_features["sleep_duration_last_night"]

        # 2. Medication Adherence Override
        if request.medication_taken is not None:
            old_med = cf_features.get("medication_taken_last_night", 1.0)
            new_med = 1.0 if request.medication_taken else 0.0
            cf_features["medication_taken_last_night"] = new_med
            if new_med == 1.0:
                cf_features["missed_doses_7d"] = 0.0
                cf_features["adherence_rate_30d"] = float(min(1.0, baseline_features.get("adherence_rate_30d", 0.85) + 0.15))
                cf_features["hours_since_last_medication"] = 12.0
            else:
                cf_features["missed_doses_7d"] = 7.0
                cf_features["adherence_rate_30d"] = float(max(0.0, baseline_features.get("adherence_rate_30d", 0.85) - 0.23))
                cf_features["hours_since_last_medication"] = 36.0

            changed_features["medication_taken_last_night"] = {
                "before": int(old_med),
                "after": int(new_med),
                "missed_doses_7d": cf_features["missed_doses_7d"],
                "hours_since_last_medication": cf_features["hours_since_last_medication"],
            }
            changed_features["medication_taken"] = changed_features["medication_taken_last_night"]

        # 3. Physical Steps Override (1000 to 12000)
        if request.steps is not None:
            old_steps = cf_features.get("steps_yesterday", 6000.0)
            target_steps = float(request.steps)
            cf_features["steps_yesterday"] = target_steps
            cf_features["steps_mean_7d"] = target_steps
            cf_features["active_minutes_yesterday"] = float(max(10.0, target_steps / 100.0))
            awake_h = max(4.0, 24.0 - cf_features.get("sleep_duration_last_night", 7.0))
            cf_features["sedentary_hours_yesterday"] = float(max(2.0, awake_h - (cf_features["active_minutes_yesterday"] / 60.0)))

            changed_features["steps_yesterday"] = {
                "before": int(old_steps),
                "after": int(target_steps),
                "sustained_7d_mean": int(target_steps),
            }
            changed_features["steps"] = changed_features["steps_yesterday"]

        # 4. Stress / Sodium Proxy
        if request.stress_level is not None:
            stress_map = {"low": 0.15, "medium": 0.50, "high": 0.85}
            level = stress_map.get(request.stress_level.lower(), 0.5)
            changed_features["stress_level_proxy"] = {"before": "current", "after": request.stress_level}
            if level > 0.6:
                cf_features["hrv_rmssd_last_night"] = max(10.0, cf_features.get("hrv_rmssd_last_night", 35.0) - 6.0)
                cf_features["resting_hr_last_night"] = cf_features.get("resting_hr_last_night", 68.0) + 4.0
            elif level < 0.3:
                cf_features["hrv_rmssd_last_night"] = cf_features.get("hrv_rmssd_last_night", 35.0) + 5.0
                cf_features["resting_hr_last_night"] = max(50.0, cf_features.get("resting_hr_last_night", 68.0) - 3.0)

        # 5. Delay Hours
        if request.delay_hours is not None:
            changed_features["medication_delay_hours"] = {"after": request.delay_hours}
            cf_features["hours_since_last_medication"] = float(request.delay_hours)

        # Score counterfactual scenario
        new_prob, new_risk_level, _ = self.pred_service.score_features(cf_features)
        delta = round(new_prob - base_prob, 4)

        if abs(delta) < 0.015:
            effect_note = (
                f"Modeled estimate shows a modest probability shift of {delta:+.1%}. "
                "Blood pressure history remains the primary risk driver; behavioral modulations produce minor short-term effects."
            )
        elif delta < 0:
            effect_note = (
                f"Modeled estimate shows an estimated risk reduction of {abs(delta):.1%} "
                "associated with sustained weekly adherence and lifestyle adjustments."
            )
        else:
            effect_note = (
                f"Modeled estimate shows an estimated risk increase of {delta:+.1%} "
                "associated with reduced recovery or missed therapy."
            )

        return WhatIfResponse(
            patient_id=patient_id,
            baseline_probability=base_prob,
            new_probability=new_prob,
            delta=delta,
            baseline_risk_level=base_risk_level,
            new_risk_level=new_risk_level,
            new_band=new_risk_level,
            changed_features=changed_features,
            effect_note=effect_note,
            disclaimer=settings.whatif_disclaimer,
        )
