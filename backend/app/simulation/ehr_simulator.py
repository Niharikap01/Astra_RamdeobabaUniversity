"""EHR Simulator for NightWatch.

Generates realistic, synthetic longitudinal patient cohorts with clinical archetypes,
EHR diagnoses, lab values, medication regimens, and baseline hemodynamics.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import numpy as np


ARCHETYPES = [
    "controlled_hypertensive",
    "poor_sleep_risk",
    "non_adherent",
    "sedentary_high_risk",
    "osa_suspected",
    "well_controlled",
]

FIRST_NAMES_M = ["James", "Robert", "John", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Charles", "Marcus", "Arthur", "Samuel", "Benjamin"]
FIRST_NAMES_F = ["Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen", "Elena", "Clara", "Grace", "Rachel"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Jackson"]


@dataclass
class PatientProfile:
    """Demographic and static EHR clinical profile of a synthetic patient."""

    patient_id: str
    name: str
    age: int
    sex: str
    height_cm: float
    weight_kg: float
    bmi: float
    archetype: str
    hypertension_duration_years: float
    baseline_sbp: float
    baseline_dbp: float
    baseline_hrv_rmssd: float
    baseline_resting_hr: float
    baseline_sleep_hours: float
    family_history_cvd: int

    # Comorbidities (0 or 1)
    diabetes: int
    ckd: int
    dyslipidemia: int
    prior_stroke: int
    ihd: int
    osa: int

    # Labs
    hba1c: float
    ldl_cholesterol: float
    hdl_cholesterol: float
    triglycerides: float
    serum_creatinine: float
    egfr: float
    serum_potassium: float

    # Medication Classes (0 or 1)
    med_acei: int
    med_arb: int
    med_ccb: int
    med_beta_blocker: int
    med_diuretic: int
    med_statin: int

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert patient profile to a serializable dictionary."""
        return {
            "patient_id": self.patient_id,
            "name": self.name,
            "age": self.age,
            "sex": self.sex,
            "height_cm": round(self.height_cm, 1),
            "weight_kg": round(self.weight_kg, 1),
            "bmi": round(self.bmi, 1),
            "archetype": self.archetype,
            "hypertension_duration_years": round(self.hypertension_duration_years, 1),
            "baseline_sbp": round(self.baseline_sbp, 1),
            "baseline_dbp": round(self.baseline_dbp, 1),
            "baseline_hrv_rmssd": round(self.baseline_hrv_rmssd, 1),
            "baseline_resting_hr": round(self.baseline_resting_hr, 1),
            "baseline_sleep_hours": round(self.baseline_sleep_hours, 1),
            "family_history_cvd": self.family_history_cvd,
            "diabetes": self.diabetes,
            "ckd": self.ckd,
            "dyslipidemia": self.dyslipidemia,
            "prior_stroke": self.prior_stroke,
            "ihd": self.ihd,
            "osa": self.osa,
            "hba1c": round(self.hba1c, 2),
            "ldl_cholesterol": round(self.ldl_cholesterol, 1),
            "hdl_cholesterol": round(self.hdl_cholesterol, 1),
            "triglycerides": round(self.triglycerides, 1),
            "serum_creatinine": round(self.serum_creatinine, 2),
            "egfr": round(self.egfr, 1),
            "serum_potassium": round(self.serum_potassium, 2),
            "med_acei": self.med_acei,
            "med_arb": self.med_arb,
            "med_ccb": self.med_ccb,
            "med_beta_blocker": self.med_beta_blocker,
            "med_diuretic": self.med_diuretic,
            "med_statin": self.med_statin,
            "created_at": self.created_at.isoformat(),
        }


