"""Test suite for Counterfactual What-If simulation engine."""

import pytest
from backend.app.schemas import WhatIfRequest
from backend.app.services.whatif_service import WhatIfService


def test_whatif_counterfactual_simulation(db_session, seeded_patient):
    """Verify counterfactual feature overrides and probability delta calculation."""
    whatif_svc = WhatIfService(db_session)

    baseline_features = {
        "sbp_latest": 142.0,
        "dbp_latest": 88.0,
        "sbp_mean_7d": 140.0,
        "sleep_duration_last_night": 4.5,
        "baseline_sleep_hours": 7.5,
        "sleep_debt_7d": 6.0,
        "hrv_rmssd_last_night": 18.0,
        "resting_hr_last_night": 76.0,
        "steps_yesterday": 2000.0,
        "medication_taken_last_night": 0.0,
        "age": 60.0,
        "bmi": 30.0,
    }

    # Simulate restoring restorative 8.0 hours of sleep and taking medication
    request = WhatIfRequest(
        sleep_hours=8.0,
        medication_taken=True,
        steps=8000,
        stress_level="low",
    )

    response = whatif_svc.run_counterfactual(
        patient_id=seeded_patient.patient_id,
        baseline_features=baseline_features,
        request=request,
    )

    assert response.patient_id == seeded_patient.patient_id
    assert 0.0 <= response.baseline_probability <= 1.0
    assert 0.0 <= response.new_probability <= 1.0
    # Expected outcome: restorative sleep + adherence should lower predicted episode risk
    assert response.new_probability < response.baseline_probability
    assert response.delta < 0.0

    assert "sleep_duration_last_night" in response.changed_features
    assert "medication_taken_last_night" in response.changed_features
    assert "steps_yesterday" in response.changed_features

    # Safety disclaimer check
    assert "Simulated scenario for clinical discussion" in response.disclaimer
