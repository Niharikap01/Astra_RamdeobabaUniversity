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
runner = ScenarioRunner(step_seconds=10.0)


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
            db_reading = SensorReading(
                patient_id=patient_id,
                sensor_type=r["sensor_type"],
                value=r["value"],
                unit=r["unit"],
                recorded_at=rec_time,
                ingested_at=datetime.now(timezone.utc),
                source=r.get("source", "simulator"),
            )
            db.merge(db_reading)
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
        cohort.append(PatientProfile(
            patient_id=p.patient_id,
            name=p.name,
            age=p.age,
            sex=p.sex,
            height_cm=p.height_cm,
            weight_kg=p.weight_kg,
            bmi=p.bmi,
            archetype=p.archetype,
            baseline_sbp=float(static_dict.get("baseline_sbp", 125.0)),
            baseline_dbp=float(static_dict.get("baseline_dbp", 80.0)),
            baseline_sleep_hours=float(static_dict.get("baseline_sleep_hours", 7.0)),
            baseline_hrv_rmssd=float(static_dict.get("baseline_hrv_rmssd", 35.0)),
            baseline_resting_hr=float(static_dict.get("baseline_resting_hr", 68.0)),
            adherence_tendency=float(static_dict.get("baseline_adherence", 0.9)),
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
