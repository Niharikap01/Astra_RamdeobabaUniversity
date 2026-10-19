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

from backend.app.auth import hash_password
from backend.app.database import SessionLocal, init_db
from backend.app.models import EHREvent, Patient, Prediction, SensorReading, User
from backend.app.simulation.ehr_simulator import EHRSimulator
from backend.app.simulation.wearable_simulator import WearableSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nightwatch.seed")


def seed_default_users(db) -> None:
    """Ensure default clinician and admin user accounts exist."""
    clinician = db.query(User).filter(User.username == "dr_clinician").first()
    if not clinician:
        clinician = User(
            username="dr_clinician",
            hashed_password=hash_password("nightwatch2026"),
            role="clinician",
            full_name="Dr. Evelyn Reed, MD",
        )
        db.add(clinician)
        db.commit()
        logger.info("Default clinician seeded: dr_clinician / nightwatch2026 (role=clinician)")

    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            hashed_password=hash_password("nightwatch2026"),
            role="admin",
            full_name="NightWatch Administrator",
        )
        db.add(admin)
        db.commit()
        logger.info("Default admin seeded: admin / nightwatch2026 (role=admin)")


def seed_database(num_patients: int = 200, days: int = 120, force: bool = False) -> None:
    """Populate database with synthetic cohort and longitudinal data."""
    init_db()
    db = SessionLocal()

    try:
        # Always ensure user credentials are seeded
        seed_default_users(db)

        if force:
            logger.info("Force flag specified. Clearing existing clinical tables...")
            from backend.app.models import Alert, EHREvent, Patient, Prediction, SensorReading
            db.query(Alert).delete()
            db.query(Prediction).delete()
            db.query(SensorReading).delete()
            db.query(EHREvent).delete()
            db.query(Patient).delete()
            db.commit()

        existing_count = db.query(Patient).count()
        if existing_count > 0 and not force:
            logger.info(f"Database already contains {existing_count} patients. Skipping patient seeding.")
            return

        logger.info(f"Seeding database with {num_patients} patients and {days} days of history...")
        ehr_sim = EHRSimulator(seed=42)
        wearable_sim = WearableSimulator(seed=42)

        cohort = ehr_sim.generate_cohort(num_patients)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        cohort_records = {}

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
            cohort_records[profile.patient_id] = daily_records
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

        logger.info("Backfilling 14-day zero-leakage predictions for seeded cohort...")
        import pandas as pd
        from backend.app.services.ehr_service import EHRService
        from backend.app.services.fusion_service import FusionService
        from backend.app.services.prediction_service import PredictionService
        ehr_svc = EHRService(db)
        fusion_svc = FusionService(db)
        pred_svc = PredictionService(db)

        for p_idx, profile in enumerate(cohort):
            static_dict = ehr_svc.get_patient_static_dict(profile.patient_id)
            if not static_dict:
                continue

            records = cohort_records.get(profile.patient_id, [])
            daily_dicts = [
                {
                    "patient_id": profile.patient_id,
                    "day_index": rec.day_index,
                    "date": rec.date,
                    "sleep_duration_hours": rec.sleep_duration_hours,
                    "deep_sleep_hours": rec.deep_sleep_hours,
                    "rem_sleep_hours": rec.rem_sleep_hours,
                    "awakenings_count": rec.awakenings_count,
                    "sleep_efficiency": rec.sleep_efficiency,
                    "hrv_rmssd": rec.hrv_rmssd,
                    "resting_hr": rec.resting_hr,
                    "steps": rec.steps,
                    "active_minutes": rec.active_minutes,
                    "medication_taken": rec.medication_taken,
                    "morning_sbp": rec.morning_sbp,
                    "morning_dbp": rec.morning_dbp,
                    "evening_sbp": rec.evening_sbp,
                    "evening_dbp": rec.evening_dbp,
                }
                for rec in records
            ]

            # Backfill one prediction per patient per day for the last 14 days using point-in-time features
            for day_idx in range(days - 14, days):
                sub_df = pd.DataFrame(daily_dicts[: day_idx + 1])
                features_dict = fusion_svc.pipeline.compute_features_from_history(static_dict, sub_df)
                prob, risk_level, top_factors = pred_svc.score_features(features_dict)
                pred_time = start_date + timedelta(days=day_idx, hours=22)

                db_pred = Prediction(
                    patient_id=profile.patient_id,
                    probability=round(prob, 4),
                    risk_level=risk_level,
                    model_version="1.1.0",
                    generated_at=pred_time,
                    top_factors=[
                        tf if isinstance(tf, dict) else tf.model_dump()
                        for tf in top_factors
                    ],
                    feature_snapshot=features_dict,
                )
                db.add(db_pred)

            if (p_idx + 1) % 25 == 0 or (p_idx + 1) == len(cohort):
                db.commit()
                logger.info(f"Backfilled 14-day predictions for {p_idx + 1}/{len(cohort)} patients...")

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
