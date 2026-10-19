"""Simulation control and scenario injection endpoints."""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal, get_db
from backend.app.schemas import (
    MessageResponse,
    ScenarioInjectRequest,
    SimulationStartRequest,
    SimulationStatusResponse,
)
from backend.app.services.ehr_service import EHRService
from backend.app.services.twin_service import TwinService
from backend.app.simulation.scenario_runner import ScenarioRunner
from backend.app.schemas import SensorReadingCreate

logger = logging.getLogger("nightwatch.simulation_router")

router = APIRouter(prefix="/api/simulation", tags=["Simulation Engine"])

# Global scenario runner instance
runner = ScenarioRunner(step_seconds=5.0)


async def handle_simulated_day(patient_id: str, readings_list: list) -> None:
    """Ingest simulated readings in batch and score ONE prediction per patient per day."""
    db = SessionLocal()
    try:
        from datetime import datetime, timezone
        from backend.app.models import SensorReading
        from backend.app.services.ehr_service import EHRService
        from backend.app.services.fusion_service import FusionService
        from backend.app.services.prediction_service import PredictionService
        from backend.app.services.alert_service import AlertService
        from backend.app.services.twin_service import TwinService
        from backend.app.services.ws_manager import ws_manager

        # 1. Ingest all sensor readings for this day
        for r in readings_list:
            rec_time = datetime.fromisoformat(r["recorded_at"]) if isinstance(r["recorded_at"], str) else r["recorded_at"]
            if rec_time.tzinfo is None:
                rec_time = rec_time.replace(tzinfo=timezone.utc)
            existing = db.query(SensorReading).filter_by(
                patient_id=patient_id,
                sensor_type=r["sensor_type"],
                recorded_at=rec_time,
            ).first()
            if existing:
                existing.value = r["value"]
                existing.unit = r["unit"]
                existing.ingested_at = datetime.now(timezone.utc)
            else:
                db_reading = SensorReading(
                    patient_id=patient_id,
                    sensor_type=r["sensor_type"],
                    value=r["value"],
                    unit=r["unit"],
                    recorded_at=rec_time,
                    ingested_at=datetime.now(timezone.utc),
                    source=r.get("source", "simulator"),
                )
                db.add(db_reading)
        db.commit()

        # 2. Recalculate features once for the simulated day
        ehr_svc = EHRService(db)
        fusion_svc = FusionService(db)
        patient = ehr_svc.get_patient(patient_id)
        if not patient:
            return
        static_dict = ehr_svc.get_patient_static_dict(patient)
        features_dict = fusion_svc.compute_current_features(static_dict)

        # 3. Generate exactly ONE prediction row per patient per day
        pred_svc = PredictionService(db)
        prediction = pred_svc.generate_and_save_prediction(patient_id, features_dict, enforce_coverage=False)

        # 4. Evaluate alert rule
        alert_svc = AlertService(db)
        alert_svc.evaluate_and_create_alert(patient_id, prediction)

        # 5. Broadcast updated twin
        twin_svc = TwinService(db)
        twin_state = twin_svc.build_twin(patient_id)
        if twin_state:
            await ws_manager.broadcast_twin_update(patient_id, twin_state.model_dump(mode="json"))
    except Exception as e:
        logger.error(f"Error handling simulated day for {patient_id}: {e}", exc_info=True)
    finally:
        db.close()


runner.on_day_generated = handle_simulated_day


