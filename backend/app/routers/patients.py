"""Patient registry and clinical profile endpoints."""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import (
    BPRecheckRequest,
    ClinicianNoteCreate,
    ClinicianNoteResponse,
    MessageResponse,
    PatientProfileDetail,
    PatientSummary,
)
from backend.app.services.alert_service import AlertService
from backend.app.services.ehr_service import EHRService
from backend.app.services.prediction_service import PredictionService

router = APIRouter(prefix="/api/patients", tags=["Patients"])


@router.get("", response_model=List[PatientSummary])
def list_patients(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve cohort of monitored patients with baseline summary and current risk tier."""
    ehr = EHRService(db)
    pred_svc = PredictionService(db)
    alert_svc = AlertService(db)

    patients = ehr.list_patients(limit=limit, offset=offset)
    results = []

    for p in patients:
        latest_pred = pred_svc.get_latest_prediction(p.patient_id)
        open_alerts = [a for a in alert_svc.get_patient_alerts(p.patient_id, limit=10) if a.status == "open"]

        results.append(
            PatientSummary(
                patient_id=p.patient_id,
                name=p.name,
                age=p.age,
                sex=p.sex,
                height_cm=p.height_cm,
                weight_kg=p.weight_kg,
                bmi=p.bmi,
                archetype=p.archetype,
                created_at=p.created_at,
                latest_risk_level=latest_pred.risk_level if latest_pred else "Low",
                latest_probability=latest_pred.probability if latest_pred else 0.15,
                open_alerts_count=len(open_alerts),
            )
        )
    return results


@router.get("/{patient_id}/profile", response_model=PatientProfileDetail)
def get_patient_profile(patient_id: str, db: Session = Depends(get_db)):
    """Retrieve complete static clinical profile including comorbidities, labs, and medications."""
    ehr = EHRService(db)
    patient = ehr.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    static_dict = ehr.get_patient_static_dict(patient)
    pred_svc = PredictionService(db)
    latest_pred = pred_svc.get_latest_prediction(patient_id)

    return PatientProfileDetail(
        patient_id=patient.patient_id,
        name=patient.name,
        age=patient.age,
        sex=patient.sex,
        height_cm=patient.height_cm,
        weight_kg=patient.weight_kg,
        bmi=patient.bmi,
        archetype=patient.archetype,
        created_at=patient.created_at,
        latest_risk_level=latest_pred.risk_level if latest_pred else "Low",
        latest_probability=latest_pred.probability if latest_pred else 0.15,
        open_alerts_count=0,
        diagnoses=static_dict.get("diagnoses", []),
        medications=static_dict.get("medications", []),
        baseline_hrv_rmssd=round(static_dict.get("baseline_hrv_rmssd", 35.0), 1),
        baseline_resting_hr=round(static_dict.get("baseline_resting_hr", 68.0), 1),
        baseline_sleep_hours=round(static_dict.get("baseline_sleep_hours", 7.0), 1),
        baseline_sbp=round(static_dict.get("baseline_sbp", 125.0), 1),
        baseline_dbp=round(static_dict.get("baseline_dbp", 80.0), 1),
    )


@router.post("/{patient_id}/notes", response_model=ClinicianNoteResponse)
def add_patient_note(
    patient_id: str,
    payload: ClinicianNoteCreate,
    db: Session = Depends(get_db),
):
    """Add a documented clinician note for the patient record."""
    ehr = EHRService(db)
    patient = ehr.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    alert_svc = AlertService(db)
    note = alert_svc.add_clinician_note(patient_id, payload.note, alert_id=payload.alert_id)
    return note


@router.post("/{patient_id}/request-bp-recheck", response_model=MessageResponse)
def request_bp_recheck(
    patient_id: str,
    payload: BPRecheckRequest,
    db: Session = Depends(get_db),
):
    """Request an immediate seated home blood pressure cuff re-measurement from patient."""
    ehr = EHRService(db)
    patient = ehr.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    alert_svc = AlertService(db)
    alert_svc.add_clinician_note(
        patient_id=patient_id,
        note_text=f"[BP Recheck Requested: Priority={payload.priority.upper()}] Instructions: {payload.instructions}",
    )

    return MessageResponse(
        status="ok",
        message=f"Home blood pressure cuff recheck order dispatched to patient {patient_id}.",
        details={"patient_id": patient_id, "priority": payload.priority, "instructions": payload.instructions},
    )
