"""Tests for JWT Authentication, RBAC, and WebSocket Authentication."""

import pytest
from backend.app.auth import create_access_token, hash_password
from backend.app.models import User, Alert, Patient


def test_login_success(raw_test_client, db_session):
    """POST /api/auth/login with valid credentials returns JWT access token."""
    user = User(
        username="dr_login_test",
        hashed_password=hash_password("nightwatch2026"),
        role="clinician",
        full_name="Dr. Login Test, MD",
    )
    db_session.add(user)
    db_session.commit()

    res = raw_test_client.post(
        "/api/auth/login",
        json={"username": "dr_login_test", "password": "nightwatch2026"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "dr_login_test"
    assert data["user"]["role"] == "clinician"
    assert data["user"]["full_name"] == "Dr. Login Test, MD"


def test_login_invalid_password(raw_test_client, db_session):
    """POST /api/auth/login with incorrect password yields 401 Unauthorized."""
    user = User(
        username="dr_wrong_pass",
        hashed_password=hash_password("nightwatch2026"),
        role="clinician",
        full_name="Dr. Wrong Pass",
    )
    db_session.add(user)
    db_session.commit()

    res = raw_test_client.post(
        "/api/auth/login",
        json={"username": "dr_wrong_pass", "password": "incorrect_password"},
    )
    assert res.status_code == 401
    assert "Incorrect username or password" in res.json()["detail"]


def test_login_unknown_user(raw_test_client):
    """POST /api/auth/login with non-existent username yields 401 Unauthorized."""
    res = raw_test_client.post(
        "/api/auth/login",
        json={"username": "non_existent_dr", "password": "nightwatch2026"},
    )
    assert res.status_code == 401


def test_unauthenticated_request_rejected(raw_test_client, seeded_patient):
    """Patient endpoints reject unauthenticated requests with 401."""
    res = raw_test_client.get("/api/patients")
    assert res.status_code == 401

    res = raw_test_client.get(f"/api/patients/{seeded_patient.patient_id}/profile")
    assert res.status_code == 401

    res = raw_test_client.get(f"/api/patients/{seeded_patient.patient_id}/twin")
    assert res.status_code == 401


def test_invalid_token_rejected(raw_test_client):
    """Requests with malformed or invalid JWT tokens yield 401."""
    headers = {"Authorization": "Bearer invalid.malformed.token"}
    res = raw_test_client.get("/api/patients", headers=headers)
    assert res.status_code == 401


def test_me_endpoint_with_valid_token(raw_test_client, db_session):
    """GET /api/auth/me returns authenticated clinician profile."""
    user = User(
        username="dr_me_test",
        hashed_password=hash_password("nightwatch2026"),
        role="clinician",
        full_name="Dr. Me Test",
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(data={"sub": user.username, "role": user.role})
    headers = {"Authorization": f"Bearer {token}"}

    res = raw_test_client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "dr_me_test"
    assert data["role"] == "clinician"
    assert data["full_name"] == "Dr. Me Test"


def test_note_author_auto_populated_from_jwt(raw_test_client, db_session, seeded_patient):
    """Clinician note author is auto-populated from JWT identity."""
    user = User(
        username="dr_note_author",
        hashed_password=hash_password("nightwatch2026"),
        role="clinician",
        full_name="Dr. Arthur Pendelton",
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(data={"sub": user.username, "role": user.role})
    headers = {"Authorization": f"Bearer {token}"}

    res = raw_test_client.post(
        f"/api/patients/{seeded_patient.patient_id}/notes",
        json={"note": "Patient observed with elevated night-time blood pressure spike."},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["author"] == "Dr. Arthur Pendelton"
    assert data["note"] == "Patient observed with elevated night-time blood pressure spike."


def test_alert_acknowledge_auto_populates_clinician(raw_test_client, db_session, seeded_patient):
    """Alert acknowledgement auto-populates clinician name from JWT."""
    user = User(
        username="dr_ack_test",
        hashed_password=hash_password("nightwatch2026"),
        role="clinician",
        full_name="Dr. Clara Oswald",
    )
    db_session.add(user)

    alert = Alert(
        patient_id=seeded_patient.patient_id,
        risk_level="High",
        probability=0.82,
        message="Simulated High Risk Alert",
        status="open",
    )
    db_session.add(alert)
    db_session.commit()

    token = create_access_token(data={"sub": user.username, "role": user.role})
    headers = {"Authorization": f"Bearer {token}"}

    res = raw_test_client.post(
        f"/api/alerts/{alert.alert_id}/acknowledge",
        json={"comment": "Verified telemetry and initiating patient follow-up"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "acknowledged"
    assert data["acknowledged_by"] == "Dr. Clara Oswald"


def test_websocket_auth_rejection(raw_test_client, seeded_patient):
    """WebSocket connection without valid token is rejected with policy violation (1008)."""
    with pytest.raises(Exception):
        with raw_test_client.websocket_connect(f"/ws/twin/{seeded_patient.patient_id}") as ws:
            pass


def test_websocket_auth_success(raw_test_client, db_session, seeded_patient):
    """WebSocket connection with valid token query parameter connects successfully."""
    user = User(
        username="dr_ws_test",
        hashed_password=hash_password("nightwatch2026"),
        role="clinician",
        full_name="Dr. WS Test",
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(data={"sub": user.username, "role": user.role})
    with raw_test_client.websocket_connect(f"/ws/twin/{seeded_patient.patient_id}?token={token}") as ws:
        data = ws.receive_json()
        assert data["patient_id"] == seeded_patient.patient_id
        assert "prediction" in data
        assert "dynamic_state" in data


def test_role_permission_enforcement(raw_test_client, db_session):
    """Test require_role dependency rejects insufficient roles with 403 Forbidden."""
    from backend.app.auth import require_role
    from fastapi import Depends
    from backend.app.main import app

    @app.get("/api/test-admin-only")
    def admin_only_endpoint(user: User = Depends(require_role(["admin"]))):
        return {"status": "ok", "user": user.username}

    # 1. Clinician trying admin-only endpoint -> 403
    clinician = User(
        username="dr_role_check",
        hashed_password=hash_password("nightwatch2026"),
        role="clinician",
        full_name="Dr. Role Check",
    )
    db_session.add(clinician)
    db_session.commit()

    token_clinician = create_access_token(data={"sub": clinician.username, "role": clinician.role})
    res_clinician = raw_test_client.get(
        "/api/test-admin-only",
        headers={"Authorization": f"Bearer {token_clinician}"},
    )
    assert res_clinician.status_code == 403
    assert "lacks permission" in res_clinician.json()["detail"]

    # 2. Admin trying admin-only endpoint -> 200
    admin = User(
        username="admin_role_check",
        hashed_password=hash_password("nightwatch2026"),
        role="admin",
        full_name="System Admin",
    )
    db_session.add(admin)
    db_session.commit()

    token_admin = create_access_token(data={"sub": admin.username, "role": admin.role})
    res_admin = raw_test_client.get(
        "/api/test-admin-only",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["user"] == "admin_role_check"


def test_role_viewer(raw_test_client, db_session, seeded_patient):
    """Viewer role is read-only: can read data, but 403 on acknowledge, snooze, false-positive, note, BP recheck, What-If, and simulation."""
    import os
    from backend.app.auth import verify_password
    from backend.app.models import Alert
    from backend.scripts.seed import seed_default_users

    # Verify DEMO_MODE seeding
    os.environ["DEMO_MODE"] = "true"
    try:
        seed_default_users(db_session)
        viewer_seeded = db_session.query(User).filter(User.username == "viewer").first()
        assert viewer_seeded is not None
        assert viewer_seeded.role == "viewer"
        assert verify_password("nightwatch2026", viewer_seeded.hashed_password)
    finally:
        os.environ.pop("DEMO_MODE", None)

    viewer = User(
        username="viewer_test_user",
        hashed_password=hash_password("nightwatch2026"),
        role="viewer",
        full_name="Viewer Test",
    )
    db_session.add(viewer)

    alert = Alert(
        patient_id=seeded_patient.patient_id,
        risk_level="High",
        probability=0.88,
        message="Critical systolic excursion alert",
        status="open",
    )
    db_session.add(alert)
    db_session.commit()

    token_viewer = create_access_token(data={"sub": viewer.username, "role": viewer.role})
    headers = {"Authorization": f"Bearer {token_viewer}"}

    # 1. Read operations ARE permitted (200)
    res_get_patient = raw_test_client.get(f"/api/patients/{seeded_patient.patient_id}/profile", headers=headers)
    assert res_get_patient.status_code == 200

    res_get_alerts = raw_test_client.get(f"/api/patients/{seeded_patient.patient_id}/alerts", headers=headers)
    assert res_get_alerts.status_code == 200

    # 2. Forbidden actions return 403
    # Acknowledge
    res_ack = raw_test_client.post(f"/api/alerts/{alert.alert_id}/acknowledge", json={"comment": "trying ack"}, headers=headers)
    assert res_ack.status_code == 403

    # Snooze
    res_snooze = raw_test_client.post(f"/api/alerts/{alert.alert_id}/snooze", json={"snooze_hours": 2.0, "reason": "test"}, headers=headers)
    assert res_snooze.status_code == 403

    # False Positive
    res_fp = raw_test_client.post(f"/api/alerts/{alert.alert_id}/false-positive", json={"reason": "test"}, headers=headers)
    assert res_fp.status_code == 403

    # Add Note
    res_note = raw_test_client.post(f"/api/patients/{seeded_patient.patient_id}/notes", json={"note": "viewer note"}, headers=headers)
    assert res_note.status_code == 403

    # Request BP Recheck
    res_recheck = raw_test_client.post(f"/api/patients/{seeded_patient.patient_id}/request-bp-recheck", json={"priority": "routine", "instructions": "test"}, headers=headers)
    assert res_recheck.status_code == 403

    # What-If
    res_whatif = raw_test_client.post(f"/api/patients/{seeded_patient.patient_id}/what-if", json={"sleep_duration_delta": 1.0}, headers=headers)
    assert res_whatif.status_code == 403

    # Simulation start
    res_sim = raw_test_client.post("/api/simulation/start", json={"step_seconds": 5.0}, headers=headers)
    assert res_sim.status_code == 403


def test_role_clinician(raw_test_client, db_session, seeded_patient):
    """Clinician role can perform clinical triage/notes/what-if, but 403 on simulator stream and scenarios."""
    from backend.app.models import Alert

    clinician = User(
        username="clinician_test_user",
        hashed_password=hash_password("nightwatch2026"),
        role="clinician",
        full_name="Dr. Clinician Test",
    )
    db_session.add(clinician)

    alert = Alert(
        patient_id=seeded_patient.patient_id,
        risk_level="High",
        probability=0.85,
        message="Elevated nighttime risk alert",
        status="open",
    )
    db_session.add(alert)
    db_session.commit()

    token = create_access_token(data={"sub": clinician.username, "role": clinician.role})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Clinical actions ARE permitted (200)
    res_note = raw_test_client.post(f"/api/patients/{seeded_patient.patient_id}/notes", json={"note": "Clinician observation note"}, headers=headers)
    assert res_note.status_code == 200

    res_recheck = raw_test_client.post(f"/api/patients/{seeded_patient.patient_id}/request-bp-recheck", json={"priority": "routine", "instructions": "Recheck cuff"}, headers=headers)
    assert res_recheck.status_code == 200

    res_whatif = raw_test_client.post(f"/api/patients/{seeded_patient.patient_id}/what-if", json={"sleep_duration_delta": 1.5}, headers=headers)
    assert res_whatif.status_code == 200

    res_ack = raw_test_client.post(f"/api/alerts/{alert.alert_id}/acknowledge", json={"comment": "Acknowledged by clinician"}, headers=headers)
    assert res_ack.status_code == 200

    # 2. Simulator controls are FORBIDDEN (403)
    res_start = raw_test_client.post("/api/simulation/start", json={"step_seconds": 5.0}, headers=headers)
    assert res_start.status_code == 403

    res_stop = raw_test_client.post("/api/simulation/stop", headers=headers)
    assert res_stop.status_code == 403

    res_scen = raw_test_client.post(f"/api/simulation/scenario/{seeded_patient.patient_id}", json={"scenario": "force_poor_sleep"}, headers=headers)
    assert res_scen.status_code == 403


def test_role_admin(raw_test_client, db_session, seeded_patient):
    """Admin role has full access: clinical triage, notes, what-if, plus simulator controls."""
    from backend.app.models import Alert

    admin = User(
        username="admin_full_access",
        hashed_password=hash_password("nightwatch2026"),
        role="admin",
        full_name="Admin Test User",
    )
    db_session.add(admin)

    alert = Alert(
        patient_id=seeded_patient.patient_id,
        risk_level="High",
        probability=0.79,
        message="Admin triage alert test",
        status="open",
    )
    db_session.add(alert)
    db_session.commit()

    token = create_access_token(data={"sub": admin.username, "role": admin.role})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Clinical actions ARE permitted
    res_note = raw_test_client.post(f"/api/patients/{seeded_patient.patient_id}/notes", json={"note": "Admin note"}, headers=headers)
    assert res_note.status_code == 200

    res_whatif = raw_test_client.post(f"/api/patients/{seeded_patient.patient_id}/what-if", json={"sleep_duration_delta": 2.0}, headers=headers)
    assert res_whatif.status_code == 200

    # 2. Simulator actions ARE permitted
    res_stop = raw_test_client.post("/api/simulation/stop", headers=headers)
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "ok"

    res_scen = raw_test_client.post(f"/api/simulation/scenario/{seeded_patient.patient_id}", json={"scenario": "force_poor_sleep"}, headers=headers)
    assert res_scen.status_code == 200
    assert res_scen.json()["status"] == "ok"

