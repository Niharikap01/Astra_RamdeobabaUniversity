"""Scenario Runner for NightWatch.

Orchestrates real-time background simulation of longitudinal patient streams,
with support for dynamic speed adjustment and clinical stress-testing scenario injection.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional
import numpy as np

from .ehr_simulator import PatientProfile
from .wearable_simulator import DailySimulationRecord, WearableSimulator

logger = logging.getLogger("nightwatch.simulation")


@dataclass
class SimulationStatus:
    """Current state of the real-time simulation background task."""

    is_running: bool = False
    patient_count: int = 0
    step_seconds: float = 10.0
    current_simulated_date: str = ""
    active_scenario: Optional[str] = None
    last_tick_at: Optional[str] = None
    ticks_completed: int = 0


class ScenarioRunner:
    """Manages real-time simulation stepping and clinical scenario perturbation injection."""

    def __init__(
        self,
        step_seconds: float = 10.0,
        on_reading_generated: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        self.step_seconds = step_seconds
        self.on_reading_generated = on_reading_generated
        self.status = SimulationStatus(step_seconds=step_seconds)
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self.active_overrides: Dict[str, Dict[str, Any]] = {}
        self.wearable_sim = WearableSimulator(seed=101)

    def set_scenario(self, patient_id: str, scenario_name: str) -> Dict[str, Any]:
        """Inject a clinical scenario perturbation for a specific patient.

        Supported scenarios:
        - 'force_poor_sleep': 4.1h fragmented sleep, low HRV, elevated sympathetic tone.
        - 'force_missed_dose': Missed medication for 2 consecutive days, rebound risk.
        - 'force_high_stress_sedentary': Sedentary (<1800 steps), high stress proxy.
        - 'restore_optimal': 8.0h restorative sleep, optimal adherence, >8500 steps.
        - 'clear': Removes active overrides.
        """
        if scenario_name == "clear":
            self.active_overrides.pop(patient_id, None)
            return {"patient_id": patient_id, "scenario": "none", "status": "cleared"}

        valid_scenarios = [
            "force_poor_sleep",
            "force_missed_dose",
            "force_high_stress_sedentary",
            "restore_optimal",
        ]
        if scenario_name not in valid_scenarios:
            raise ValueError(f"Unknown scenario '{scenario_name}'. Valid options: {valid_scenarios}")

        self.active_overrides[patient_id] = {
            "scenario": scenario_name,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }
        self.status.active_scenario = f"{scenario_name} (Patient {patient_id})"
        logger.info(f"Clinical scenario '{scenario_name}' injected for patient {patient_id}")

        return {
            "patient_id": patient_id,
            "scenario": scenario_name,
            "status": "active",
            "description": self._get_scenario_description(scenario_name),
        }

    def _get_scenario_description(self, scenario_name: str) -> str:
        descriptions = {
            "force_poor_sleep": "Forces 4.1 hours fragmented sleep with frequent awakenings, suppressed HRV, and morning sympathetic surge.",
            "force_missed_dose": "Simulates 48-hour oral medication omission, provoking rebound hemodynamic vascular tone.",
            "force_high_stress_sedentary": "Imposes sedentary activity (<1800 steps) with elevated autonomic stress proxy.",
            "restore_optimal": "Restores 8.0 hours restorative sleep architecture, 100% medication adherence, and protective activity levels.",
        }
        return descriptions.get(scenario_name, "Custom scenario applied.")

    def step_patient_day(
        self,
        profile: PatientProfile,
        base_record: DailySimulationRecord,
        new_day_idx: int,
        sim_date: datetime,
    ) -> DailySimulationRecord:
        """Advance a patient by 1 simulated day, applying any active scenario overrides."""
        override = self.active_overrides.get(profile.patient_id, {}).get("scenario")

        # Base simulation values for the day
        sleep_h, deep_h, rem_h, awakenings, efficiency = self.wearable_sim._simulate_sleep(
            profile, is_weekend=(sim_date.weekday() >= 5), day_idx=new_day_idx
        )
        stress = float(np.clip(np.random.beta(2, 5), 0.0, 1.0))
        med_taken, _ = self.wearable_sim._simulate_adherence(profile, streak=0)
        steps, active_min = self.wearable_sim._simulate_activity(profile, is_weekend=False, sleep_hours=sleep_h)

        # Apply Scenario Overrides
        if override == "force_poor_sleep":
            sleep_h = 4.1
            deep_h = 0.35
            rem_h = 0.50
            awakenings = 7
            efficiency = 0.62
            stress = 0.85
        elif override == "force_missed_dose":
            med_taken = 0
            stress = 0.55
        elif override == "force_high_stress_sedentary":
            steps = 1450
            active_min = 8
            stress = 0.90
        elif override == "restore_optimal":
            sleep_h = 8.1
            deep_h = 1.65
            rem_h = 1.80
            awakenings = 1
            efficiency = 0.94
            stress = 0.15
            med_taken = 1
            steps = 9200
            active_min = 45

        hrv_rmssd, resting_hr = self.wearable_sim._simulate_autonomic(profile, sleep_h, efficiency, stress)

        # Latent risk and hemodynamics
        sleep_debt = max(0.0, profile.baseline_sleep_hours - sleep_h)
        latent_prob, m_sbp, m_dbp, e_sbp, e_dbp = self.wearable_sim._simulate_hemodynamics(
            profile=profile,
            sleep_hours=sleep_h,
            efficiency=efficiency,
            accumulated_sleep_debt=sleep_debt,
            hrv=hrv_rmssd,
            resting_hr=resting_hr,
            steps=steps,
            med_taken=med_taken,
            missed_streak=0 if med_taken else 1,
            stress_level=stress,
        )

        return DailySimulationRecord(
            patient_id=profile.patient_id,
            day_index=new_day_idx,
            date=sim_date.strftime("%Y-%m-%d"),
            sleep_duration_hours=round(sleep_h, 2),
            deep_sleep_hours=round(deep_h, 2),
            rem_sleep_hours=round(rem_h, 2),
            awakenings_count=awakenings,
            sleep_efficiency=round(efficiency, 3),
            hrv_rmssd=round(hrv_rmssd, 1),
            resting_hr=round(resting_hr, 1),
            steps=steps,
            active_minutes=active_min,
            medication_taken=med_taken,
            stress_level=round(stress, 2),
            morning_sbp=round(m_sbp, 1),
            morning_dbp=round(m_dbp, 1),
            evening_sbp=round(e_sbp, 1),
            evening_dbp=round(e_dbp, 1),
            latent_risk_score=round(latent_prob, 3),
            hypertensive_episode_next_day=int(m_sbp >= 140 or m_dbp >= 90 or e_sbp >= 140 or e_dbp >= 90),
        )

    async def start(
        self,
        patients: List[PatientProfile],
        latest_records: Dict[str, DailySimulationRecord],
        step_seconds: Optional[float] = None,
    ) -> None:
        """Start the background simulation loop."""
        if self.status.is_running:
            return

        if step_seconds is not None:
            self.step_seconds = step_seconds
            self.status.step_seconds = step_seconds

        self.status.is_running = True
        self.status.patient_count = len(patients)
        self._stop_event.clear()

        self._task = asyncio.create_task(
            self._run_loop(patients, latest_records)
        )
        logger.info(f"NightWatch simulation started for {len(patients)} patients with {self.step_seconds}s cadence.")

    async def stop(self) -> None:
        """Stop the background simulation loop."""
        if not self.status.is_running:
            return
        self.status.is_running = False
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("NightWatch simulation paused.")

    async def _run_loop(
        self,
        patients: List[PatientProfile],
        latest_records: Dict[str, DailySimulationRecord],
    ) -> None:
        """Asynchronous execution loop advancing simulated patient days."""
        sim_day_offset = 1
        current_time = datetime.now(timezone.utc)

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.step_seconds)
                sim_date = current_time + timedelta(days=sim_day_offset)
                self.status.current_simulated_date = sim_date.strftime("%Y-%m-%d")
                self.status.last_tick_at = datetime.now(timezone.utc).isoformat()
                self.status.ticks_completed += 1

                for patient in patients:
                    prev_rec = latest_records.get(patient.patient_id)
                    day_idx = (prev_rec.day_index + 1) if prev_rec else sim_day_offset
                    new_rec = self.step_patient_day(patient, prev_rec, day_idx, sim_date)
                    latest_records[patient.patient_id] = new_rec

                    if self.on_reading_generated:
                        readings = new_rec.to_sensor_readings(sim_date)
                        for r in readings:
                            await self.on_reading_generated(r)

                sim_day_offset += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error during simulation tick: {e}", exc_info=True)
                await asyncio.sleep(2.0)
