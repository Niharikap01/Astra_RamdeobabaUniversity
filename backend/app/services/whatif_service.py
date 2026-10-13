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
            cf_features["sleep_duration_last_night"] = float(request.sleep_hours)
            changed_features["sleep_duration_last_night"] = {
                "before": round(old_sleep, 2),
                "after": round(request.sleep_hours, 2),
            }

            # Dependent recomputation: sleep debt, z-score, deep/rem estimates
            b_sleep = baseline_features.get("baseline_sleep_hours", 7.0)
            debt_delta = old_sleep - request.sleep_hours
            cf_features["sleep_debt_7d"] = float(max(0.0, cf_features.get("sleep_debt_7d", 0.0) + debt_delta))
            cf_features["sleep_duration_zscore_30d"] = float((request.sleep_hours - b_sleep) / 0.6)

            # Poor sleep streak adjustment
            if request.sleep_hours >= 6.5:
                cf_features["poor_sleep_streak"] = 0.0

            # Physiological coupling with HRV
            hrv_boost = (request.sleep_hours - old_sleep) * 2.5
            cf_features["hrv_rmssd_last_night"] = float(max(10.0, cf_features.get("hrv_rmssd_last_night", 35.0) + hrv_boost))
            cf_features["resting_hr_last_night"] = float(max(48.0, cf_features.get("resting_hr_last_night", 68.0) - (hrv_boost * 0.4)))

        # 2. Medication Adherence Override
        if request.medication_taken is not None:
            new_med = 1.0 if request.medication_taken else 0.0
            old_med = cf_features.get("medication_taken_last_night", 1.0)
            cf_features["medication_taken_last_night"] = new_med
            changed_features["medication_taken_last_night"] = {
                "before": int(old_med),
                "after": int(new_med),
            }
            cf_features["hours_since_last_medication"] = 12.0 if new_med == 1.0 else 36.0
            if new_med == 1.0 and old_med == 0.0:
                cf_features["missed_doses_7d"] = max(0.0, cf_features.get("missed_doses_7d", 1.0) - 1.0)

        # 3. Physical Steps Override (1000 to 12000)
        if request.steps is not None:
            old_steps = cf_features.get("steps_yesterday", 6000.0)
            cf_features["steps_yesterday"] = float(request.steps)
            changed_features["steps_yesterday"] = {
                "before": int(old_steps),
                "after": int(request.steps),
            }
            # Active minutes and sedentary hours derived
            cf_features["active_minutes_yesterday"] = float(max(10.0, request.steps / 110.0))
            awake_h = max(4.0, 24.0 - cf_features.get("sleep_duration_last_night", 7.0))
            cf_features["sedentary_hours_yesterday"] = float(max(2.0, awake_h - (cf_features["active_minutes_yesterday"] / 60.0)))

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

        return WhatIfResponse(
            patient_id=patient_id,
            baseline_probability=base_prob,
            new_probability=new_prob,
            delta=delta,
            baseline_risk_level=base_risk_level,
            new_risk_level=new_risk_level,
            changed_features=changed_features,
            disclaimer=settings.whatif_disclaimer,
        )
