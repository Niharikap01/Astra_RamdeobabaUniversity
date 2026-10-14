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

    def compute_patient_30d_baseline(self, patient_id: str) -> Dict[str, float]:
        """Estimate personal baseline metrics from the patient's first 30 days of stored readings.

        Avoids simulator ground truth or archetype heuristics.
        """
        from datetime import timedelta
        import numpy as np
        from backend.app.models import SensorReading

        readings = list(self.db.execute(
            select(SensorReading)
            .where(SensorReading.patient_id == patient_id)
            .order_by(SensorReading.recorded_at.asc())
        ).scalars().all())

        if not readings:
            return {
                "baseline_sbp": float("nan"),
                "baseline_dbp": float("nan"),
                "baseline_sleep_hours": float("nan"),
                "baseline_hrv_rmssd": float("nan"),
                "baseline_resting_hr": float("nan"),
                "baseline_sleep_efficiency": float("nan"),
                "baseline_sbp_std": 3.5,
                "baseline_morning_surge": 3.0,
                "baseline_adherence": 1.0,
            }

        start_time = readings[0].recorded_at
        cutoff_30d = start_time + timedelta(days=30)
        first_30d_readings = [r for r in readings if r.recorded_at <= cutoff_30d]

        sbp_vals = [r.value for r in first_30d_readings if r.sensor_type == "home_sbp"]
        dbp_vals = [r.value for r in first_30d_readings if r.sensor_type == "home_dbp"]
        sleep_vals = [r.value for r in first_30d_readings if r.sensor_type == "sleep_duration"]
        hrv_vals = [r.value for r in first_30d_readings if r.sensor_type == "hrv_rmssd"]
        rhr_vals = [r.value for r in first_30d_readings if r.sensor_type == "resting_hr"]
        eff_vals = [r.value for r in first_30d_readings if r.sensor_type == "sleep_efficiency"]
        med_vals = [r.value for r in first_30d_readings if r.sensor_type == "medication_taken"]

        b_sbp = float(np.mean(sbp_vals)) if sbp_vals else float("nan")
        b_dbp = float(np.mean(dbp_vals)) if dbp_vals else float("nan")
        b_sleep = float(np.mean(sleep_vals)) if sleep_vals else float("nan")
        b_hrv = float(np.mean(hrv_vals)) if hrv_vals else float("nan")
        b_rhr = float(np.mean(rhr_vals)) if rhr_vals else float("nan")
        b_eff = float(np.mean(eff_vals)) if eff_vals else float("nan")
        b_std = float(np.std(sbp_vals, ddof=1)) if len(sbp_vals) > 1 else 3.5
        b_med = float(np.mean(med_vals)) if med_vals else 1.0

        morning_sbps = [r.value for r in first_30d_readings if r.sensor_type == "home_sbp" and r.recorded_at.hour < 12]
        evening_sbps = [r.value for r in first_30d_readings if r.sensor_type == "home_sbp" and r.recorded_at.hour >= 12]
        if morning_sbps and evening_sbps:
            b_surge = float(np.mean(morning_sbps) - np.mean(evening_sbps))
        else:
            b_surge = 3.0 if not np.isnan(b_sbp) else float("nan")

        return {
            "baseline_sbp": round(b_sbp, 1) if not np.isnan(b_sbp) else float("nan"),
            "baseline_dbp": round(b_dbp, 1) if not np.isnan(b_dbp) else float("nan"),
            "baseline_sleep_hours": round(b_sleep, 2) if not np.isnan(b_sleep) else float("nan"),
            "baseline_hrv_rmssd": round(b_hrv, 1) if not np.isnan(b_hrv) else float("nan"),
            "baseline_resting_hr": round(b_rhr, 1) if not np.isnan(b_rhr) else float("nan"),
            "baseline_sleep_efficiency": round(b_eff, 3) if not np.isnan(b_eff) else float("nan"),
            "baseline_sbp_std": round(b_std, 2),
            "baseline_morning_surge": round(b_surge, 1) if not np.isnan(b_surge) else 3.0,
            "baseline_adherence": round(b_med, 2),
        }

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

        # Personal baselines estimated from each patient's first 30 days of stored sensor data
        baselines = self.compute_patient_30d_baseline(patient.patient_id)
        b_sbp = baselines.get("baseline_sbp")
        b_dbp = baselines.get("baseline_dbp")
        b_sleep = baselines.get("baseline_sleep_hours")
        b_hrv = baselines.get("baseline_hrv_rmssd")
        b_rhr = baselines.get("baseline_resting_hr")

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
            "baseline_sleep_efficiency": baselines.get("baseline_sleep_efficiency"),
            "baseline_sbp_std": baselines.get("baseline_sbp_std"),
            "baseline_morning_surge": baselines.get("baseline_morning_surge"),
            "baseline_adherence": baselines.get("baseline_adherence"),
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
