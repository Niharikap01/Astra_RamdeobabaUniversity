"""Full API endpoint integration test suite for NightWatch."""

from datetime import datetime, timezone
import pytest


def test_health_check(test_client):
    """GET /health returns 200 healthy when DB and model are available."""
    res = test_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "NightWatch"
    assert data["database"] == "connected"
    assert data["model_loaded"] is True


def test_health_check_db_failure(test_client):
    """GET /health returns 503 unhealthy when database SELECT 1 fails."""
    from unittest.mock import MagicMock
    from backend.app.database import get_db
    from backend.app.main import app

    mock_session = MagicMock()
    mock_session.execute.side_effect = Exception("Database connection failure")

    def failing_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = failing_get_db
    try:
        res = test_client.get("/health")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_health_check_model_not_loaded(test_client, monkeypatch):
    """GET /health returns 503 unhealthy when model is not loaded."""
    from backend.app.services.prediction_service import PredictionService

    monkeypatch.setattr(PredictionService, "_model", None)
    res = test_client.get("/health")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "unhealthy"
    assert data["model_loaded"] is False


def test_config_app_port_env(monkeypatch):
    """Verify that Settings reads APP_PORT from environment (port == 9123)."""
    from backend.app.config import Settings

    monkeypatch.setenv("APP_PORT", "9123")
    custom_settings = Settings()
    assert custom_settings.port == 9123



def test_patients_endpoints(test_client, seeded_patient, db_session):
    """GET /api/patients and GET /api/patients/{id}/profile"""
    # 1. List
    res_list = test_client.get("/api/patients")
    assert res_list.status_code == 200
    patients = res_list.json()
    assert len(patients) >= 1
    p_data = next(p for p in patients if p["patient_id"] == seeded_patient.patient_id)
    assert "data_coverage_pct" in p_data

    # 2. Profile
    res_prof = test_client.get(f"/api/patients/{seeded_patient.patient_id}/profile")
    assert res_prof.status_code == 200
    prof = res_prof.json()
    assert prof["patient_id"] == seeded_patient.patient_id
    assert "baseline_sbp" in prof
    assert "diagnoses" in prof
    assert "data_coverage_pct" in prof

    # 3. Patient without prediction returns null risk level and probability
    from backend.app.models import Patient
    p_unpredicted = Patient(
        patient_id="NW-TEST-UNPREDICTED",
        name="Unpredicted Patient",
        age=50,
        sex="M",
        height_cm=175.0,
        weight_kg=75.0,
        bmi=24.5,
        archetype="healthy_resilient",
    )
    db_session.add(p_unpredicted)
    db_session.commit()

    res_unpred = test_client.get(f"/api/patients/{p_unpredicted.patient_id}/profile")
    assert res_unpred.status_code == 200
    unpred_prof = res_unpred.json()
    assert unpred_prof["latest_risk_level"] is None
    assert unpred_prof["latest_probability"] is None


def test_get_endpoints_are_readonly(test_client, seeded_patient, db_session):
    """GET endpoints must not write prediction rows to the database."""
    from backend.app.models import Prediction
    pred_count_before = db_session.query(Prediction).filter_by(patient_id=seeded_patient.patient_id).count()

    res_twin = test_client.get(f"/api/patients/{seeded_patient.patient_id}/twin")
    assert res_twin.status_code == 200

    res_horizon = test_client.get(f"/api/patients/{seeded_patient.patient_id}/risk-horizon")
    assert res_horizon.status_code == 200

    pred_count_after = db_session.query(Prediction).filter_by(patient_id=seeded_patient.patient_id).count()
    assert pred_count_before == pred_count_after


def test_digital_twin_endpoints(test_client, seeded_patient):
    """GET /api/patients/{id}/twin and GET /api/patients/{id}/sleep-fingerprint"""
    # 1. Twin
    res_twin = test_client.get(f"/api/patients/{seeded_patient.patient_id}/twin")
    assert res_twin.status_code == 200
    twin = res_twin.json()
    assert twin["patient_id"] == seeded_patient.patient_id
    assert "static_profile" in twin
    assert "dynamic_state" in twin
    assert "prediction" in twin
    assert "sleep_fingerprint" in twin
    assert "recommended_actions" in twin
    assert "disclaimer" in twin

    # 2. Sleep Fingerprint
    res_fp = test_client.get(f"/api/patients/{seeded_patient.patient_id}/sleep-fingerprint")
    assert res_fp.status_code == 200
    fp = res_fp.json()
    assert "sleep_duration_deviation_pct" in fp
    assert "hrv_deviation_pct" in fp
    assert "status" in fp
    assert "summary" in fp


