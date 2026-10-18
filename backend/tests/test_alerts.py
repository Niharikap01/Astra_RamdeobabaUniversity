"""Test suite for clinical alerts, deduplication cooldown, snooze duration and expiry."""

import pytest
from datetime import datetime, timedelta, timezone
from backend.app.config import settings
from backend.app.models import Alert, Prediction
from backend.app.services.alert_service import AlertService
from backend.app.schemas import AlertSnoozeRequest, AlertAcknowledgeRequest


def test_alert_generation_at_threshold(db_session, seeded_patient):
    """Verify alert is triggered when predicted probability exceeds high threshold."""
    alert_svc = AlertService(db_session)

    # 1. Prediction below threshold should NOT trigger alert
    pred_low = Prediction(
        patient_id=seeded_patient.patient_id,
        probability=settings.risk_threshold_high - 0.05,
        risk_level="Moderate",
        generated_at=datetime.now(timezone.utc),
        top_factors=[],
    )
    db_session.add(pred_low)
    db_session.commit()

    alert_none = alert_svc.evaluate_and_create_alert(seeded_patient.patient_id, pred_low)
    assert alert_none is None

    # 2. Prediction at or above threshold should trigger alert
    pred_high = Prediction(
        patient_id=seeded_patient.patient_id,
        probability=settings.risk_threshold_high + 0.05,
        risk_level="High",
        generated_at=datetime.now(timezone.utc),
        top_factors=[{"feature": "sbp_mean_7d", "display_name": "7-day Mean Systolic BP", "reason": "152 mmHg"}],
    )
    db_session.add(pred_high)
    db_session.commit()

    alert = alert_svc.evaluate_and_create_alert(seeded_patient.patient_id, pred_high)
    assert alert is not None
    assert alert.status == "open"
    assert alert.risk_level == "High"
    assert alert.probability == pred_high.probability
    assert "HIGH RISK ALERT" in alert.message


def test_alert_cooldown_open_acknowledged_snoozed(db_session, seeded_patient):
    """Verify cooldown suppresses duplicate alerts for open, acknowledged, and snoozed alerts."""
    alert_svc = AlertService(db_session)
    now = datetime.now(timezone.utc)

    pred_high = Prediction(
        patient_id=seeded_patient.patient_id,
        probability=settings.risk_threshold_high + 0.10,
        risk_level="High",
        generated_at=now,
        top_factors=[],
    )
    db_session.add(pred_high)
    db_session.commit()

    # Case A: Open alert suppresses second alert within cooldown
    first_alert = alert_svc.evaluate_and_create_alert(seeded_patient.patient_id, pred_high)
    assert first_alert is not None

    dup_alert = alert_svc.evaluate_and_create_alert(seeded_patient.patient_id, pred_high)
    assert dup_alert is None, "Should suppress duplicate alert while first alert is open"

    # Case B: Acknowledging the alert STILL suppresses duplicate within cooldown window
    alert_svc.acknowledge_alert(first_alert.alert_id, clinician_name="Dr. Smith", comment="Reviewed cuff telemetry")
    dup_ack = alert_svc.evaluate_and_create_alert(seeded_patient.patient_id, pred_high)
    assert dup_ack is None, "Cooldown must consider acknowledged alerts as well as open ones"

    # Case C: Snoozing the alert STILL suppresses duplicate within cooldown window
    alert_svc.snooze_alert(first_alert.alert_id, clinician_name="Dr. Smith", snooze_hours=4.0, reason="Recheck pending")
    dup_snooze = alert_svc.evaluate_and_create_alert(seeded_patient.patient_id, pred_high)
    assert dup_snooze is None, "Cooldown must consider snoozed alerts as well as open ones"

    # Case D: Past cooldown window (> 24h) and expired snooze, a new alert CAN fire
    first_alert.created_at = now - timedelta(hours=settings.alert_cooldown_hours + 1)
    first_alert.snoozed_until = now - timedelta(hours=settings.alert_cooldown_hours + 1)
    db_session.commit()

    new_alert_after_cooldown = alert_svc.evaluate_and_create_alert(seeded_patient.patient_id, pred_high)
    assert new_alert_after_cooldown is not None, "New alert must fire once cooldown has expired"


