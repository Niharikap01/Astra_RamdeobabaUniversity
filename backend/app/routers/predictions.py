"""Prediction history, risk evaluation, and clinical alert feed endpoints."""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import (
    AlertAcknowledgeRequest,
    AlertResponse,
    AlertSnoozeRequest,
    FalsePositiveRequest,
    PredictionResponse,
    TopFactor,
)
from backend.app.services.alert_service import AlertService
from backend.app.services.ehr_service import EHRService
from backend.app.services.prediction_service import PredictionService

router = APIRouter(tags=["Predictions & Alerts"])


@router.get("/api/patients/{patient_id}/risk", response_model=PredictionResponse)
def get_patient_risk(patient_id: str, db: Session = Depends(get_db)):
    """Retrieve most recent 24-hour hypertensive episode risk forecast."""
    pred_svc = PredictionService(db)
    pred = pred_svc.get_latest_prediction(patient_id)
    if not pred:
        raise HTTPException(status_code=404, detail=f"No predictions found for patient {patient_id}.")

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
    )


@router.get("/api/patients/{patient_id}/risk-history", response_model=List[PredictionResponse])
def get_patient_risk_history(
    patient_id: str,
    limit: int = Query(default=30, ge=1, le=100),
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
    db: Session = Depends(get_db),
):
    """Retrieve active and historical clinical alerts for a patient."""
    alert_svc = AlertService(db)
    return alert_svc.get_patient_alerts(patient_id, limit=limit)


@router.post("/api/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledgeRequest,
    db: Session = Depends(get_db),
):
    """Acknowledge a high-risk clinical alert with optional note."""
    alert_svc = AlertService(db)
    alert = alert_svc.acknowledge_alert(
        alert_id=alert_id,
        clinician_name=payload.clinician_name,
        comment=payload.comment,
    )
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    return alert


@router.post("/api/alerts/{alert_id}/snooze", response_model=AlertResponse)
def snooze_alert(
    alert_id: str,
    payload: AlertSnoozeRequest,
    db: Session = Depends(get_db),
):
    """Snooze a clinical alert with duration and documented reason."""
    alert_svc = AlertService(db)
    alert = alert_svc.snooze_alert(
        alert_id=alert_id,
        clinician_name=payload.clinician_name,
        snooze_hours=payload.snooze_hours,
        reason=payload.reason,
    )
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    return alert


@router.post("/api/alerts/{alert_id}/false-positive", response_model=AlertResponse)
def mark_false_positive(
    alert_id: str,
    payload: FalsePositiveRequest,
    db: Session = Depends(get_db),
):
    """Mark an alert as false positive for model safety auditing."""
    alert_svc = AlertService(db)
    alert = alert_svc.mark_false_positive(
        alert_id=alert_id,
        clinician_name=payload.clinician_name,
        reason=payload.reason,
    )
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    return alert
