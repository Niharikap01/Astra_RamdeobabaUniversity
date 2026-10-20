"""Prediction history, risk evaluation, and clinical alert feed endpoints."""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, require_role
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import User
from backend.app.schemas import (
    AlertAcknowledgeRequest,
    AlertResponse,
    AlertSnoozeRequest,
    FalsePositiveRequest,
    PredictionResponse,
    ThresholdsResponse,
    TopFactor,
)
from backend.app.services.alert_service import AlertService
from backend.app.services.ehr_service import EHRService
from backend.app.services.prediction_service import PredictionService

router = APIRouter(tags=["Predictions & Alerts"])


@router.get("/api/thresholds", response_model=ThresholdsResponse)
def get_operating_thresholds():
    """Retrieve calibrated clinical decision operating thresholds (derived from validation set)."""
    return ThresholdsResponse(
        moderate=settings.risk_threshold_moderate,
        high=settings.risk_threshold_high,
        source="validation",
        cooldown_hours=settings.alert_cooldown_hours,
    )


@router.get("/api/patients/{patient_id}/risk", response_model=PredictionResponse)
def get_patient_risk(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve most recent 24-hour hypertensive episode risk forecast."""
    ehr = EHRService(db)
    patient = ehr.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    from backend.app.services.fusion_service import FusionService
    from backend.app.models import SensorReading
    from sqlalchemy import select

    fusion_svc = FusionService(db)
    overall_cov, _ = fusion_svc.compute_data_coverage(patient_id, days_lookback=7)

    pred_svc = PredictionService(db)
    pred = pred_svc.get_latest_prediction(patient_id)

    if not pred:
        # Check if patient has readings but coverage is too low
        if overall_cov < (settings.min_coverage_threshold * 100.0):
            has_readings = db.execute(
                select(SensorReading).where(SensorReading.patient_id == patient_id)
            ).scalars().first()
            if has_readings is not None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Prediction refused: Data coverage ({overall_cov:.1f}%) is below minimum threshold ({settings.min_coverage_threshold * 100.0:.1f}%)."
                )
        raise HTTPException(status_code=404, detail=f"No predictions found for patient {patient_id}.")

    snap = pred.feature_snapshot or {}
    pred_cov = snap.get("_data_coverage_pct", overall_cov)
    quality_score = snap.get("_confidence_score", 0.95)
    uncertainty_range = [
        snap.get("_confidence_lower", max(0.0, round(pred.probability - 0.08, 4))),
        snap.get("_confidence_upper", min(1.0, round(pred.probability + 0.08, 4))),
    ]

    top_factors_data = [
        TopFactor(
            feature=f.get("feature", ""),
            display_name=f.get("display_name", ""),
            value=float(f.get("value", 0.0)),
            impact=float(f.get("impact", 0.0)),
            is_risk_driver=bool(f.get("is_risk_driver", False)),
            reason=f.get("reason", ""),
        )
        for f in pred.top_factors
    ]

    return PredictionResponse(
        prediction_id=pred.prediction_id,
        patient_id=patient_id,
        probability=pred.probability,
        risk_level=pred.risk_level,
        model_version=pred.model_version,
        generated_at=pred.generated_at,
        top_factors=top_factors_data,
        feature_snapshot=pred.feature_snapshot or {},
        data_coverage=pred_cov,
        uncertainty_quality=quality_score,
        uncertainty_range_heuristic=uncertainty_range,
    )


@router.get("/api/patients/{patient_id}/risk-history", response_model=List[PredictionResponse])
def get_patient_risk_history(
    patient_id: str,
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve historical prediction trajectory for longitudinal risk plotting."""
    pred_svc = PredictionService(db)
    history = pred_svc.get_prediction_history(patient_id, limit=limit)

    results = []
    for pred in history:
        top_factors_data = [
            TopFactor(
                feature=f.get("feature", ""),
                display_name=f.get("display_name", ""),
                value=float(f.get("value", 0.0)),
                impact=float(f.get("impact", 0.0)),
                is_risk_driver=bool(f.get("is_risk_driver", False)),
                reason=f.get("reason", ""),
            )
            for f in pred.top_factors
        ]
        results.append(
            PredictionResponse(
                prediction_id=pred.prediction_id,
                patient_id=pred.patient_id,
                probability=pred.probability,
                risk_level=pred.risk_level,
                model_version=pred.model_version,
                generated_at=pred.generated_at,
                top_factors=top_factors_data,
                feature_snapshot=pred.feature_snapshot or {},
            )
        )
    return results


@router.get("/api/patients/{patient_id}/alerts", response_model=List[AlertResponse])
def get_patient_alerts(
    patient_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve active and historical clinical alerts for a patient."""
    alert_svc = AlertService(db)
    return alert_svc.get_patient_alerts(patient_id, limit=limit)


@router.post("/api/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledgeRequest,
    current_user: User = Depends(require_role(["clinician", "admin"])),
    db: Session = Depends(get_db),
):
    """Acknowledge a high-risk clinical alert with optional note."""
    clinician_identity = (
        payload.clinician_name
        if (payload.clinician_name and payload.clinician_name != "Dr. Clinician")
        else (current_user.full_name or current_user.username or "Dr. Clinician")
    )
    alert_svc = AlertService(db)
    alert = alert_svc.acknowledge_alert(
        alert_id=alert_id,
        clinician_name=clinician_identity,
        comment=payload.comment,
    )
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    return alert


@router.post("/api/alerts/{alert_id}/snooze", response_model=AlertResponse)
def snooze_alert(
    alert_id: str,
    payload: AlertSnoozeRequest,
    current_user: User = Depends(require_role(["clinician", "admin"])),
    db: Session = Depends(get_db),
):
    """Snooze a clinical alert with duration and documented reason."""
    clinician_identity = (
        payload.clinician_name
        if (payload.clinician_name and payload.clinician_name != "Dr. Clinician")
        else (current_user.full_name or current_user.username or "Dr. Clinician")
    )
    alert_svc = AlertService(db)
    try:
        alert = alert_svc.snooze_alert(
            alert_id=alert_id,
            clinician_name=clinician_identity,
            snooze_hours=payload.snooze_hours,
            reason=payload.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    return alert


@router.post("/api/alerts/{alert_id}/false-positive", response_model=AlertResponse)
def mark_false_positive(
    alert_id: str,
    payload: FalsePositiveRequest,
    current_user: User = Depends(require_role(["clinician", "admin"])),
    db: Session = Depends(get_db),
):
    """Mark an alert as false positive for model safety auditing."""
    clinician_identity = (
        payload.clinician_name
        if (payload.clinician_name and payload.clinician_name != "Dr. Clinician")
        else (current_user.full_name or current_user.username or "Dr. Clinician")
    )
    alert_svc = AlertService(db)
    alert = alert_svc.mark_false_positive(
        alert_id=alert_id,
        clinician_name=clinician_identity,
        reason=payload.reason,
    )
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    return alert
