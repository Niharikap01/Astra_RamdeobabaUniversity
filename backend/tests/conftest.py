"""Pytest fixtures for NightWatch test suite."""

import os
import sys
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import EHREvent, Patient, SensorReading, Prediction
from backend.app.simulation.ehr_simulator import EHRSimulator
from backend.app.simulation.wearable_simulator import WearableSimulator

# Use in-memory SQLite for fast, isolated testing
TEST_DB_URL = "sqlite:///:memory:"
engine_test = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="session")
def setup_test_db():
    """Create all schema tables in test database."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def db_session(setup_test_db):
    """Provide clean database session for a test."""
    connection = engine_test.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_client(db_session):
    """Provide FastAPI test client with injected test database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_patient(db_session) -> Patient:
    """Seed a single representative patient with 30 days of sensor history."""
    sim_ehr = EHRSimulator(seed=123)
    profile = sim_ehr._generate_patient("NW-TEST-001", "poor_sleep_risk")

    patient = Patient(
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
    db_session.add(patient)

    start_date = datetime.now(timezone.utc) - timedelta(days=30)
    events = sim_ehr.generate_ehr_events(profile, start_date)
    for ev in events:
        db_session.add(EHREvent(
            patient_id=ev["patient_id"],
            event_type=ev["event_type"],
            code=ev["code"],
            description=ev["description"],
            value=ev["value"],
            unit=ev.get("unit", ""),
            event_time=datetime.fromisoformat(ev["event_time"]),
            source=ev["source"],
        ))

    sim_wearable = WearableSimulator(seed=123)
    records = sim_wearable.simulate_patient_history(profile, days=30, start_date=start_date)
    for rec in records:
        for r in rec.to_sensor_readings(start_date):
            db_session.add(SensorReading(
                patient_id=r["patient_id"],
                sensor_type=r["sensor_type"],
                value=r["value"],
                unit=r["unit"],
                recorded_at=datetime.fromisoformat(r["recorded_at"]),
                ingested_at=datetime.fromisoformat(r["ingested_at"]),
                source=r["source"],
            ))

    db_session.commit()
    return patient
