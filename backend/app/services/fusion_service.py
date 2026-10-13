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

            # Parse morning vs evening BP if multiple readings present
            sbp_readings = bucket.get("home_sbp", [])
            dbp_readings = bucket.get("home_dbp", [])

            if len(sbp_readings) >= 2:
                morning_sbp = sbp_readings[0]
                evening_sbp = sbp_readings[1]
            elif len(sbp_readings) == 1:
                morning_sbp = sbp_readings[0]
                evening_sbp = sbp_readings[0] - 2.0
            else:
                morning_sbp = 125.0
                evening_sbp = 123.0

            if len(dbp_readings) >= 2:
                morning_dbp = dbp_readings[0]
                evening_dbp = dbp_readings[1]
            elif len(dbp_readings) == 1:
                morning_dbp = dbp_readings[0]
                evening_dbp = dbp_readings[0] - 1.5
            else:
                morning_dbp = 80.0
                evening_dbp = 78.5

            def avg_or(vals: List[float], default: float) -> float:
                return float(sum(vals) / len(vals)) if vals else default

            daily_records.append({
                "patient_id": patient_id,
                "day_index": idx,
                "date": d_str,
                "sleep_duration_hours": avg_or(bucket.get("sleep_duration"), 7.0),
                "deep_sleep_hours": avg_or(bucket.get("deep_sleep"), 1.2),
                "rem_sleep_hours": avg_or(bucket.get("rem_sleep"), 1.4),
                "awakenings_count": int(avg_or(bucket.get("awakenings"), 2.0)),
                "sleep_efficiency": avg_or(bucket.get("sleep_efficiency"), 0.85),
                "hrv_rmssd": avg_or(bucket.get("hrv_rmssd"), 35.0),
                "resting_hr": avg_or(bucket.get("resting_hr"), 68.0),
                "steps": int(avg_or(bucket.get("steps"), 6000.0)),
                "active_minutes": int(avg_or(bucket.get("active_minutes"), 30.0)),
                "medication_taken": int(avg_or(bucket.get("medication_taken"), 1.0)),
                "morning_sbp": round(morning_sbp, 1),
                "morning_dbp": round(morning_dbp, 1),
                "evening_sbp": round(evening_sbp, 1),
                "evening_dbp": round(evening_dbp, 1),
            })

        return pd.DataFrame(daily_records)

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
