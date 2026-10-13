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


async def handle_simulated_reading(reading_dict: dict) -> None:
    """Callback when background simulator generates a new reading."""
    db = SessionLocal()
    try:
        patient_id = reading_dict["patient_id"]
        reading_create = SensorReadingCreate(
            sensor_type=reading_dict["sensor_type"],
            value=reading_dict["value"],
            unit=reading_dict["unit"],
            recorded_at=reading_dict["recorded_at"],
            source=reading_dict.get("source", "simulator"),
        )
        twin_svc = TwinService(db)
        await twin_svc.process_new_reading_pipeline(patient_id, reading_create)
    except Exception as e:
        logger.error(f"Error handling simulated reading: {e}", exc_info=True)
    finally:
        db.close()


runner.on_reading_generated = handle_simulated_reading


@router.post("/start", response_model=MessageResponse)
async def start_simulation(payload: SimulationStartRequest, db: Session = Depends(get_db)):
    """Start real-time longitudinal simulation ticks across cohort."""
    ehr = EHRService(db)
    patients = ehr.list_patients(limit=20)
    if not patients:
        raise HTTPException(status_code=400, detail="No patients in database. Seed the database first.")

    # Convert to PatientProfile dataclasses
    from backend.app.simulation.ehr_simulator import EHRSimulator
    sim = EHRSimulator(seed=42)
    cohort = sim.generate_cohort(len(patients))

    await runner.start(patients=cohort, latest_records={}, step_seconds=payload.step_seconds)
    return MessageResponse(
        status="ok",
        message=f"Simulation started with {len(cohort)} patients at {payload.step_seconds}s cadence.",
        details={"running": True, "step_seconds": payload.step_seconds},
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
    """Check current simulation background task state."""
    st = runner.status
    return SimulationStatusResponse(
        is_running=st.is_running,
        patient_count=st.patient_count,
        step_seconds=st.step_seconds,
        current_simulated_date=st.current_simulated_date or None,
        active_scenario=st.active_scenario,
        ticks_completed=st.ticks_completed,
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
