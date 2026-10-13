"""Data Preparation Pipeline for NightWatch.

Orchestrates synthetic cohort generation, zero-leakage longitudinal feature extraction,
patient-level GroupShuffleSplit (70% train, 15% val, 15% test), and dataset persistence.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from backend.app.simulation.ehr_simulator import EHRSimulator, PatientProfile
from backend.app.simulation.wearable_simulator import WearableSimulator
from ml.feature_engineering import FeatureEngineeringPipeline, ALL_NUMERIC_FEATURES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nightwatch.data_prep")


class DataPreparationPipeline:
    """End-to-end dataset preparation and patient-wise splitting pipeline."""

    def __init__(
        self,
        num_patients: int = 200,
        history_days: int = 120,
        seed: int = 42,
        raw_dir: str = "data/raw",
        processed_dir: str = "data/processed",
    ) -> None:
        self.num_patients = num_patients
        self.history_days = history_days
        self.seed = seed
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir

        os.makedirs(raw_dir, exist_ok=True)
        os.makedirs(processed_dir, exist_ok=True)

        self.ehr_sim = EHRSimulator(seed=seed)
        self.wearable_sim = WearableSimulator(seed=seed)
        self.feat_pipeline = FeatureEngineeringPipeline(feature_subset="full")

    def run(self, save_artifacts: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Generate synthetic cohort, compute rolling features, and produce patient-split datasets."""
        logger.info(f"Generating synthetic cohort: {self.num_patients} patients, {self.history_days} days...")
        patients = self.ehr_sim.generate_cohort(self.num_patients)

        patients_data = [p.to_dict() for p in patients]
        patients_df = pd.DataFrame(patients_data)

        all_daily_records: List[Dict] = []
        for p in patients:
            recs = self.wearable_sim.simulate_patient_history(p, days=self.history_days)
            for r in recs:
                all_daily_records.append(asdict(r))

        records_df = pd.DataFrame(all_daily_records)

        if save_artifacts:
            patients_df.to_parquet(os.path.join(self.raw_dir, "patients.parquet"), index=False)
            records_df.to_parquet(os.path.join(self.raw_dir, "records_daily.parquet"), index=False)
            logger.info("Saved raw cohort tables to data/raw/")

        logger.info("Computing zero-leakage rolling feature matrix...")
        feature_rows: List[Dict] = []
        patient_lookup = {p.patient_id: p.to_dict() for p in patients}

        # Warmup period of 14 days to compute rolling 7d/14d statistics
        for pid, group in records_df.groupby("patient_id"):
            static_info = patient_lookup[pid]
            group_sorted = group.sort_values("day_index").reset_index(drop=True)
            for d_idx in range(14, len(group_sorted) - 1):
                # Extract features strictly up to day d_idx (observations strictly before next-day episode d_idx + 1)
                sub_history = group_sorted[group_sorted["day_index"] <= d_idx]
                feat_dict = self.feat_pipeline.compute_features_from_history(
                    static_info=static_info,
                    history_df=sub_history,
                    current_day_index=d_idx + 1,
                )
                feat_dict["patient_id"] = pid
                feat_dict["day_index"] = d_idx

                # Target: Hypertensive episode on day d_idx + 1 (labeled in current row as next_day)
                curr_row = group_sorted.iloc[d_idx]
                feat_dict["target"] = int(curr_row["hypertensive_episode_next_day"])
                feat_dict["lead_time_hours"] = float(curr_row.get("lead_time_hours", 11.0))
                feature_rows.append(feat_dict)
        dataset_df = pd.DataFrame(feature_rows)
        pos_rate = dataset_df["target"].mean()
        logger.info(f"Generated {len(dataset_df)} daily instances. Positive episode rate: {pos_rate:.1%}")

        # Split: Patient-wise GroupShuffleSplit (70% train, 15% val, 15% test)
        train_df, val_df, test_df = self._split_by_patient(dataset_df)

        if save_artifacts:
            dataset_df.to_parquet(os.path.join(self.processed_dir, "features_all.parquet"), index=False)
            train_df.to_parquet(os.path.join(self.processed_dir, "train.parquet"), index=False)
            val_df.to_parquet(os.path.join(self.processed_dir, "val.parquet"), index=False)
            test_df.to_parquet(os.path.join(self.processed_dir, "test.parquet"), index=False)
            logger.info("Saved train, val, and test partitions to data/processed/")

        return train_df, val_df, test_df

    def _split_by_patient(
        self, df: pd.DataFrame, seed: Optional[int] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split dataset by patient_id using GroupShuffleSplit to prevent subject-level data leakage."""
        split_seed = self.seed if seed is None else seed
        gss_train = GroupShuffleSplit(n_splits=1, train_size=0.70, random_state=split_seed)
        train_idx, temp_idx = next(gss_train.split(df, groups=df["patient_id"]))
        train_df = df.iloc[train_idx].copy()
        temp_df = df.iloc[temp_idx].copy()

        # Split remaining 30% evenly into 15% val and 15% test
        gss_val = GroupShuffleSplit(n_splits=1, train_size=0.50, random_state=split_seed)
        val_idx_rel, test_idx_rel = next(gss_val.split(temp_df, groups=temp_df["patient_id"]))
        val_df = temp_df.iloc[val_idx_rel].copy()
        test_df = temp_df.iloc[test_idx_rel].copy()

        train_patients = train_df["patient_id"].nunique()
        val_patients = val_df["patient_id"].nunique()
        test_patients = test_df["patient_id"].nunique()
        logger.info(
            f"Patient Group Split (seed={split_seed}) -> Train: {train_patients} patients ({len(train_df)} rows), "
            f"Val: {val_patients} patients ({len(val_df)} rows), "
            f"Test: {test_patients} patients ({len(test_df)} rows)"
        )
        return train_df, val_df, test_df


if __name__ == "__main__":
    pipeline = DataPreparationPipeline()
    pipeline.run()
