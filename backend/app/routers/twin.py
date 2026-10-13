"""Digital Twin consolidated state and Sleep Fingerprint endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.schemas import (
    DigitalTwinResponse,
    RiskHorizonResponse,
    SleepFingerprintData,
    WhyRiskChangedResponse,
)
from backend.app.services.ehr_service import EHRService
from backend.app.services.fingerprint_service import FingerprintService
from backend.app.services.fusion_service import FusionService
from backend.app.services.twin_service import TwinService

router = APIRouter(prefix="/api/patients", tags=["Digital Twin"])


@router.get("/{patient_id}/twin", response_model=DigitalTwinResponse)
def get_patient_twin(patient_id: str, db: Session = Depends(get_db)):
    """Retrieve full consolidated Digital Twin representation of patient."""
    twin_svc = TwinService(db)
    twin = twin_svc.build_twin(patient_id)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")
    return twin


@router.get("/{patient_id}/sleep-fingerprint", response_model=SleepFingerprintData)
def get_sleep_fingerprint(patient_id: str, db: Session = Depends(get_db)):
    """Retrieve 5-axis normalized radar deviations vs personal 30-day baseline."""
    ehr = EHRService(db)
    patient = ehr.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    fusion_svc = FusionService(db)
    static_dict = ehr.get_patient_static_dict(patient)
    features_dict = fusion_svc.compute_current_features(static_dict)

    return FingerprintService.compute_fingerprint(static_dict, features_dict)


@router.get("/{patient_id}/risk-horizon", response_model=RiskHorizonResponse)
def get_risk_horizon(patient_id: str, db: Session = Depends(get_db)):
    """Retrieve 24-hour synchronized Risk Horizon trajectory."""
    twin_svc = TwinService(db)
    horizon = twin_svc.build_risk_horizon(patient_id)
    if not horizon:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")
    return horizon


@router.get("/{patient_id}/why-risk-changed", response_model=WhyRiskChangedResponse)
def get_why_risk_changed(patient_id: str, db: Session = Depends(get_db)):
    """Retrieve clinician-oriented signed factor waterfall comparison."""
    twin_svc = TwinService(db)
    res = twin_svc.get_why_risk_changed(patient_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")
    return res
