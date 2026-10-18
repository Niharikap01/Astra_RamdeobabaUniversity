"""Sensor reading ingestion and historical time-series queries."""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import ReadingsSeriesResponse, SensorReadingCreate, SensorReadingResponse
from backend.app.services.ehr_service import EHRService
from backend.app.services.sensor_service import SensorService
from backend.app.services.twin_service import TwinService

router = APIRouter(prefix="/api/patients", tags=["Sensor Readings"])


@router.get("/{patient_id}/readings-series", response_model=ReadingsSeriesResponse)
def get_readings_series(
    patient_id: str,
    days: int = Query(default=30, ge=1, le=120),
    db: Session = Depends(get_db),
):
    """Retrieve stored readings series in Asia/Kolkata timezone with personal 30-day baseline."""
    ehr = EHRService(db)
    if not ehr.get_patient(patient_id):
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    sensor_svc = SensorService(db)
    return sensor_svc.get_readings_series(patient_id, days=days)


@router.get("/{patient_id}/sensor-readings", response_model=List[SensorReadingResponse])
def get_sensor_readings(
    patient_id: str,
    sensor_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Fetch raw or filtered historical sensor and home cuff readings."""
    ehr = EHRService(db)
    if not ehr.get_patient(patient_id):
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    sensor_svc = SensorService(db)
    return sensor_svc.get_patient_readings(patient_id, sensor_type=sensor_type, limit=limit)


@router.post("/{patient_id}/sensor-readings", response_model=SensorReadingResponse)
async def post_sensor_reading(
    patient_id: str,
    payload: SensorReadingCreate,
    db: Session = Depends(get_db),
):
    """Idempotently ingest a wearable or cuff reading.

    Triggers live update flow:
    1. Persists reading idempotently.
    2. Recalculates fused rolling features.
    3. Re-scores calibrated prediction.
    4. Evaluates High-risk alert rules.
    5. Broadcasts updated Twin state to active WebSockets.
    """
    ehr = EHRService(db)
    if not ehr.get_patient(patient_id):
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    twin_svc = TwinService(db)
    await twin_svc.process_new_reading_pipeline(patient_id, payload)

    # Return the newly persisted sensor record
    sensor_svc = SensorService(db)
    readings = sensor_svc.get_patient_readings(patient_id, sensor_type=payload.sensor_type, limit=1)
    if readings:
        return readings[0]

    # Fallback to direct insertion return
    record = sensor_svc.add_reading(patient_id, payload)
    return record
