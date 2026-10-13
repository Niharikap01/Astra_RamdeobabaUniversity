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
