"""Test suite for Digital Twin state construction and rules."""

import pytest
from backend.app.services.twin_service import TwinService


def test_twin_construction(db_session, seeded_patient):
    """Verify Twin service generates complete, validated twin payload."""
    twin_svc = TwinService(db_session)
    twin = twin_svc.build_twin(seeded_patient.patient_id)

    assert twin is not None
    assert twin.patient_id == seeded_patient.patient_id
    assert twin.static_profile.age == seeded_patient.age
    assert twin.static_profile.bmi == pytest.approx(seeded_patient.bmi, 0.1)

    # Dynamic state
    assert twin.dynamic_state.latest_sbp > 0
    assert twin.dynamic_state.latest_dbp > 0
    assert twin.dynamic_state.sleep_last_night > 0

    # Prediction
    assert 0.0 <= twin.prediction.probability <= 1.0
    assert twin.prediction.risk_level in ["Low", "Moderate", "High"]
    assert len(twin.top_factors) > 0

    # Sleep Fingerprint
    assert twin.sleep_fingerprint.status in ["optimal", "degraded", "acute_deficit"]
    assert len(twin.sleep_fingerprint.summary) > 10

    # Recommended Actions (rule-based suggestions, non-prescriptive)
    assert len(twin.recommended_actions) >= 1
    for act in twin.recommended_actions:
        assert isinstance(act, str)
        # Verify non-prescriptive phrasing
        assert "prescribe" not in act.lower()