class EHRSimulator:
    """Generates synthetic patient cohorts with balanced clinical archetypes and EHR events."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        random.seed(seed)

    def generate_cohort(self, num_patients: int = 200) -> List[PatientProfile]:
        """Generate a cohort of synthetic patients evenly or realistically distributed across archetypes."""
        patients: List[PatientProfile] = []
        for i in range(num_patients):
            archetype = ARCHETYPES[i % len(ARCHETYPES)]
            pid = f"NW-{i+1:04d}"
            profile = self._generate_patient(pid, archetype)
            patients.append(profile)
        return patients

    def _generate_patient(self, patient_id: str, archetype: str) -> PatientProfile:
        """Create a single patient profile based on archetype physiological boundaries."""
        sex = "M" if self.rng.random() < 0.52 else "F"
        name = (
            f"{random.choice(FIRST_NAMES_M)} {random.choice(LAST_NAMES)}"
            if sex == "M"
            else f"{random.choice(FIRST_NAMES_F)} {random.choice(LAST_NAMES)}"
        )

        # Baseline age conditioned on archetype
        if archetype in ("sedentary_high_risk", "osa_suspected"):
            age = int(self.rng.integers(48, 79))
        elif archetype == "well_controlled":
            age = int(self.rng.integers(36, 65))
        else:
            age = int(self.rng.integers(42, 74))

        # Height and Weight with BMI calculation
        if sex == "M":
            height_cm = float(self.rng.normal(176.0, 7.0))
        else:
            height_cm = float(self.rng.normal(163.0, 6.5))

        # Archetype BMI distributions
        if archetype in ("sedentary_high_risk", "osa_suspected"):
            target_bmi = float(self.rng.normal(33.5, 3.8))
        elif archetype == "well_controlled":
            target_bmi = float(self.rng.normal(24.8, 2.2))
        else:
            target_bmi = float(self.rng.normal(28.4, 3.2))

        target_bmi = max(19.0, min(45.0, target_bmi))
        height_m = height_cm / 100.0
        weight_kg = target_bmi * (height_m**2)

        # Comorbidities based on archetype & age
        htn_years = float(max(1.0, min(30.0, self.rng.normal(8.0 + (age - 50) * 0.2, 4.0))))
        family_cvd = 1 if self.rng.random() < 0.38 else 0

        # Archetype condition assignments
        diabetes = 1 if (archetype in ("sedentary_high_risk", "osa_suspected") and self.rng.random() < 0.55) or self.rng.random() < 0.22 else 0
        ckd = 1 if (age > 65 and self.rng.random() < 0.25) or (diabetes and self.rng.random() < 0.20) else 0
        dyslipidemia = 1 if (archetype in ("sedentary_high_risk", "non_adherent") and self.rng.random() < 0.70) or self.rng.random() < 0.45 else 0
        prior_stroke = 1 if (age > 68 and self.rng.random() < 0.12) else 0
        ihd = 1 if (family_cvd and age > 60 and self.rng.random() < 0.28) else 0
        osa = 1 if (archetype == "osa_suspected" or (target_bmi > 32 and self.rng.random() < 0.45)) else 0

        # Baseline labs
        hba1c = float(self.rng.normal(7.4, 0.9) if diabetes else self.rng.normal(5.4, 0.3))
        ldl = float(self.rng.normal(138.0, 25.0) if dyslipidemia else self.rng.normal(98.0, 18.0))
        hdl = float(self.rng.normal(42.0, 7.0) if sex == "M" else self.rng.normal(49.0, 8.0))
        trig = float(self.rng.normal(190.0, 45.0) if dyslipidemia else self.rng.normal(125.0, 30.0))
        creat = float(self.rng.normal(1.65, 0.35) if ckd else self.rng.normal(0.95, 0.18))
        egfr = float(max(25.0, min(110.0, 141.0 * min(creat / 0.9, 1.0) ** (-0.411) * 0.993**age)))
        potassium = float(self.rng.normal(4.3, 0.35))

        # Antihypertensive and cardioprotective medications
        # Guideline-directed medical therapy: ACEi or ARB, plus CCB or Diuretic
        takes_acei = 1 if self.rng.random() < 0.48 else 0
        takes_arb = 0 if takes_acei else (1 if self.rng.random() < 0.65 else 0)
        takes_ccb = 1 if (archetype in ("poor_sleep_risk", "sedentary_high_risk") and self.rng.random() < 0.60) or self.rng.random() < 0.42 else 0
        takes_bb = 1 if (ihd or prior_stroke or self.rng.random() < 0.25) else 0
        takes_diuretic = 1 if (ckd or archetype == "sedentary_high_risk" or self.rng.random() < 0.35) else 0
        takes_statin = 1 if (dyslipidemia or diabetes or age > 62 or self.rng.random() < 0.50) else 0

        # Baseline BP & Wearable baselines by archetype (calibrated resting levels)
        if archetype == "well_controlled":
            base_sbp = float(self.rng.normal(116.0, 3.5))
            base_dbp = float(self.rng.normal(74.0, 3.0))
            base_sleep = float(self.rng.normal(7.6, 0.4))
            base_hrv = float(self.rng.normal(46.0, 6.0))
            base_rhr = float(self.rng.normal(61.0, 4.0))
        elif archetype == "controlled_hypertensive":
            base_sbp = float(self.rng.normal(122.0, 4.0))
            base_dbp = float(self.rng.normal(78.0, 3.0))
            base_sleep = float(self.rng.normal(7.1, 0.5))
            base_hrv = float(self.rng.normal(37.0, 5.0))
            base_rhr = float(self.rng.normal(65.0, 4.5))
        elif archetype == "poor_sleep_risk":
            base_sbp = float(self.rng.normal(126.0, 4.0))
            base_dbp = float(self.rng.normal(81.0, 3.5))
            base_sleep = float(self.rng.normal(5.4, 0.4))
            base_hrv = float(self.rng.normal(24.0, 4.0))
            base_rhr = float(self.rng.normal(73.0, 5.0))
        elif archetype == "non_adherent":
            base_sbp = float(self.rng.normal(125.0, 4.5))
            base_dbp = float(self.rng.normal(80.5, 3.5))
            base_sleep = float(self.rng.normal(6.8, 0.6))
            base_hrv = float(self.rng.normal(32.0, 5.5))
            base_rhr = float(self.rng.normal(69.0, 5.0))
        elif archetype == "sedentary_high_risk":
            base_sbp = float(self.rng.normal(127.0, 4.0))
            base_dbp = float(self.rng.normal(81.5, 3.5))
            base_sleep = float(self.rng.normal(6.3, 0.5))
            base_hrv = float(self.rng.normal(22.0, 3.5))
            base_rhr = float(self.rng.normal(76.0, 5.5))
        else:  # osa_suspected
            base_sbp = float(self.rng.normal(127.0, 4.0))
            base_dbp = float(self.rng.normal(81.5, 3.5))
            base_sleep = float(self.rng.normal(5.8, 0.6))
            base_hrv = float(self.rng.normal(25.0, 4.0))
            base_rhr = float(self.rng.normal(74.0, 5.0))

        return PatientProfile(
            patient_id=patient_id,
            name=name,
            age=age,
            sex=sex,
            height_cm=height_cm,
            weight_kg=weight_kg,
            bmi=target_bmi,
            archetype=archetype,
            hypertension_duration_years=htn_years,
            baseline_sbp=base_sbp,
            baseline_dbp=base_dbp,
            baseline_hrv_rmssd=base_hrv,
            baseline_resting_hr=base_rhr,
            baseline_sleep_hours=base_sleep,
            family_history_cvd=family_cvd,
            diabetes=diabetes,
            ckd=ckd,
            dyslipidemia=dyslipidemia,
            prior_stroke=prior_stroke,
            ihd=ihd,
            osa=osa,
            hba1c=hba1c,
            ldl_cholesterol=ldl,
            hdl_cholesterol=hdl,
            triglycerides=trig,
            serum_creatinine=creat,
            egfr=egfr,
            serum_potassium=potassium,
            med_acei=takes_acei,
            med_arb=takes_arb,
            med_ccb=takes_ccb,
            med_beta_blocker=takes_bb,
            med_diuretic=takes_diuretic,
            med_statin=takes_statin,
        )

    def generate_ehr_events(self, profile: PatientProfile, start_date: datetime) -> List[Dict[str, Any]]:
        """Generate coded discrete EHR events for database ingestion."""
        events: List[Dict[str, Any]] = []

        def add_event(event_type: str, code: str, desc: str, val: Any, unit: str, delta_days: int = 0):
            event_time = start_date + timedelta(days=delta_days)
            events.append({
                "patient_id": profile.patient_id,
                "event_type": event_type,
                "code": code,
                "description": desc,
                "value": str(val),
                "unit": unit,
                "event_time": event_time.isoformat(),
                "source": "Hospital_EHR",
            })

        # Diagnoses
        add_event("diagnosis", "I10", "Essential (primary) hypertension", "Active", "", 0)
        if profile.diabetes:
            add_event("diagnosis", "E11.9", "Type 2 diabetes mellitus without complications", "Active", "", 5)
        if profile.ckd:
            add_event("diagnosis", "N18.3", "Chronic kidney disease, stage 3", "Active", "", 10)
        if profile.dyslipidemia:
            add_event("diagnosis", "E78.5", "Hyperlipidemia, unspecified", "Active", "", 2)
        if profile.prior_stroke:
            add_event("diagnosis", "I69.30", "Sequelae of cerebral infarction", "Past", "", -180)
        if profile.ihd:
            add_event("diagnosis", "I25.10", "Atherosclerotic heart disease of native coronary artery", "Active", "", 8)
        if profile.osa:
            add_event("diagnosis", "G47.33", "Obstructive sleep apnea (adult)", "Active", "", 12)
        if profile.family_history_cvd:
            add_event("family_history", "Z82.49", "Family history of ischemic heart disease", "Positive", "", 0)

        # Baseline Labs
        add_event("lab", "4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", profile.hba1c, "%", 15)
        add_event("lab", "13457-7", "Cholesterol in LDL [Mass/volume] in Serum", profile.ldl_cholesterol, "mg/dL", 15)
        add_event("lab", "2085-9", "Cholesterol in HDL [Mass/volume] in Serum", profile.hdl_cholesterol, "mg/dL", 15)
        add_event("lab", "2571-8", "Triglyceride [Mass/volume] in Serum", profile.triglycerides, "mg/dL", 15)
        add_event("lab", "2160-0", "Creatinine [Mass/volume] in Serum", profile.serum_creatinine, "mg/dL", 15)
        add_event("lab", "33914-3", "Glomerular filtration rate/1.73 sq M.predicted", profile.egfr, "mL/min/1.73m2", 15)
        add_event("lab", "2823-3", "Potassium [Moles/volume] in Serum", profile.serum_potassium, "mmol/L", 15)

        # Medications
        if profile.med_acei:
            add_event("medication", "Lisinopril", "Lisinopril 20 MG Oral Tablet", "20", "mg", 0)
        if profile.med_arb:
            add_event("medication", "Losartan", "Losartan potassium 50 MG Oral Tablet", "50", "mg", 0)
        if profile.med_ccb:
            add_event("medication", "Amlodipine", "Amlodipine 5 MG Oral Tablet", "5", "mg", 0)
        if profile.med_beta_blocker:
            add_event("medication", "Metoprolol", "Metoprolol succinate 50 MG Extended Release Tablet", "50", "mg", 0)
        if profile.med_diuretic:
            add_event("medication", "Hydrochlorothiazide", "Hydrochlorothiazide 25 MG Oral Tablet", "25", "mg", 0)
        if profile.med_statin:
            add_event("medication", "Atorvastatin", "Atorvastatin 20 MG Oral Tablet", "20", "mg", 0)

        return events