def test_snooze_duration_stored_and_expires(db_session, seeded_patient):
    """Verify snooze duration is stored and expires automatically when time has elapsed."""
    alert_svc = AlertService(db_session)
    now = datetime.now(timezone.utc)

    alert = Alert(
        patient_id=seeded_patient.patient_id,
        risk_level="High",
        probability=0.75,
        message="Test alert for snooze expiry",
        created_at=now - timedelta(hours=2),
        status="open",
    )
    db_session.add(alert)
    db_session.commit()

    # Snooze for 2.0 hours
    snoozed = alert_svc.snooze_alert(
        alert_id=alert.alert_id,
        clinician_name="Dr. Jones",
        snooze_hours=2.0,
        reason="Patient resting seated",
    )
    assert snoozed is not None
    assert snoozed.status == "snoozed"
    assert snoozed.snooze_duration_minutes == 120
    assert snoozed.snoozed_until is not None
    assert snoozed.snooze_reason == "Patient resting seated"
    assert snoozed.acknowledged_by == "Dr. Jones"

    # While still within snooze duration, snooze does NOT expire
    expired_count = alert_svc.check_and_expire_snoozes(seeded_patient.patient_id)
    assert expired_count == 0
    assert snoozed.status == "snoozed"

    # Fast forward time: simulate snoozed_until in the past
    snoozed.snoozed_until = now - timedelta(minutes=5)
    db_session.commit()

    # Expiration check should revert status to 'open'
    expired_count = alert_svc.check_and_expire_snoozes(seeded_patient.patient_id)
    assert expired_count == 1
    assert snoozed.status == "open"
    assert snoozed.snoozed_until is None


def test_snooze_requires_reason(db_session, seeded_patient, test_client):
    """Verify snooze fails with 422 or 400 if reason is omitted or empty."""
    alert = Alert(
        patient_id=seeded_patient.patient_id,
        risk_level="High",
        probability=0.75,
        message="Test alert for snooze reason requirement",
        created_at=datetime.now(timezone.utc),
        status="open",
    )
    db_session.add(alert)
    db_session.commit()

    res = test_client.post(
        f"/api/alerts/{alert.alert_id}/snooze",
        json={"clinician_name": "Dr. Clinician", "snooze_hours": 2.0, "reason": ""},
    )
    assert res.status_code in [400, 422]


def test_alerts_fire_in_simulation_run(db_session, seeded_patient):
    """Verify alerts fire during high-risk simulated reading ingestion (alert count > 0)."""
    from backend.app.schemas import SensorReadingCreate
    from backend.app.services.twin_service import TwinService
    from backend.app.models import SensorReading
    import asyncio

    twin_svc = TwinService(db_session)
    now = datetime.now(timezone.utc)

    # Populate 7 days of elevated home BP readings to elevate sbp_mean_7d / dbp_mean_7d
    for day in range(7, 0, -1):
        t = now - timedelta(days=day)
        db_session.add(SensorReading(
            patient_id=seeded_patient.patient_id,
            sensor_type="home_sbp",
            value=155.0,
            unit="mmHg",
            recorded_at=t,
            ingested_at=t,
            source="home_cuff",
        ))
        db_session.add(SensorReading(
            patient_id=seeded_patient.patient_id,
            sensor_type="home_dbp",
            value=98.0,
            unit="mmHg",
            recorded_at=t,
            ingested_at=t,
            source="home_cuff",
        ))
    db_session.commit()

    # Ingest new severe hypertensive cuff reading via the live event pipeline
    reading = SensorReadingCreate(
        sensor_type="home_sbp",
        value=162.0,
        unit="mmHg",
        recorded_at=now,
        source="home_cuff",
    )
    asyncio.run(twin_svc.process_new_reading_pipeline(seeded_patient.patient_id, reading))

    # Check alert feed for patient
    alerts = twin_svc.alert_service.get_patient_alerts(seeded_patient.patient_id)
    assert len(alerts) > 0, f"Expected alert count > 0 during high-risk reading ingestion, got {len(alerts)}"
    high_alerts = [a for a in alerts if a.risk_level == "High"]
    assert len(high_alerts) > 0
    assert high_alerts[0].status == "open"


def test_thresholds_endpoint(test_client):
    """Verify /api/thresholds endpoint returns operating thresholds matching config."""
    res = test_client.get("/api/thresholds")
    assert res.status_code == 200
    data = res.json()
    assert "moderate" in data
    assert "high" in data
    assert data["moderate"] == pytest.approx(settings.risk_threshold_moderate, 0.001)
    assert data["high"] == pytest.approx(settings.risk_threshold_high, 0.001)
    assert data["moderate"] < data["high"]
    assert data["cooldown_hours"] == settings.alert_cooldown_hours
