"""Test suite for calibrated ML prediction service and explainability."""

import pytest
from backend.app.services.prediction_service import PredictionService


def test_prediction_scoring(db_session, seeded_patient):
    """Verify calibrated probability scoring and risk bands."""
    pred_svc = PredictionService(db_session)

    # Synthetic feature vector representing elevated risk (short sleep, low HRV, elevated SBP)
    high_risk_feats = {
        "sbp_latest": 146.0,
        "dbp_latest": 92.0,
        "sbp_mean_7d": 144.0,
        "sbp_std_7d": 5.2,
        "sleep_duration_last_night": 4.1,
        "sleep_debt_7d": 5.5,
        "poor_sleep_streak": 3.0,
        "hrv_rmssd_last_night": 16.0,
        "hrv_drop_from_personal_baseline": 18.0,
        "resting_hr_last_night": 79.0,
        "medication_taken_last_night": 0.0,
        "hours_since_last_medication": 36.0,
        "steps_yesterday": 1800.0,
        "age": 62.0,
        "bmi": 32.5,
        "diabetes": 1.0,
        "osa": 1.0,
    }

    prob, risk_level, top_factors = pred_svc.score_features(high_risk_feats)
    assert 0.0 <= prob <= 1.0
    assert risk_level in ["Low", "Moderate", "High"]
    assert len(top_factors) >= 3

    # Check top factor structure
    top1 = top_factors[0]
    assert "feature" in top1
    assert "display_name" in top1
    assert "impact" in top1
    assert "reason" in top1
    assert isinstance(top1["is_risk_driver"], bool)

    # Persist prediction
    saved_pred = pred_svc.generate_and_save_prediction(seeded_patient.patient_id, high_risk_feats)
    assert saved_pred.prediction_id is not None
    assert saved_pred.probability == prob
    assert saved_pred.risk_level == risk_level
