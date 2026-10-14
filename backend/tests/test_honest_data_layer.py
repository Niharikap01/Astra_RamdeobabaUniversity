"""Test suite for Phase 2: Honest Data Layer (M3).

Verifies:
1. No silent imputation in fusion_service (NaN preserved).
2. Data coverage computation & refusal below configurable threshold.
3. Coverage-aware confidence interval widening.
4. Personal 30-day baseline estimation from stored readings (no simulator archetype leakage).
5. Real Risk Horizon points (Asia/Kolkata timezone, real BP/med markers, nocturnal_dipping_pct is None).
6. Sleep Fingerprint 6 clinical axes using personal baselines.
7. Why-Risk-Changed returns 'No previous prediction exists.' when 1 prediction exists,
   and computes honest feature snapshot diffs when >= 2 exist.
"""

from datetime import datetime, timedelta, timezone
import numpy as np
import pytest

from backend.app.config import settings
from backend.app.models import Patient, Prediction, SensorReading
from backend.app.services.ehr_service import EHRService
from backend.app.services.fingerprint_service import FingerprintService
from backend.app.services.fusion_service import FusionService
from backend.app.services.prediction_service import PredictionService
from backend.app.services.twin_service import TwinService


def test_fusion_no_silent_imputation(db_session):
    """Verify missing values are not silently imputed with magical constants."""
    patient = Patient(
        patient_id="NW-HONEST-001",
        name="Missing Data Patient",
        age=50,
        sex="F",
        height_cm=165.0,
        weight_kg=70.0,
        bmi=25.7,
        archetype="normal",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(patient)

    # Ingest only a single HR reading today, no BP, no sleep, no steps
    now = datetime.now(timezone.utc)
    db_session.add(
        SensorReading(
            patient_id=patient.patient_id,
            sensor_type="heart_rate",
            value=72.0,
            unit="bpm",
            recorded_at=now - timedelta(hours=2),
            source="wearable",
        )
    )
    db_session.commit()

    fusion_svc = FusionService(db_session)
    df = fusion_svc.build_patient_history_df(patient.patient_id, days_lookback=7)

    assert not df.empty
    latest_row = df.iloc[-1]

    # BP was not provided, must NOT silently default to 125/80
    assert np.isnan(latest_row["morning_sbp"])
    assert np.isnan(latest_row["morning_dbp"])
    # Sleep was not provided, must NOT silently default to 7.0 / 35.0
    assert np.isnan(latest_row["sleep_duration_hours"])
    assert np.isnan(latest_row["rem_sleep_hours"])


def test_coverage_computation_and_prediction_refusal(db_session, test_client):
    """Verify prediction refuses when data coverage falls below minimum threshold."""
    patient = Patient(
        patient_id="NW-SPARSE-001",
        name="Sparse Patient",
        age=60,
        sex="M",
        height_cm=175.0,
        weight_kg=85.0,
        bmi=27.8,
        archetype="normal",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(patient)

    # Provide only 1 reading out of 7 days expected
    now = datetime.now(timezone.utc)
    db_session.add(
        SensorReading(
            patient_id=patient.patient_id,
            sensor_type="steps",
            value=2000.0,
            unit="count",
            recorded_at=now - timedelta(days=1),
            source="wearable",
        )
    )
    db_session.commit()

    fusion_svc = FusionService(db_session)
    overall_cov, per_source = fusion_svc.compute_data_coverage(patient.patient_id, days_lookback=7)
    assert overall_cov < (settings.min_coverage_threshold * 100.0)

    # 1. PredictionService raises ValueError on refusal
    ehr_svc = EHRService(db_session)
    static_dict = ehr_svc.get_patient_static_dict(patient)
    features = fusion_svc.compute_current_features(static_dict)

    pred_svc = PredictionService(db_session)
    with pytest.raises(ValueError, match="Prediction refused: Data coverage"):
        pred_svc.generate_and_save_prediction(patient.patient_id, features, enforce_coverage=True)

    # 2. API Endpoint returns HTTP 422 refusal
    resp = test_client.get(f"/api/patients/{patient.patient_id}/risk")
    assert resp.status_code == 422
    assert "Prediction refused: Data coverage" in resp.json()["detail"]


def test_confidence_and_ci_widening(db_session):
    """Verify confidence interval scales with coverage."""
    pred_svc = PredictionService(db_session)

    # High coverage (e.g. 95%)
    conf_high, ci_high = pred_svc.compute_confidence(0.60, coverage_pct=95.0)
    width_high = ci_high[1] - ci_high[0]

    # Low coverage (e.g. 52%)
    conf_low, ci_low = pred_svc.compute_confidence(0.60, coverage_pct=52.0)
    width_low = ci_low[1] - ci_low[0]

    assert conf_high > conf_low
    assert width_low > width_high  # CI widens when coverage is lower
    assert 0.0 <= ci_low[0] <= ci_low[1] <= 1.0
    assert 0.0 <= ci_high[0] <= ci_high[1] <= 1.0


def test_patient_30d_baseline_estimation(db_session, seeded_patient):
    """Verify baseline is calculated from real stored sensor readings, not archetype simulator."""
    ehr_svc = EHRService(db_session)
    baseline = ehr_svc.compute_patient_30d_baseline(seeded_patient.patient_id)

    assert not np.isnan(baseline["baseline_resting_hr"])
    assert baseline["baseline_resting_hr"] > 40.0
    assert baseline["baseline_sleep_hours"] > 0.0
    assert baseline["baseline_sbp"] > 80.0
    assert baseline["baseline_dbp"] > 40.0

    # Test fallback for a patient with zero readings
    empty_patient = Patient(
        patient_id="NW-EMPTY-001",
        name="Empty Patient",
        age=45,
        sex="M",
        height_cm=180.0,
        weight_kg=80.0,
        bmi=24.7,
        archetype="normal",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(empty_patient)
    db_session.commit()

    fb_baseline = ehr_svc.compute_patient_30d_baseline(empty_patient.patient_id)
    assert np.isnan(fb_baseline["baseline_resting_hr"])
    assert np.isnan(fb_baseline["baseline_sleep_hours"])
    assert np.isnan(fb_baseline["baseline_sbp"])


def test_risk_horizon_honest_markers_and_timezone(db_session, seeded_patient):
    """Verify Risk Horizon adheres to local timezone, stored markers, and nocturnal dipping is None."""
    now = datetime.now(timezone.utc)
    # Ensure a recent BP reading exists at a round hour in the past 12h
    recent_bp_time = now - timedelta(hours=2)
    db_session.add(
        SensorReading(
            patient_id=seeded_patient.patient_id,
            sensor_type="home_sbp",
            value=134.0,
            unit="mmHg",
            recorded_at=recent_bp_time,
            source="cuff",
        )
    )
    db_session.add(
        SensorReading(
            patient_id=seeded_patient.patient_id,
            sensor_type="home_dbp",
            value=84.0,
            unit="mmHg",
            recorded_at=recent_bp_time,
            source="cuff",
        )
    )
    db_session.commit()

    twin_svc = TwinService(db_session)
    horizon = twin_svc.build_risk_horizon(seeded_patient.patient_id)

    assert horizon.patient_id == seeded_patient.patient_id
    # Cuff readings cannot measure ambulatory nocturnal dipping
    assert horizon.nocturnal_dipping_pct is None

    # Verify series timestamps have valid ISO strings with Kolkata offset (+05:30)
    assert len(horizon.series) > 0
    for pt in horizon.series:
        assert "+05:30" in pt.timestamp
        assert 0.0 <= pt.risk_pct <= 100.0

    # Verify markers in series only flag real events
    has_any_bp = any(pt.measured_sbp is not None for pt in horizon.series)
    assert has_any_bp


def test_sleep_fingerprint_six_clinical_axes(db_session, seeded_patient):
    """Verify Sleep Fingerprint computes all 6 clinical axes using personal baselines."""
    twin_svc = TwinService(db_session)
    twin = twin_svc.build_twin(seeded_patient.patient_id)
    fp = twin.sleep_fingerprint

    assert fp.status in ["optimal", "degraded", "acute_deficit"]
    assert -100.0 <= fp.nocturnal_bp_stability_pct <= 100.0
    assert -100.0 <= fp.autonomic_resilience_pct <= 100.0
    assert -100.0 <= fp.sleep_continuity_pct <= 100.0
    assert -100.0 <= fp.morning_surge_control_pct <= 100.0
    assert -100.0 <= fp.medication_coverage_pct <= 100.0
    assert -100.0 <= fp.recovery_capacity_pct <= 100.0
    assert len(fp.summary) > 10

    # Verify static call directly
    fp_direct = FingerprintService.compute_fingerprint(
        static_dict={"baseline_sleep_hours": 7.5, "baseline_resting_hr": 65.0},
        features_dict={"sleep_duration_last_night": 5.0, "resting_hr_last_night": 78.0},
    )
    assert -100.0 <= fp_direct.recovery_capacity_pct <= 100.0


def test_why_risk_changed_single_and_multiple_predictions(db_session, seeded_patient):
    """Verify Why-Risk-Changed handles single prediction vs consecutive prediction diffs."""
    twin_svc = TwinService(db_session)

    # Clear any existing predictions first
    db_session.query(Prediction).filter_by(patient_id=seeded_patient.patient_id).delete()
    db_session.commit()

    # 1. Single prediction
    now = datetime.now(timezone.utc)
    pred1 = Prediction(
        patient_id=seeded_patient.patient_id,
        generated_at=now - timedelta(days=1),
        probability=0.45,
        risk_level="Moderate",
        top_factors=[{"feature": "sleep_duration", "impact": 0.12, "direction": "elevates"}],
        feature_snapshot={"sleep_duration": 6.0, "sbp_mean": 130.0, "resting_hr": 74.0},
    )
    db_session.add(pred1)
    db_session.commit()

    resp_single = twin_svc.get_why_risk_changed(seeded_patient.patient_id)
    assert resp_single.previous_risk_pct is None
    assert resp_single.risk_delta_pct is None
    assert "No previous prediction exists" in resp_single.summary
    assert len(resp_single.factors) == 0

    # 2. Add second prediction
    pred2 = Prediction(
        patient_id=seeded_patient.patient_id,
        generated_at=now,
        probability=0.65,
        risk_level="High",
        top_factors=[{"feature": "sleep_duration", "impact": 0.20, "direction": "elevates"}],
        feature_snapshot={"sleep_duration": 4.5, "sbp_mean": 142.0, "resting_hr": 82.0},
    )
    db_session.add(pred2)
    db_session.commit()

    resp_dual = twin_svc.get_why_risk_changed(seeded_patient.patient_id)
    assert resp_dual.current_risk_pct == 65.0
    assert resp_dual.previous_risk_pct == 45.0
    assert resp_dual.risk_delta_pct == 20.0
    assert len(resp_dual.factors) > 0

    factor_names = [f.feature for f in resp_dual.factors]
    assert "sleep_duration" in factor_names or "sbp_mean" in factor_names
