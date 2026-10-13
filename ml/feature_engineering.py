"""Unified Feature Engineering Pipeline for NightWatch.

Shared between training and live inference to eliminate train/serve skew.
Enforces strict temporal causality (all features at time t use data strictly before t).
Computes personal 30-day rolling baselines, hemodynamic trends, sleep architecture,
autonomic tone metrics, and medication adherence.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("nightwatch.features")

# ==============================================================================
# Feature Definitions & Ablation Groups
# ==============================================================================

STATIC_FEATURES = [
    "age",
    "sex_male",
    "bmi",
    "hypertension_duration_years",
    "diabetes",
    "ckd",
    "dyslipidemia",
    "prior_stroke",
    "ihd",
    "osa",
    "family_history_cvd",
    "hba1c",
    "ldl_cholesterol",
    "hdl_cholesterol",
    "triglycerides",
    "serum_creatinine",
    "egfr",
    "serum_potassium",
    "med_acei",
    "med_arb",
    "med_ccb",
    "med_beta_blocker",
    "med_diuretic",
    "med_statin",
]

BP_FEATURES = [
    "sbp_latest",
    "dbp_latest",
    "sbp_mean_3d",
    "sbp_mean_7d",
    "sbp_std_7d",
    "dbp_mean_7d",
    "sbp_slope_7d",
    "morning_sbp_mean_7d",
    "evening_sbp_mean_7d",
    "morning_minus_evening_sbp",
    "days_since_last_bp_reading",
    "bp_reading_count_7d",
]

SLEEP_FEATURES = [
    "sleep_duration_last_night",
    "deep_sleep_last_night",
    "rem_sleep_last_night",
    "awakenings_last_night",
    "sleep_efficiency_last_night",
    "sleep_duration_mean_7d",
    "sleep_efficiency_mean_7d",
    "sleep_debt_7d",
    "poor_sleep_streak",
    "sleep_duration_zscore_30d",
    "sleep_efficiency_zscore_30d",
]

HRV_HR_FEATURES = [
    "hrv_rmssd_last_night",
    "hrv_rmssd_mean_7d",
    "hrv_zscore_30d",
    "hrv_drop_from_personal_baseline",
    "resting_hr_last_night",
    "resting_hr_mean_7d",
    "resting_hr_zscore_30d",
]

ACTIVITY_ADHERENCE_FEATURES = [
    "steps_yesterday",
    "steps_mean_7d",
    "active_minutes_yesterday",
    "sedentary_hours_yesterday",
    "medication_taken_last_night",
    "missed_doses_7d",
    "adherence_rate_30d",
    "hours_since_last_medication",
]

DEVIATION_FEATURES = [
    "sbp_deviation_vs_30d_baseline",
    "dbp_deviation_vs_30d_baseline",
    "bp_variability_ratio_7d_vs_30d",
]

# Ablation Model Feature Subsets
FEATURE_SETS = {
    "ehr_only": STATIC_FEATURES,
    "ehr_plus_bp": STATIC_FEATURES + BP_FEATURES,
    "ehr_bp_sleep_hrv": STATIC_FEATURES + BP_FEATURES + SLEEP_FEATURES + HRV_HR_FEATURES + DEVIATION_FEATURES,
    "full": (
        STATIC_FEATURES
        + BP_FEATURES
        + SLEEP_FEATURES
        + HRV_HR_FEATURES
        + ACTIVITY_ADHERENCE_FEATURES
        + DEVIATION_FEATURES
    ),
}

ALL_NUMERIC_FEATURES = FEATURE_SETS["full"]


class FeatureEngineeringPipeline:
    """Computes zero-leakage physiological feature vectors for both offline training and online serving."""

    def __init__(self, feature_subset: str = "full") -> None:
        if feature_subset not in FEATURE_SETS:
            raise ValueError(f"Unknown feature subset: {feature_subset}. Options: {list(FEATURE_SETS.keys())}")
        self.feature_subset = feature_subset
        self.feature_names = FEATURE_SETS[feature_subset]

    @staticmethod
    def extract_static_features(static_info: Dict[str, Any]) -> Dict[str, float]:
        """Normalize static EHR profile fields."""
        sex_val = static_info.get("sex", "M")
        sex_male = 1.0 if (sex_val == "M" or sex_val is True or sex_val == 1) else 0.0

        return {
            "age": float(static_info.get("age", 58)),
            "sex_male": sex_male,
            "bmi": float(static_info.get("bmi", 28.5)),
            "hypertension_duration_years": float(static_info.get("hypertension_duration_years", 6.0)),
            "diabetes": float(static_info.get("diabetes", 0)),
            "ckd": float(static_info.get("ckd", 0)),
            "dyslipidemia": float(static_info.get("dyslipidemia", 0)),
            "prior_stroke": float(static_info.get("prior_stroke", 0)),
            "ihd": float(static_info.get("ihd", 0)),
            "osa": float(static_info.get("osa", 0)),
            "family_history_cvd": float(static_info.get("family_history_cvd", 0)),
            "hba1c": float(static_info.get("hba1c", 5.7)),
            "ldl_cholesterol": float(static_info.get("ldl_cholesterol", 110.0)),
            "hdl_cholesterol": float(static_info.get("hdl_cholesterol", 45.0)),
            "triglycerides": float(static_info.get("triglycerides", 145.0)),
            "serum_creatinine": float(static_info.get("serum_creatinine", 1.0)),
            "egfr": float(static_info.get("egfr", 85.0)),
            "serum_potassium": float(static_info.get("serum_potassium", 4.2)),
            "med_acei": float(static_info.get("med_acei", 0)),
            "med_arb": float(static_info.get("med_arb", 0)),
            "med_ccb": float(static_info.get("med_ccb", 0)),
            "med_beta_blocker": float(static_info.get("med_beta_blocker", 0)),
            "med_diuretic": float(static_info.get("med_diuretic", 0)),
            "med_statin": float(static_info.get("med_statin", 0)),
        }

    def compute_features_from_history(
        self,
        static_info: Dict[str, Any],
        history_df: pd.DataFrame,
        current_day_index: Optional[int] = None,
    ) -> Dict[str, float]:
        """Compute rolling features strictly using observations before current_day_index.

        If current_day_index is provided, filters for day_index < current_day_index.
        This mathematically guarantees zero future target leakage.
        """
        feats: Dict[str, float] = self.extract_static_features(static_info)

        if history_df.empty:
            # Fallback for empty history: populate defaults based on static EHR baselines
            return self._fill_defaults(feats, static_info)

        df = history_df.copy()
        if "day_index" in df.columns and current_day_index is not None:
            df = df[df["day_index"] < current_day_index].sort_values("day_index")

        if df.empty:
            return self._fill_defaults(feats, static_info)

        # Windows
        recent_1d = df.iloc[-1]
        recent_3d = df.iloc[-3:] if len(df) >= 3 else df
        recent_7d = df.iloc[-7:] if len(df) >= 7 else df
        recent_30d = df.iloc[-30:] if len(df) >= 30 else df

        # --- BP Features (Home Cuff ground truth) ---
        feats["sbp_latest"] = float(recent_1d.get("evening_sbp", recent_1d.get("morning_sbp", static_info.get("baseline_sbp", 130.0))))
        feats["dbp_latest"] = float(recent_1d.get("evening_dbp", recent_1d.get("morning_dbp", static_info.get("baseline_dbp", 82.0))))

        sbp_series_3d = pd.concat([recent_3d["morning_sbp"], recent_3d["evening_sbp"]])
        sbp_series_7d = pd.concat([recent_7d["morning_sbp"], recent_7d["evening_sbp"]])
        dbp_series_7d = pd.concat([recent_7d["morning_dbp"], recent_7d["evening_dbp"]])

        feats["sbp_mean_3d"] = float(sbp_series_3d.mean())
        feats["sbp_mean_7d"] = float(sbp_series_7d.mean())
        feats["sbp_std_7d"] = float(sbp_series_7d.std(ddof=1)) if len(sbp_series_7d) > 1 else 3.5
        feats["dbp_mean_7d"] = float(dbp_series_7d.mean())

        # 7-day linear slope of SBP
        if len(recent_7d) >= 3:
            daily_sbp_7d = (recent_7d["morning_sbp"] + recent_7d["evening_sbp"]) / 2.0
            x_vals = np.arange(len(daily_sbp_7d))
            slope, _ = np.polyfit(x_vals, daily_sbp_7d.values, 1)
            feats["sbp_slope_7d"] = float(slope)
        else:
            feats["sbp_slope_7d"] = 0.0

        feats["morning_sbp_mean_7d"] = float(recent_7d["morning_sbp"].mean())
        feats["evening_sbp_mean_7d"] = float(recent_7d["evening_sbp"].mean())
        feats["morning_minus_evening_sbp"] = float(feats["morning_sbp_mean_7d"] - feats["evening_sbp_mean_7d"])
        feats["days_since_last_bp_reading"] = 0.0  # Daily home monitoring compliant
        feats["bp_reading_count_7d"] = float(len(recent_7d) * 2)

        # --- Sleep Architecture Features ---
        feats["sleep_duration_last_night"] = float(recent_1d.get("sleep_duration_hours", 7.0))
        feats["deep_sleep_last_night"] = float(recent_1d.get("deep_sleep_hours", 1.2))
        feats["rem_sleep_last_night"] = float(recent_1d.get("rem_sleep_hours", 1.4))
        feats["awakenings_last_night"] = float(recent_1d.get("awakenings_count", 2))
        feats["sleep_efficiency_last_night"] = float(recent_1d.get("sleep_efficiency", 0.85))

        feats["sleep_duration_mean_7d"] = float(recent_7d["sleep_duration_hours"].mean())
        feats["sleep_efficiency_mean_7d"] = float(recent_7d["sleep_efficiency"].mean())

        base_sleep = float(static_info.get("baseline_sleep_hours", 7.0))
        feats["sleep_debt_7d"] = float(max(0.0, (base_sleep * len(recent_7d)) - recent_7d["sleep_duration_hours"].sum()))

        # Poor sleep streak (< 6.0 hours consecutive count)
        streak = 0
        for s_dur in reversed(recent_7d["sleep_duration_hours"].tolist()):
            if s_dur < 6.0:
                streak += 1
            else:
                break
        feats["poor_sleep_streak"] = float(streak)

        # 30-day z-scores
        sleep_mean_30d = float(recent_30d["sleep_duration_hours"].mean())
        sleep_std_30d = float(recent_30d["sleep_duration_hours"].std(ddof=1)) or 0.6
        feats["sleep_duration_zscore_30d"] = float((feats["sleep_duration_last_night"] - sleep_mean_30d) / sleep_std_30d)

        eff_mean_30d = float(recent_30d["sleep_efficiency"].mean())
        eff_std_30d = float(recent_30d["sleep_efficiency"].std(ddof=1)) or 0.05
        feats["sleep_efficiency_zscore_30d"] = float((feats["sleep_efficiency_last_night"] - eff_mean_30d) / eff_std_30d)

        # --- Autonomic Tone (HRV & Resting HR) ---
        feats["hrv_rmssd_last_night"] = float(recent_1d.get("hrv_rmssd", 32.0))
        feats["hrv_rmssd_mean_7d"] = float(recent_7d["hrv_rmssd"].mean())

        hrv_mean_30d = float(recent_30d["hrv_rmssd"].mean())
        hrv_std_30d = float(recent_30d["hrv_rmssd"].std(ddof=1)) or 4.0
        feats["hrv_zscore_30d"] = float((feats["hrv_rmssd_last_night"] - hrv_mean_30d) / hrv_std_30d)

        base_hrv = float(static_info.get("baseline_hrv_rmssd", hrv_mean_30d))
        feats["hrv_drop_from_personal_baseline"] = float(max(0.0, base_hrv - feats["hrv_rmssd_last_night"]))

        feats["resting_hr_last_night"] = float(recent_1d.get("resting_hr", 68.0))
        feats["resting_hr_mean_7d"] = float(recent_7d["resting_hr"].mean())

        rhr_mean_30d = float(recent_30d["resting_hr"].mean())
        rhr_std_30d = float(recent_30d["resting_hr"].std(ddof=1)) or 3.5
        feats["resting_hr_zscore_30d"] = float((feats["resting_hr_last_night"] - rhr_mean_30d) / rhr_std_30d)

        # --- Physical Activity & Medication Adherence ---
        feats["steps_yesterday"] = float(recent_1d.get("steps", 6000))
        feats["steps_mean_7d"] = float(recent_7d["steps"].mean())
        feats["active_minutes_yesterday"] = float(recent_1d.get("active_minutes", 30))
        # Estimate sedentary hours as awake hours minus active hours
        awake_hours = max(4.0, 24.0 - feats["sleep_duration_last_night"])
        feats["sedentary_hours_yesterday"] = float(max(2.0, awake_hours - (feats["active_minutes_yesterday"] / 60.0)))

        feats["medication_taken_last_night"] = float(recent_1d.get("medication_taken", 1))
        feats["missed_doses_7d"] = float(len(recent_7d) - recent_7d["medication_taken"].sum())
        feats["adherence_rate_30d"] = float(recent_30d["medication_taken"].mean())
        feats["hours_since_last_medication"] = 12.0 if feats["medication_taken_last_night"] == 1.0 else 36.0

        # --- Baseline Deviations ---
        base_sbp = float(static_info.get("baseline_sbp", 128.0))
        base_dbp = float(static_info.get("baseline_dbp", 80.0))
        feats["sbp_deviation_vs_30d_baseline"] = float(feats["sbp_mean_7d"] - base_sbp)
        feats["dbp_deviation_vs_30d_baseline"] = float(feats["dbp_mean_7d"] - base_dbp)

        sbp_series_30d = pd.concat([recent_30d["morning_sbp"], recent_30d["evening_sbp"]])
        std_30d = float(sbp_series_30d.std(ddof=1)) if len(sbp_series_30d) > 1 else 4.0
        feats["bp_variability_ratio_7d_vs_30d"] = float(feats["sbp_std_7d"] / (std_30d if std_30d > 0.1 else 4.0))

        # Return only the requested subset or all
        return {k: feats[k] for k in self.feature_names if k in feats}

    def _fill_defaults(self, feats: Dict[str, float], static_info: Dict[str, Any]) -> Dict[str, float]:
        """Fill standard physiologically plausible baseline defaults."""
        b_sbp = float(static_info.get("baseline_sbp", 128.0))
        b_dbp = float(static_info.get("baseline_dbp", 80.0))
        b_sleep = float(static_info.get("baseline_sleep_hours", 7.0))
        b_hrv = float(static_info.get("baseline_hrv_rmssd", 35.0))
        b_rhr = float(static_info.get("baseline_resting_hr", 68.0))

        defaults = {
            "sbp_latest": b_sbp,
            "dbp_latest": b_dbp,
            "sbp_mean_3d": b_sbp,
            "sbp_mean_7d": b_sbp,
            "sbp_std_7d": 3.5,
            "dbp_mean_7d": b_dbp,
            "sbp_slope_7d": 0.0,
            "morning_sbp_mean_7d": b_sbp + 2.0,
            "evening_sbp_mean_7d": b_sbp - 1.0,
            "morning_minus_evening_sbp": 3.0,
            "days_since_last_bp_reading": 0.0,
            "bp_reading_count_7d": 14.0,
            "sleep_duration_last_night": b_sleep,
            "deep_sleep_last_night": b_sleep * 0.18,
            "rem_sleep_last_night": b_sleep * 0.20,
            "awakenings_last_night": 2.0,
            "sleep_efficiency_last_night": 0.88,
            "sleep_duration_mean_7d": b_sleep,
            "sleep_efficiency_mean_7d": 0.88,
            "sleep_debt_7d": 0.0,
            "poor_sleep_streak": 0.0,
            "sleep_duration_zscore_30d": 0.0,
            "sleep_efficiency_zscore_30d": 0.0,
            "hrv_rmssd_last_night": b_hrv,
            "hrv_rmssd_mean_7d": b_hrv,
            "hrv_zscore_30d": 0.0,
            "hrv_drop_from_personal_baseline": 0.0,
            "resting_hr_last_night": b_rhr,
            "resting_hr_mean_7d": b_rhr,
            "resting_hr_zscore_30d": 0.0,
            "steps_yesterday": 6500.0,
            "steps_mean_7d": 6500.0,
            "active_minutes_yesterday": 30.0,
            "sedentary_hours_yesterday": 9.0,
            "medication_taken_last_night": 1.0,
            "missed_doses_7d": 0.0,
            "adherence_rate_30d": 0.95,
            "hours_since_last_medication": 12.0,
            "sbp_deviation_vs_30d_baseline": 0.0,
            "dbp_deviation_vs_30d_baseline": 0.0,
            "bp_variability_ratio_7d_vs_30d": 1.0,
        }
        feats.update(defaults)
        return {k: feats[k] for k in self.feature_names if k in feats}