def test_risk_and_history_endpoints(test_client, seeded_patient):
    """GET /api/patients/{id}/risk and GET /api/patients/{id}/risk-history"""
    # First get twin to ensure initial prediction exists
    test_client.get(f"/api/patients/{seeded_patient.patient_id}/twin")

    # Risk
    res_risk = test_client.get(f"/api/patients/{seeded_patient.patient_id}/risk")
    assert res_risk.status_code == 200
    risk = res_risk.json()
    assert 0.0 <= risk["probability"] <= 1.0
    assert risk["risk_level"] in ["Low", "Moderate", "High"]

    # History
    res_hist = test_client.get(f"/api/patients/{seeded_patient.patient_id}/risk-history")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 1


def test_whatif_endpoint(test_client, seeded_patient):
    """POST /api/patients/{id}/what-if"""
    payload = {
        "sleep_hours": 8.0,
        "medication_taken": True,
        "steps": 7500,
        "stress_level": "low",
    }
    res = test_client.post(f"/api/patients/{seeded_patient.patient_id}/what-if", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "baseline_probability" in data
    assert "new_probability" in data
    assert "delta" in data
    assert "disclaimer" in data


def test_sensor_ingestion_and_pipeline_trigger(test_client, seeded_patient):
    """POST /api/patients/{id}/sensor-readings triggers live pipeline:
    new prediction row, alert check, and state rebuild.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "sensor_type": "home_sbp",
        "value": 152.0,  # Acute high cuff reading
        "unit": "mmHg",
        "recorded_at": now_iso,
        "source": "home_bp_cuff",
    }
    res = test_client.post(f"/api/patients/{seeded_patient.patient_id}/sensor-readings", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["patient_id"] == seeded_patient.patient_id
    assert data["sensor_type"] == "home_sbp"
    assert data["value"] == 152.0

    # Verify new prediction row exists
    res_risk = test_client.get(f"/api/patients/{seeded_patient.patient_id}/risk")
    assert res_risk.status_code == 200


def test_risk_horizon_and_why_risk_changed(test_client, seeded_patient):
    """GET /api/patients/{id}/risk-horizon and GET /api/patients/{id}/why-risk-changed"""
    # 1. Risk Horizon
    res_hor = test_client.get(f"/api/patients/{seeded_patient.patient_id}/risk-horizon")
    assert res_hor.status_code == 200
    hor = res_hor.json()
    assert hor["patient_id"] == seeded_patient.patient_id
    assert len(hor["series"]) >= 15
    assert "peak_risk_window" in hor
    assert "data_coverage_pct" in hor
    assert "nocturnal_dipping_pct" in hor

    # 2. Why Risk Changed
    res_why = test_client.get(f"/api/patients/{seeded_patient.patient_id}/why-risk-changed")
    assert res_why.status_code == 200
    why = res_why.json()
    assert "current_risk_pct" in why
    assert "factors" in why
    assert "trust_statement" in why


def test_alert_lifecycle_and_notes(test_client, seeded_patient, db_session):
    """Alert creation, acknowledge, snooze, false positive, and clinician notes."""
    from backend.app.models import Alert
    # Insert test open alert
    alert = Alert(
        patient_id=seeded_patient.patient_id,
        risk_level="High",
        probability=0.78,
        message="Test alert message",
        created_at=datetime.now(timezone.utc),
        status="open",
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # 1. Get alerts
    res_alerts = test_client.get(f"/api/patients/{seeded_patient.patient_id}/alerts")
    assert res_alerts.status_code == 200
    alerts = res_alerts.json()
    assert any(a["alert_id"] == alert.alert_id for a in alerts)

    # 2. Snooze alert
    res_snooze = test_client.post(
        f"/api/alerts/{alert.alert_id}/snooze",
        json={"clinician_name": "Dr. Sarah Adams", "snooze_hours": 3.0, "reason": "Awaiting repeat cuff reading"},
    )
    assert res_snooze.status_code == 200
    assert res_snooze.json()["status"] == "snoozed"

    # 2. Acknowledge alert
    res_ack = test_client.post(
        f"/api/alerts/{alert.alert_id}/acknowledge",
        json={"clinician_name": "Dr. Sarah Adams", "comment": "Patient notified to rest seated"},
    )
    assert res_ack.status_code == 200
    assert res_ack.json()["status"] == "acknowledged"

    # 3. Mark false positive on a second alert
    alert2 = Alert(
        patient_id=seeded_patient.patient_id,
        risk_level="High",
        probability=0.72,
        message="Second alert",
        created_at=datetime.now(timezone.utc),
        status="open",
    )
    db_session.add(alert2)
    db_session.commit()

    res_fp = test_client.post(
        f"/api/alerts/{alert2.alert_id}/false-positive",
        json={"clinician_name": "Dr. Sarah Adams", "reason": "Patient had acute dental surgery"},
    )
    assert res_fp.status_code == 200
    assert res_fp.json()["status"] == "false_positive"

    # 4. Add clinician note
    res_note = test_client.post(
        f"/api/patients/{seeded_patient.patient_id}/notes",
        json={"note": "Telemetry review completed. Adherence confirmed."},
    )
    assert res_note.status_code == 200
    assert res_note.json()["note"] == "Telemetry review completed. Adherence confirmed."

    # 5. Request BP Recheck
    res_recheck = test_client.post(
        f"/api/patients/{seeded_patient.patient_id}/request-bp-recheck",
        json={"priority": "urgent", "instructions": "Take seated reading after 5 min rest."},
    )
    assert res_recheck.status_code == 200
    assert res_recheck.json()["status"] == "ok"


def test_simulation_endpoints(test_client, db_session):
    """GET/POST /api/simulation status, start, stop."""
    from backend.app.auth import get_current_user
    from backend.app.main import app
    from backend.app.models import User

    # Status
    res_st = test_client.get("/api/simulation/status")
    assert res_st.status_code == 200
    assert "is_running" in res_st.json()

    # Clinician is forbidden from simulator controls
    res_forbidden = test_client.post("/api/simulation/stop")
    assert res_forbidden.status_code == 403

    # Admin is permitted
    admin_user = User(
        username="admin_sim_test",
        hashed_password="hash",
        role="admin",
        full_name="Admin Sim",
    )
    old_override = app.dependency_overrides[get_current_user]
    try:
        app.dependency_overrides[get_current_user] = lambda: admin_user
        res_stop = test_client.post("/api/simulation/stop")
        assert res_stop.status_code == 200
        assert res_stop.json()["status"] == "ok"
    finally:
        app.dependency_overrides[get_current_user] = old_override


def test_websocket_stream(test_client, seeded_patient):
    """WS /ws/twin/{patient_id} establishes connection and receives initial state."""
    with test_client.websocket_connect(f"/ws/twin/{seeded_patient.patient_id}") as ws:
        initial_data = ws.receive_json()
        assert initial_data["patient_id"] == seeded_patient.patient_id
        assert "prediction" in initial_data
        assert "dynamic_state" in initial_data

        ws.send_text("ping")
        pong = ws.receive_text()
        assert pong == "pong"
        ws.send_text("close")


def test_readings_series_endpoint(test_client, seeded_patient):
    """GET /api/patients/{id}/readings-series returns Kolkata timestamps and estimated personal baselines."""
    res = test_client.get(f"/api/patients/{seeded_patient.patient_id}/readings-series?days=30")
    assert res.status_code == 200
    data = res.json()

    assert data["patient_id"] == seeded_patient.patient_id
    assert data["days"] == 30
    assert data["timezone"] == "Asia/Kolkata"
    assert "baseline_30d" in data
    assert "sbp" in data["baseline_30d"]
    assert "sleep_duration" in data["baseline_30d"]

    assert len(data["series"]) == 30
    first_pt = data["series"][0]
    assert "+05:30" in first_pt["timestamp"]
    for key in ["sbp", "dbp", "sleep_duration", "sleep_efficiency", "hrv_rmssd", "resting_hr", "steps", "medication_taken"]:
        assert key in first_pt


def test_whatif_endpoint_fields(test_client, seeded_patient):
    """POST /api/patients/{id}/what-if returns delta, new_band, and effect_note."""
    res = test_client.post(
        f"/api/patients/{seeded_patient.patient_id}/what-if",
        json={"sleep_hours": 8.0, "medication_taken": True, "steps": 9000},
    )
    assert res.status_code == 200
    data = res.json()
    assert "baseline_probability" in data
    assert "new_probability" in data
    assert "delta" in data
    assert "new_band" in data
    assert "effect_note" in data
    assert "changed_features" in data
    assert "sleep_duration_last_night" in data["changed_features"]
    assert "sleep_hours" not in data["changed_features"]



def test_smart_ring_coverage_not_zero(db_session, seeded_patient):
    """Ensure data coverage computation does not truncate smart ring morning readings to 0%."""
    from backend.app.services.fusion_service import FusionService
    fusion_svc = FusionService(db_session)
    overall_cov, per_source = fusion_svc.compute_data_coverage(seeded_patient.patient_id, days_lookback=1)
    assert per_source["smart_ring"] > 0.0
    assert overall_cov > 0.0
