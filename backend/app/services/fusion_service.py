"""Multimodal Data Fusion Service for NightWatch.

Aggregates asynchronous longitudinal sensor readings and home BP cuff readings
into aligned daily physiological summaries, feeding them into the unified
FeatureEngineeringPipeline to produce zero-leakage feature vectors.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models import SensorReading
from ml.feature_engineering import FeatureEngineeringPipeline

logger = logging.getLogger("nightwatch.fusion")


class FusionService:
    """Fuses static EHR with longitudinal wearable and home BP time-series."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.pipeline = FeatureEngineeringPipeline(feature_subset="full")

    def build_patient_history_df(self, patient_id: str, days_lookback: int = 45) -> pd.DataFrame:
        """Aggregate raw sensor readings into a structured daily historical DataFrame."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)

        readings = list(self.db.execute(
            select(SensorReading)
            .where(
                SensorReading.patient_id == patient_id,
                SensorReading.recorded_at >= cutoff_date,
            )
            .order_by(SensorReading.recorded_at.asc())
        ).scalars().all())

        if not readings:
            return pd.DataFrame()

        # Bucket readings by date string (YYYY-MM-DD)
        daily_buckets: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        for r in readings:
            date_str = r.recorded_at.strftime("%Y-%m-%d")
            daily_buckets[date_str][r.sensor_type].append(float(r.value))

        sorted_dates = sorted(daily_buckets.keys())
        daily_records: List[Dict[str, Any]] = []

        for idx, d_str in enumerate(sorted_dates):
            bucket = daily_buckets[d_str]

            # Parse morning vs evening BP strictly from actual stored readings without silent imputation
            sbp_readings = bucket.get("home_sbp", [])
            dbp_readings = bucket.get("home_dbp", [])

            if len(sbp_readings) >= 2:
                morning_sbp = sbp_readings[0]
                evening_sbp = sbp_readings[1]
            elif len(sbp_readings) == 1:
                morning_sbp = sbp_readings[0]
                evening_sbp = float("nan")
            else:
                morning_sbp = float("nan")
                evening_sbp = float("nan")

            if len(dbp_readings) >= 2:
                morning_dbp = dbp_readings[0]
                evening_dbp = dbp_readings[1]
            elif len(dbp_readings) == 1:
                morning_dbp = dbp_readings[0]
                evening_dbp = float("nan")
            else:
                morning_dbp = float("nan")
                evening_dbp = float("nan")

            def avg_or_nan(vals: List[float]) -> float:
                return float(sum(vals) / len(vals)) if vals else float("nan")

            sleep_dur = avg_or_nan(bucket.get("sleep_duration", []))
            deep_sleep = avg_or_nan(bucket.get("deep_sleep", []))
            rem_sleep = avg_or_nan(bucket.get("rem_sleep", []))
            awakenings = float(sum(bucket.get("awakenings", []))) if bucket.get("awakenings") else float("nan")
            sleep_eff = avg_or_nan(bucket.get("sleep_efficiency", []))
            hrv = avg_or_nan(bucket.get("hrv_rmssd", []))
            rhr = avg_or_nan(bucket.get("resting_hr", []))
            steps = float(sum(bucket.get("steps", []))) if bucket.get("steps") else float("nan")
            active_min = float(sum(bucket.get("active_minutes", []))) if bucket.get("active_minutes") else float("nan")
            med_taken = float(bucket.get("medication_taken")[0]) if bucket.get("medication_taken") else float("nan")

            daily_records.append({
                "patient_id": patient_id,
                "day_index": idx,
                "date": d_str,
                "sleep_duration_hours": sleep_dur,
                "deep_sleep_hours": deep_sleep,
                "rem_sleep_hours": rem_sleep,
                "awakenings_count": awakenings,
                "sleep_efficiency": sleep_eff,
                "hrv_rmssd": hrv,
                "resting_hr": rhr,
                "steps": steps,
                "active_minutes": active_min,
                "medication_taken": med_taken,
                "morning_sbp": round(morning_sbp, 1) if not pd.isna(morning_sbp) else float("nan"),
                "morning_dbp": round(morning_dbp, 1) if not pd.isna(morning_dbp) else float("nan"),
                "evening_sbp": round(evening_sbp, 1) if not pd.isna(evening_sbp) else float("nan"),
                "evening_dbp": round(evening_dbp, 1) if not pd.isna(evening_dbp) else float("nan"),
            })

        return pd.DataFrame(daily_records)

    def compute_data_coverage(self, patient_id: str, days_lookback: int = 7) -> Tuple[float, Dict[str, float]]:
        """Compute honest data coverage percentages from stored readings over lookback window."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        readings = list(self.db.execute(
            select(SensorReading)
            .where(
                SensorReading.patient_id == patient_id,
                SensorReading.recorded_at >= cutoff_date,
            )
        ).scalars().all())

        if not readings:
            return 0.0, {"home_bp_cuff": 0.0, "smart_ring": 0.0, "smart_pillbox": 0.0}

        # Expected counts over days_lookback:
        # Home BP: 2 readings per day (morning + evening) -> expected = days_lookback * 2
        # Smart Ring: sleep_duration (1/day) + hrv_rmssd (1/day) -> expected = days_lookback * 2
        # Smart Pillbox: medication_taken (1/day) -> expected = days_lookback * 1
        bp_count = sum(1 for r in readings if r.sensor_type in ("home_sbp", "home_dbp"))
        bp_events = bp_count / 2.0
        expected_bp = float(max(1, days_lookback * 2))
        bp_cov = min(100.0, round((bp_events / expected_bp) * 100.0, 1))

        ring_count = sum(1 for r in readings if r.sensor_type in ("sleep_duration", "hrv_rmssd", "resting_hr"))
        expected_ring = float(max(1, days_lookback * 2))
        ring_cov = min(100.0, round((ring_count / expected_ring) * 100.0, 1))

        med_count = sum(1 for r in readings if r.sensor_type == "medication_taken")
        expected_med = float(max(1, days_lookback * 1))
        med_cov = min(100.0, round((med_count / expected_med) * 100.0, 1))

        per_source = {
            "home_bp_cuff": bp_cov,
            "smart_ring": ring_cov,
            "smart_pillbox": med_cov,
        }
        overall_cov = round(sum(per_source.values()) / len(per_source), 1)
        return overall_cov, per_source

    def compute_current_features(
        self,
        static_dict: Dict[str, Any],
        history_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, float]:
        """Compute the complete multimodal feature vector as of current time."""
        patient_id = static_dict["patient_id"]
        if history_df is None:
            history_df = self.build_patient_history_df(patient_id, days_lookback=45)

        return self.pipeline.compute_features_from_history(
            static_info=static_dict,
            history_df=history_df,
        )
