"""Counterfactual What-If simulator router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, require_role
from backend.app.database import get_db
from backend.app.models import User
from backend.app.schemas import WhatIfRequest, WhatIfResponse
from backend.app.services.ehr_service import EHRService
from backend.app.services.fusion_service import FusionService
from backend.app.services.whatif_service import WhatIfService

router = APIRouter(prefix="/api/patients", tags=["What-If Simulator"])


@router.post("/{patient_id}/what-if", response_model=WhatIfResponse)
def evaluate_what_if_scenario(
    patient_id: str,
    payload: WhatIfRequest,
    current_user: User = Depends(require_role(["clinician", "admin"])),
    db: Session = Depends(get_db),
):
    """Simulate counterfactual clinical interventions (sleep, adherence, activity, stress)
    and compute delta risk against observed baseline.
    """
    ehr = EHRService(db)
    patient = ehr.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    fusion_svc = FusionService(db)
    static_dict = ehr.get_patient_static_dict(patient)
    baseline_features = fusion_svc.compute_current_features(static_dict)

    whatif_svc = WhatIfService(db)
    return whatif_svc.run_counterfactual(
        patient_id=patient_id,
        baseline_features=baseline_features,
        request=payload,
    )
