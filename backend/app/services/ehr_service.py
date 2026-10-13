"""EHR data access and clinical summary service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models import EHREvent, Patient


class EHRService:
    """Provides structured EHR profile and history queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        """Fetch patient record by primary key."""
        return self.db.execute(select(Patient).where(Patient.patient_id == patient_id)).scalar_one_or_none()

    def list_patients(self, limit: int = 200, offset: int = 0) -> List[Patient]:
        """List patients with pagination."""
        return list(self.db.execute(select(Patient).order_by(Patient.patient_id).offset(offset).limit(limit)).scalars().all())

    def get_patient_ehr_events(self, patient_id: str) -> List[EHREvent]:
        """Fetch all discrete EHR events for a patient."""
        return list(self.db.execute(
            select(EHREvent)
            .where(EHREvent.patient_id == patient_id)
            .order_by(EHREvent.event_time.asc())
        ).scalars().all())

    def get_patient_static_dict(self, patient: Patient) -> Dict[str, Any]:
        """Convert patient and EHR events to the static feature dictionary expected by FeatureEngineeringPipeline."""
        events = self.get_patient_ehr_events(patient.patient_id)

        diagnoses = [e.description for e in events if e.event_type == "diagnosis"]
        medications = [e.description for e in events if e.event_type == "medication"]

        has_dm = 1 if any("diabetes" in d.lower() for d in diagnoses) else 0
        has_ckd = 1 if any("kidney" in d.lower() for d in diagnoses) else 0
        has_dyslip = 1 if any("lipid" in d.lower() or "cholesterol" in d.lower() for d in diagnoses) else 0
        has_stroke = 1 if any("stroke" in d.lower() or "infarction" in d.lower() for d in diagnoses) else 0
        has_ihd = 1 if any("ischemic" in d.lower() or "coronary" in d.lower() for d in diagnoses) else 0
        has_osa = 1 if any("apnea" in d.lower() for d in diagnoses) else 0
        has_family_cvd = 1 if any(e.event_type == "family_history" for e in events) else 0

        # Medication classes
        has_acei = 1 if any("lisinopril" in m.lower() or "enalapril" in m.lower() for m in medications) else 0
        has_arb = 1 if any("losartan" in m.lower() or "valsartan" in m.lower() for m in medications) else 0
        has_ccb = 1 if any("amlodipine" in m.lower() or "diltiazem" in m.lower() for m in medications) else 0
        has_bb = 1 if any("metoprolol" in m.lower() or "atenolol" in m.lower() for m in medications) else 0
        has_diur = 1 if any("hydrochlorothiazide" in m.lower() or "chlorthalidone" in m.lower() for m in medications) else 0
        has_stat = 1 if any("statin" in m.lower() for m in medications) else 0

        # Lab values
        def get_lab_val(code: str, default: float) -> float:
            for e in events:
                if e.event_type == "lab" and (e.code == code or code in e.description.lower()):
                    try:
                        return float(e.value)
                    except ValueError:
                        pass
            return default

        hba1c = get_lab_val("4548-4", 7.2 if has_dm else 5.4)
        ldl = get_lab_val("13457-7", 130.0 if has_dyslip else 95.0)
        hdl = get_lab_val("2085-9", 45.0)
        trig = get_lab_val("2571-8", 160.0 if has_dyslip else 120.0)
        creat = get_lab_val("2160-0", 1.5 if has_ckd else 0.95)
        egfr = get_lab_val("33914-3", 55.0 if has_ckd else 85.0)
        potassium = get_lab_val("2823-3", 4.3)

        # Baseline hemodynamics conditioned on archetype
        archetype = patient.archetype
        if archetype == "well_controlled":
            b_sbp, b_dbp, b_sleep, b_hrv, b_rhr = 118.0, 75.0, 7.6, 46.0, 61.0
        elif archetype == "controlled_hypertensive":
            b_sbp, b_dbp, b_sleep, b_hrv, b_rhr = 125.0, 79.0, 7.1, 37.0, 65.0
        elif archetype == "poor_sleep_risk":
            b_sbp, b_dbp, b_sleep, b_hrv, b_rhr = 135.0, 86.0, 5.4, 24.0, 73.0
        elif archetype == "non_adherent":
            b_sbp, b_dbp, b_sleep, b_hrv, b_rhr = 136.0, 87.0, 6.8, 32.0, 69.0
        elif archetype == "sedentary_high_risk":
            b_sbp, b_dbp, b_sleep, b_hrv, b_rhr = 139.0, 88.5, 6.3, 22.0, 76.0
        else:  # osa_suspected
            b_sbp, b_dbp, b_sleep, b_hrv, b_rhr = 138.0, 88.0, 5.8, 25.0, 74.0

        return {
            "patient_id": patient.patient_id,
            "name": patient.name,
            "age": patient.age,
            "sex": patient.sex,
            "height_cm": patient.height_cm,
            "weight_kg": patient.weight_kg,
            "bmi": patient.bmi,
            "archetype": patient.archetype,
            "hypertension_duration_years": max(2.0, (patient.age - 45) * 0.4),
            "baseline_sbp": b_sbp,
            "baseline_dbp": b_dbp,
            "baseline_hrv_rmssd": b_hrv,
            "baseline_resting_hr": b_rhr,
            "baseline_sleep_hours": b_sleep,
            "family_history_cvd": has_family_cvd,
            "diabetes": has_dm,
            "ckd": has_ckd,
            "dyslipidemia": has_dyslip,
            "prior_stroke": has_stroke,
            "ihd": has_ihd,
            "osa": has_osa,
            "hba1c": hba1c,
            "ldl_cholesterol": ldl,
            "hdl_cholesterol": hdl,
            "triglycerides": trig,
            "serum_creatinine": creat,
            "egfr": egfr,
            "serum_potassium": potassium,
            "med_acei": has_acei,
            "med_arb": has_arb,
            "med_ccb": has_ccb,
            "med_beta_blocker": has_bb,
            "med_diuretic": has_diur,
            "med_statin": has_stat,
            "diagnoses": diagnoses,
            "medications": medications,
        }