@router.post("/start", response_model=MessageResponse)
async def start_simulation(payload: SimulationStartRequest, db: Session = Depends(get_db)):
    """Start real-time longitudinal simulation ticks across cohort from DB."""
    from backend.app.config import settings
    from backend.app.simulation.ehr_simulator import PatientProfile
    ehr = EHRService(db)

    max_p = settings.simulation_max_patients
    db_patients = ehr.list_patients(limit=max_p)
    if not db_patients:
        raise HTTPException(status_code=400, detail="No patients in database. Seed the database first.")

    cohort: list[PatientProfile] = []
    for p in db_patients:
        static_dict = ehr.get_patient_static_dict(p)

        def _f(val, fallback: float) -> float:
            try:
                if val is None:
                    return fallback
                import math
                fval = float(val)
                return fallback if math.isnan(fval) else fval
            except (ValueError, TypeError):
                return fallback

        def _i(val, fallback: int) -> int:
            try:
                return fallback if val is None else int(val)
            except (ValueError, TypeError):
                return fallback

        cohort.append(PatientProfile(
            patient_id=p.patient_id,
            name=p.name,
            age=p.age,
            sex=p.sex,
            height_cm=_f(p.height_cm, 170.0),
            weight_kg=_f(p.weight_kg, 75.0),
            bmi=_f(p.bmi, 26.0),
            archetype=p.archetype,
            hypertension_duration_years=_f(static_dict.get("hypertension_duration_years"), 5.0),
            baseline_sbp=_f(static_dict.get("baseline_sbp"), 125.0),
            baseline_dbp=_f(static_dict.get("baseline_dbp"), 80.0),
            baseline_hrv_rmssd=_f(static_dict.get("baseline_hrv_rmssd"), 35.0),
            baseline_resting_hr=_f(static_dict.get("baseline_resting_hr"), 68.0),
            baseline_sleep_hours=_f(static_dict.get("baseline_sleep_hours"), 7.0),
            family_history_cvd=_i(static_dict.get("family_history_cvd"), 0),
            diabetes=_i(static_dict.get("diabetes"), 0),
            ckd=_i(static_dict.get("ckd"), 0),
            dyslipidemia=_i(static_dict.get("dyslipidemia"), 0),
            prior_stroke=_i(static_dict.get("prior_stroke"), 0),
            ihd=_i(static_dict.get("ihd"), 0),
            osa=_i(static_dict.get("osa"), 0),
            hba1c=_f(static_dict.get("hba1c"), 5.6),
            ldl_cholesterol=_f(static_dict.get("ldl_cholesterol"), 100.0),
            hdl_cholesterol=_f(static_dict.get("hdl_cholesterol"), 45.0),
            triglycerides=_f(static_dict.get("triglycerides"), 130.0),
            serum_creatinine=_f(static_dict.get("serum_creatinine"), 1.0),
            egfr=_f(static_dict.get("egfr"), 85.0),
            serum_potassium=_f(static_dict.get("serum_potassium"), 4.3),
            med_acei=_i(static_dict.get("med_acei"), 0),
            med_arb=_i(static_dict.get("med_arb"), 0),
            med_ccb=_i(static_dict.get("med_ccb"), 0),
            med_beta_blocker=_i(static_dict.get("med_beta_blocker"), 0),
            med_diuretic=_i(static_dict.get("med_diuretic"), 0),
            med_statin=_i(static_dict.get("med_statin"), 0),
        ))

    await runner.start(patients=cohort, latest_records={}, step_seconds=payload.step_seconds)
    return MessageResponse(
        status="ok",
        message=f"Simulation started with {len(cohort)} patients at {payload.step_seconds}s cadence.",
        details={"running": True, "step_seconds": payload.step_seconds, "patient_count": len(cohort)},
    )


@router.post("/stop", response_model=MessageResponse)
async def stop_simulation():
    """Pause real-time simulation background loop."""
    await runner.stop()
    return MessageResponse(
        status="ok",
        message="Simulation stopped.",
        details={"running": False},
    )


@router.get("/status", response_model=SimulationStatusResponse)
def get_simulation_status():
    """Check current simulation background task state including tick duration."""
    st = runner.status
    return SimulationStatusResponse(
        is_running=st.is_running,
        patient_count=st.patient_count,
        step_seconds=st.step_seconds,
        current_simulated_date=st.current_simulated_date or None,
        active_scenario=st.active_scenario,
        ticks_completed=st.ticks_completed,
        last_tick_duration_seconds=st.last_tick_duration_seconds,
        last_tick_seconds=st.last_tick_duration_seconds,
    )


@router.post("/scenario/{patient_id}", response_model=MessageResponse)
def inject_scenario(
    patient_id: str,
    payload: ScenarioInjectRequest,
    db: Session = Depends(get_db),
):
    """Inject acute scenario perturbation (force_poor_sleep, force_missed_dose, etc.) for a patient."""
    ehr = EHRService(db)
    if not ehr.get_patient(patient_id):
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found.")

    try:
        result = runner.set_scenario(patient_id, payload.scenario)
        return MessageResponse(
            status="ok",
            message=f"Scenario '{payload.scenario}' applied for patient {patient_id}.",
            details=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
