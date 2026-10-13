"""Database seeding script for NightWatch.

Populates 200 synthetic patients with 120 days of longitudinal wearable
and home BP cuff readings, and coded EHR history.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

# Ensure root path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.database import SessionLocal, init_db
from backend.app.models import EHREvent, Patient, SensorReading
from backend.app.simulation.ehr_simulator import EHRSimulator
from backend.app.simulation.wearable_simulator import WearableSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nightwatch.seed")


def seed_database(num_patients: int = 200, days: int = 120, force: bool = False) -> None:
    """Populate database with synthetic cohort and longitudinal data."""
    init_db()
    db = SessionLocal()

    try:
        existing_count = db.query(Patient).count()
        if existing_count > 0 and not force:
            logger.info(f"Database already contains {existing_count} patients. Skipping seeding.")
            return

        logger.info(f"Seeding database with {num_patients} patients and {days} days of history...")
        ehr_sim = EHRSimulator(seed=42)
        wearable_sim = WearableSimulator(seed=42)

        cohort = ehr_sim.generate_cohort(num_patients)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        for p_idx, profile in enumerate(cohort):
            # 1. Patient Record
            db_patient = Patient(
                patient_id=profile.patient_id,
                name=profile.name,
                age=profile.age,
                sex=profile.sex,
                height_cm=profile.height_cm,
                weight_kg=profile.weight_kg,
                bmi=profile.bmi,
                archetype=profile.archetype,
                created_at=profile.created_at,
            )
            db.add(db_patient)

            # 2. EHR Events
            ehr_events = ehr_sim.generate_ehr_events(profile, start_date)
            for ev in ehr_events:
                db_event = EHREvent(
                    patient_id=ev["patient_id"],
                    event_type=ev["event_type"],
                    code=ev["code"],
                    description=ev["description"],
                    value=ev["value"],
                    unit=ev.get("unit", ""),
                    event_time=datetime.fromisoformat(ev["event_time"]),
                    source=ev["source"],
                )
                db.add(db_event)

            # 3. Longitudinal Wearable & Home BP readings
            daily_records = wearable_sim.simulate_patient_history(profile, days=days, start_date=start_date)
            for rec in daily_records:
                readings = rec.to_sensor_readings(start_date)
                for r in readings:
                    db_reading = SensorReading(
                        patient_id=r["patient_id"],
                        sensor_type=r["sensor_type"],
                        value=r["value"],
                        unit=r["unit"],
                        recorded_at=datetime.fromisoformat(r["recorded_at"]),
                        ingested_at=datetime.fromisoformat(r["ingested_at"]),
                        source=r["source"],
                    )
                    db.add(db_reading)

            # Commit in batches of 10 patients
            if (p_idx + 1) % 10 == 0 or (p_idx + 1) == len(cohort):
                db.commit()
                logger.info(f"Seeded {p_idx + 1}/{len(cohort)} patients...")

        logger.info("Successfully completed NightWatch database seeding.")
    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    seed_database(num_patients=200, days=120, force=force_flag)
