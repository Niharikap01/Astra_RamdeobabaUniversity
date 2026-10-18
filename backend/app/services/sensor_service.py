"""Sensor and home BP cuff ingestion and query service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError

from backend.app.models import SensorReading
from backend.app.schemas import SensorReadingCreate

logger = logging.getLogger("nightwatch.sensor")


class SensorService:
    """Manages idempotent time-series ingestion and retrieval of wearable and cuff telemetry."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add_reading(self, patient_id: str, reading: SensorReadingCreate) -> SensorReading:
        """Idempotently ingest a single sensor reading."""
        # Ensure UTC timezone awareness
        rec_time = reading.recorded_at
        if rec_time.tzinfo is None:
            rec_time = rec_time.replace(tzinfo=timezone.utc)

        # Check existing reading for idempotency
        existing = self.db.execute(
            select(SensorReading).where(
                SensorReading.patient_id == patient_id,
                SensorReading.sensor_type == reading.sensor_type,
                SensorReading.recorded_at == rec_time,
            )
        ).scalar_one_or_none()

        if existing:
            # Update value idempotently
            existing.value = reading.value
            existing.unit = reading.unit
            existing.ingested_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        db_reading = SensorReading(
            patient_id=patient_id,
            sensor_type=reading.sensor_type,
            value=reading.value,
            unit=reading.unit,
            recorded_at=rec_time,
            ingested_at=datetime.now(timezone.utc),
            source=reading.source or "manual_or_wearable",
        )
        try:
            self.db.add(db_reading)
            self.db.commit()
            self.db.refresh(db_reading)
            return db_reading
        except IntegrityError:
            self.db.rollback()
            existing = self.db.execute(
                select(SensorReading).where(
                    SensorReading.patient_id == patient_id,
                    SensorReading.sensor_type == reading.sensor_type,
                    SensorReading.recorded_at == rec_time,
                )
            ).scalar_one()
            return existing

    def get_patient_readings(
        self,
        patient_id: str,
        sensor_type: Optional[str] = None,
        limit: int = 200,
    ) -> List[SensorReading]:
        """Fetch chronologically descending sensor readings for a patient."""
        query = select(SensorReading).where(SensorReading.patient_id == patient_id)
        if sensor_type:
            query = query.where(SensorReading.sensor_type == sensor_type)
        query = query.order_by(desc(SensorReading.recorded_at)).limit(limit)
        return list(self.db.execute(query).scalars().all())

    def get_readings_series(
        self,
        patient_id: str,
        days: int = 30,
    ):
        """Retrieve stored readings series in Asia/Kolkata timezone with personal 30d baseline."""
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        import numpy as np
        from backend.app.schemas import DailyReadingItem, PersonalBaseline30d, ReadingsSeriesResponse

        kolkata_tz = ZoneInfo("Asia/Kolkata")
        now_utc = datetime.now(timezone.utc)
        now_kolkata = now_utc.astimezone(kolkata_tz)

        lookback_days = max(days, 30)
        cutoff_date = (now_utc - timedelta(days=lookback_days + 1))

        readings = list(self.db.execute(
            select(SensorReading)
            .where(
                SensorReading.patient_id == patient_id,
                SensorReading.recorded_at >= cutoff_date,
            )
            .order_by(SensorReading.recorded_at.asc())
        ).scalars().all())

        cutoff_30d = now_utc - timedelta(days=30)
        readings_30d = [
            r for r in readings
            if (r.recorded_at if r.recorded_at.tzinfo is not None else r.recorded_at.replace(tzinfo=timezone.utc)) >= cutoff_30d
        ]

        def _mean_val(stype: str) -> Optional[float]:
            vals = [r.value for r in readings_30d if r.sensor_type == stype]
            return round(float(np.mean(vals)), 1) if vals else None

        med_vals = [r.value for r in readings_30d if r.sensor_type == "medication_taken"]
        med_adh = round(float(np.mean(med_vals)), 2) if med_vals else None

        baseline_30d = PersonalBaseline30d(
            sbp=_mean_val("home_sbp"),
            dbp=_mean_val("home_dbp"),
            sleep_duration=_mean_val("sleep_duration"),
            sleep_efficiency=round(float(np.mean([r.value for r in readings_30d if r.sensor_type == "sleep_efficiency"])), 3) if any(r.sensor_type == "sleep_efficiency" for r in readings_30d) else None,
            hrv_rmssd=_mean_val("hrv_rmssd"),
            resting_hr=_mean_val("resting_hr"),
            steps=round(float(np.mean([r.value for r in readings_30d if r.sensor_type == "steps"])), 0) if any(r.sensor_type == "steps" for r in readings_30d) else None,
            medication_adherence=med_adh,
        )

        daily_readings_map = {}
        for r in readings:
            r_time = r.recorded_at if r.recorded_at.tzinfo is not None else r.recorded_at.replace(tzinfo=timezone.utc)
            r_kolkata = r_time.astimezone(kolkata_tz)
            date_key = r_kolkata.strftime("%Y-%m-%d")
            if date_key not in daily_readings_map:
                daily_readings_map[date_key] = {}
            if r.sensor_type not in daily_readings_map[date_key]:
                daily_readings_map[date_key][r.sensor_type] = []
            daily_readings_map[date_key][r.sensor_type].append(r.value)

        series = []
        start_date_kolkata = (now_kolkata - timedelta(days=days - 1)).date()
        for i in range(days):
            day_date = start_date_kolkata + timedelta(days=i)
            date_str = day_date.strftime("%Y-%m-%d")
            day_dt = datetime(day_date.year, day_date.month, day_date.day, 12, 0, 0, tzinfo=kolkata_tz)
            day_dict = daily_readings_map.get(date_str, {})

            sbp_vals = day_dict.get("home_sbp", [])
            dbp_vals = day_dict.get("home_dbp", [])
            sleep_vals = day_dict.get("sleep_duration", [])
            eff_vals = day_dict.get("sleep_efficiency", [])
            hrv_vals = day_dict.get("hrv_rmssd", [])
            rhr_vals = day_dict.get("resting_hr", [])
            step_vals = day_dict.get("steps", [])
            med_vals_day = day_dict.get("medication_taken", [])

            series.append(DailyReadingItem(
                date=date_str,
                timestamp=day_dt.isoformat(),
                sbp=round(float(np.mean(sbp_vals)), 1) if sbp_vals else None,
                dbp=round(float(np.mean(dbp_vals)), 1) if dbp_vals else None,
                sleep_duration=round(float(sleep_vals[-1]), 2) if sleep_vals else None,
                sleep_efficiency=round(float(eff_vals[-1]), 3) if eff_vals else None,
                hrv_rmssd=round(float(hrv_vals[-1]), 1) if hrv_vals else None,
                resting_hr=round(float(rhr_vals[-1]), 1) if rhr_vals else None,
                steps=int(step_vals[-1]) if step_vals else None,
                medication_taken=int(med_vals_day[-1]) if med_vals_day else None,
            ))

        return ReadingsSeriesResponse(
            patient_id=patient_id,
            days=days,
            timezone="Asia/Kolkata",
            baseline_30d=baseline_30d,
            series=series,
        )
