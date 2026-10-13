"""Test suite for Multimodal Fusion and Feature Engineering.

Includes unit test proving zero future target leakage.
"""

import pandas as pd
import pytest
from ml.feature_engineering import FeatureEngineeringPipeline


def test_zero_future_leakage_proof():
    """Prove that injecting or modifying data on or after time t has ZERO impact on features at time t."""
    pipeline = FeatureEngineeringPipeline(feature_subset="full")

    static_info = {
        "patient_id": "NW-LEAK-TEST",
        "age": 60,
        "sex": "M",
        "bmi": 28.0,
        "baseline_sbp": 125.0,
        "baseline_dbp": 80.0,
        "baseline_sleep_hours": 7.0,
        "baseline_hrv_rmssd": 35.0,
        "baseline_resting_hr": 65.0,
    }

    # Create 20 days of historical data
    rows = []
    for d in range(20):
        rows.append({
            "patient_id": "NW-LEAK-TEST",
            "day_index": d,
            "morning_sbp": 120.0 + d * 0.5,
            "morning_dbp": 78.0,
            "evening_sbp": 122.0 + d * 0.5,
            "evening_dbp": 79.0,
            "sleep_duration_hours": 7.0,
            "deep_sleep_hours": 1.2,
            "rem_sleep_hours": 1.4,
            "awakenings_count": 2,
            "sleep_efficiency": 0.88,
            "hrv_rmssd": 35.0,
            "resting_hr": 65.0,
            "steps": 6000,
            "active_minutes": 30,
            "medication_taken": 1,
        })
    df_clean = pd.DataFrame(rows)

    # Compute features for day 15 using data strictly before day 15
    target_day = 15
    feats_baseline = pipeline.compute_features_from_history(
        static_info=static_info,
        history_df=df_clean,
        current_day_index=target_day,
    )

    # Now create an adversarial future: spike SBP to 220, sleep to 1h on days 15..19
    df_corrupted_future = df_clean.copy()
    for d in range(target_day, 20):
        df_corrupted_future.loc[df_corrupted_future["day_index"] == d, "morning_sbp"] = 220.0
        df_corrupted_future.loc[df_corrupted_future["day_index"] == d, "evening_sbp"] = 210.0
        df_corrupted_future.loc[df_corrupted_future["day_index"] == d, "sleep_duration_hours"] = 1.0

    feats_with_future_corrupted = pipeline.compute_features_from_history(
        static_info=static_info,
        history_df=df_corrupted_future,
        current_day_index=target_day,
    )

    # Exact equality assertion: features computed at day 15 MUST BE IDENTICAL
    for k in feats_baseline:
        assert feats_baseline[k] == pytest.approx(feats_with_future_corrupted[k]), (
            f"Leakage detected in feature '{k}': {feats_baseline[k]} != {feats_with_future_corrupted[k]}"
        )


def test_fusion_service_integration(db_session, seeded_patient):
    """Verify FusionService accurately aggregates database sensor readings."""
    from backend.app.services.ehr_service import EHRService
    from backend.app.services.fusion_service import FusionService

    ehr = EHRService(db_session)
    static_dict = ehr.get_patient_static_dict(seeded_patient)

    fusion = FusionService(db_session)
    history_df = fusion.build_patient_history_df(seeded_patient.patient_id, days_lookback=30)
    assert not history_df.empty
    assert len(history_df) >= 25

    features = fusion.compute_current_features(static_dict, history_df)
    assert "sbp_latest" in features
    assert "sleep_duration_last_night" in features
    assert "hrv_rmssd_last_night" in features
    assert "sleep_debt_7d" in features
    assert len(features) >= 55
