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
        last_s_val = recent_1d.get("evening_sbp") if pd.notna(recent_1d.get("evening_sbp")) else recent_1d.get("morning_sbp")
        feats["sbp_latest"] = float(last_s_val) if pd.notna(last_s_val) else float("nan")
        last_d_val = recent_1d.get("evening_dbp") if pd.notna(recent_1d.get("evening_dbp")) else recent_1d.get("morning_dbp")
        feats["dbp_latest"] = float(last_d_val) if pd.notna(last_d_val) else float("nan")

        sbp_series_3d = pd.concat([recent_3d["morning_sbp"], recent_3d["evening_sbp"]]).dropna()
        sbp_series_7d = pd.concat([recent_7d["morning_sbp"], recent_7d["evening_sbp"]]).dropna()
        dbp_series_7d = pd.concat([recent_7d["morning_dbp"], recent_7d["evening_dbp"]]).dropna()

        feats["sbp_mean_3d"] = float(sbp_series_3d.mean()) if not sbp_series_3d.empty else float("nan")
        feats["sbp_mean_7d"] = float(sbp_series_7d.mean()) if not sbp_series_7d.empty else float("nan")
        feats["sbp_std_7d"] = float(sbp_series_7d.std(ddof=1)) if len(sbp_series_7d) > 1 else float("nan")
        feats["dbp_mean_7d"] = float(dbp_series_7d.mean()) if not dbp_series_7d.empty else float("nan")

        # 7-day linear slope of SBP
        daily_sbp_7d = pd.concat([recent_7d["morning_sbp"], recent_7d["evening_sbp"]], axis=1).mean(axis=1).dropna()
        if len(daily_sbp_7d) >= 3:
            x_vals = np.arange(len(daily_sbp_7d))
            slope, _ = np.polyfit(x_vals, daily_sbp_7d.values, 1)
            feats["sbp_slope_7d"] = float(slope)
        else:
            feats["sbp_slope_7d"] = 0.0

        m_sbp_7d = recent_7d["morning_sbp"].dropna()
        e_sbp_7d = recent_7d["evening_sbp"].dropna()
        feats["morning_sbp_mean_7d"] = float(m_sbp_7d.mean()) if not m_sbp_7d.empty else float("nan")
        feats["evening_sbp_mean_7d"] = float(e_sbp_7d.mean()) if not e_sbp_7d.empty else float("nan")
        if pd.notna(feats["morning_sbp_mean_7d"]) and pd.notna(feats["evening_sbp_mean_7d"]):
            feats["morning_minus_evening_sbp"] = float(feats["morning_sbp_mean_7d"] - feats["evening_sbp_mean_7d"])
        else:
            feats["morning_minus_evening_sbp"] = float("nan")

        # Real days since last reading and actual count of readings
        all_sbp_nonnull = df[df["morning_sbp"].notna() | df["evening_sbp"].notna()]
        if not all_sbp_nonnull.empty and "day_index" in df.columns:
            last_reading_day = all_sbp_nonnull["day_index"].iloc[-1]
            current_day = df["day_index"].iloc[-1]
            feats["days_since_last_bp_reading"] = float(max(0, current_day - last_reading_day))
        else:
            feats["days_since_last_bp_reading"] = 0.0

        feats["bp_reading_count_7d"] = float(len(sbp_series_7d))

        # --- Sleep Architecture Features ---
        feats["sleep_duration_last_night"] = float(recent_1d["sleep_duration_hours"]) if pd.notna(recent_1d.get("sleep_duration_hours")) else float("nan")
        feats["deep_sleep_last_night"] = float(recent_1d["deep_sleep_hours"]) if pd.notna(recent_1d.get("deep_sleep_hours")) else float("nan")
        feats["rem_sleep_last_night"] = float(recent_1d["rem_sleep_hours"]) if pd.notna(recent_1d.get("rem_sleep_hours")) else float("nan")
        feats["awakenings_last_night"] = float(recent_1d["awakenings_count"]) if pd.notna(recent_1d.get("awakenings_count")) else float("nan")
        feats["sleep_efficiency_last_night"] = float(recent_1d["sleep_efficiency"]) if pd.notna(recent_1d.get("sleep_efficiency")) else float("nan")

        sleep_7d = recent_7d["sleep_duration_hours"].dropna()
        eff_7d = recent_7d["sleep_efficiency"].dropna()
        feats["sleep_duration_mean_7d"] = float(sleep_7d.mean()) if not sleep_7d.empty else float("nan")
        feats["sleep_efficiency_mean_7d"] = float(eff_7d.mean()) if not eff_7d.empty else float("nan")

        b_sleep_val = static_info.get("baseline_sleep_hours")
        base_sleep = float(b_sleep_val) if pd.notna(b_sleep_val) else 7.0
        feats["sleep_debt_7d"] = float(max(0.0, (base_sleep * len(sleep_7d)) - sleep_7d.sum())) if not sleep_7d.empty else float("nan")

        # Poor sleep streak (< 6.0 hours consecutive count)
        streak = 0
        for s_dur in reversed(sleep_7d.tolist()):
            if s_dur < 6.0:
                streak += 1
            else:
                break
        feats["poor_sleep_streak"] = float(streak)

        # 30-day z-scores
        sleep_30d = recent_30d["sleep_duration_hours"].dropna()
        if len(sleep_30d) > 1 and pd.notna(feats["sleep_duration_last_night"]):
            sleep_mean_30d = float(sleep_30d.mean())
            sleep_std_30d = float(sleep_30d.std(ddof=1)) or 0.6
            feats["sleep_duration_zscore_30d"] = float((feats["sleep_duration_last_night"] - sleep_mean_30d) / sleep_std_30d)
        else:
            feats["sleep_duration_zscore_30d"] = 0.0

        eff_30d = recent_30d["sleep_efficiency"].dropna()
        if len(eff_30d) > 1 and pd.notna(feats["sleep_efficiency_last_night"]):
            eff_mean_30d = float(eff_30d.mean())
            eff_std_30d = float(eff_30d.std(ddof=1)) or 0.05
            feats["sleep_efficiency_zscore_30d"] = float((feats["sleep_efficiency_last_night"] - eff_mean_30d) / eff_std_30d)
        else:
            feats["sleep_efficiency_zscore_30d"] = 0.0

        # --- Autonomic Tone (HRV & Resting HR) ---
        feats["hrv_rmssd_last_night"] = float(recent_1d["hrv_rmssd"]) if pd.notna(recent_1d.get("hrv_rmssd")) else float("nan")
        hrv_7d = recent_7d["hrv_rmssd"].dropna()
        feats["hrv_rmssd_mean_7d"] = float(hrv_7d.mean()) if not hrv_7d.empty else float("nan")

        hrv_30d = recent_30d["hrv_rmssd"].dropna()
        if len(hrv_30d) > 1 and pd.notna(feats["hrv_rmssd_last_night"]):
            hrv_mean_30d = float(hrv_30d.mean())
            hrv_std_30d = float(hrv_30d.std(ddof=1)) or 4.0
            feats["hrv_zscore_30d"] = float((feats["hrv_rmssd_last_night"] - hrv_mean_30d) / hrv_std_30d)
        else:
            feats["hrv_zscore_30d"] = 0.0

        b_hrv_val = static_info.get("baseline_hrv_rmssd")
        if pd.notna(b_hrv_val) and pd.notna(feats["hrv_rmssd_last_night"]):
            feats["hrv_drop_from_personal_baseline"] = float(max(0.0, float(b_hrv_val) - feats["hrv_rmssd_last_night"]))
        elif pd.notna(feats["hrv_rmssd_last_night"]) and not hrv_30d.empty:
            feats["hrv_drop_from_personal_baseline"] = float(max(0.0, float(hrv_30d.mean()) - feats["hrv_rmssd_last_night"]))
        else:
            feats["hrv_drop_from_personal_baseline"] = float("nan")

        feats["resting_hr_last_night"] = float(recent_1d["resting_hr"]) if pd.notna(recent_1d.get("resting_hr")) else float("nan")
        rhr_7d = recent_7d["resting_hr"].dropna()
        feats["resting_hr_mean_7d"] = float(rhr_7d.mean()) if not rhr_7d.empty else float("nan")

        rhr_30d = recent_30d["resting_hr"].dropna()
        if len(rhr_30d) > 1 and pd.notna(feats["resting_hr_last_night"]):
            rhr_mean_30d = float(rhr_30d.mean())
            rhr_std_30d = float(rhr_30d.std(ddof=1)) or 3.5
            feats["resting_hr_zscore_30d"] = float((feats["resting_hr_last_night"] - rhr_mean_30d) / rhr_std_30d)
        else:
            feats["resting_hr_zscore_30d"] = 0.0

        # --- Physical Activity & Medication Adherence ---
        feats["steps_yesterday"] = float(recent_1d["steps"]) if pd.notna(recent_1d.get("steps")) else float("nan")
        steps_7d = recent_7d["steps"].dropna()
        feats["steps_mean_7d"] = float(steps_7d.mean()) if not steps_7d.empty else float("nan")
        feats["active_minutes_yesterday"] = float(recent_1d["active_minutes"]) if pd.notna(recent_1d.get("active_minutes")) else float("nan")
        
        # Estimate sedentary hours as awake hours minus active hours
        if pd.notna(feats["sleep_duration_last_night"]) and pd.notna(feats["active_minutes_yesterday"]):
            awake_hours = max(4.0, 24.0 - feats["sleep_duration_last_night"])
            feats["sedentary_hours_yesterday"] = float(max(2.0, awake_hours - (feats["active_minutes_yesterday"] / 60.0)))
        else:
            feats["sedentary_hours_yesterday"] = float("nan")

        feats["medication_taken_last_night"] = float(recent_1d["medication_taken"]) if pd.notna(recent_1d.get("medication_taken")) else float("nan")
        med_7d = recent_7d["medication_taken"].dropna()
        feats["missed_doses_7d"] = float((med_7d == 0).sum()) if not med_7d.empty else float("nan")
        med_30d = recent_30d["medication_taken"].dropna()
        feats["adherence_rate_30d"] = float(med_30d.mean()) if not med_30d.empty else float("nan")
        if pd.notna(feats["medication_taken_last_night"]):
            feats["hours_since_last_medication"] = 12.0 if feats["medication_taken_last_night"] == 1.0 else 36.0
        else:
            feats["hours_since_last_medication"] = float("nan")

        # --- Baseline Deviations ---
        b_sbp_val = static_info.get("baseline_sbp")
        b_dbp_val = static_info.get("baseline_dbp")
        if pd.notna(b_sbp_val) and pd.notna(feats["sbp_mean_7d"]):
            feats["sbp_deviation_vs_30d_baseline"] = float(feats["sbp_mean_7d"] - float(b_sbp_val))
        else:
            feats["sbp_deviation_vs_30d_baseline"] = float("nan")

        if pd.notna(b_dbp_val) and pd.notna(feats["dbp_mean_7d"]):
            feats["dbp_deviation_vs_30d_baseline"] = float(feats["dbp_mean_7d"] - float(b_dbp_val))
        else:
            feats["dbp_deviation_vs_30d_baseline"] = float("nan")

        sbp_series_30d = pd.concat([recent_30d["morning_sbp"], recent_30d["evening_sbp"]]).dropna()
        std_30d = float(sbp_series_30d.std(ddof=1)) if len(sbp_series_30d) > 1 else float("nan")
        if pd.notna(feats["sbp_std_7d"]) and pd.notna(std_30d) and std_30d > 0.1:
            feats["bp_variability_ratio_7d_vs_30d"] = float(feats["sbp_std_7d"] / std_30d)
        else:
            feats["bp_variability_ratio_7d_vs_30d"] = 1.0

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
