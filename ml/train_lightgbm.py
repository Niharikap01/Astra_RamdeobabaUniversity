"""LightGBM Multimodal Training and Multi-Seed Ablation Pipeline for NightWatch.

Trains baseline, intermediate, and full digital twin models with early stopping,
strong tree regularization (to eliminate overfitting on patient groups),
isotonic probability calibration, multi-seed ablation evaluation (5 split seeds),
bootstrap 95% confidence intervals, and automated artifact generation.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping
from sklearn.calibration import CalibratedClassifierCV

from ml.data_preparation import DataPreparationPipeline
from ml.evaluate import ModelEvaluator
from ml.feature_engineering import FEATURE_SETS, ALL_NUMERIC_FEATURES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nightwatch.train")

MODEL_VERSION = "1.1.0"
EVALUATION_SEEDS = [42, 101, 202, 303, 404]


class LightGBMTrainer:
    """Production LightGBM trainer with regularized hyperparameters and multi-seed benchmarking."""

    def __init__(
        self,
        artifacts_dir: str = "ml/artifacts",
        data_dir: str = "data/processed",
        seed: int = 42,
    ) -> None:
        self.artifacts_dir = artifacts_dir
        self.data_dir = data_dir
        self.seed = seed
        self.evaluator = ModelEvaluator(artifacts_dir=artifacts_dir)
        os.makedirs(artifacts_dir, exist_ok=True)

    def load_or_generate_data(
        self, force_regenerate: bool = False
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Load cached train/val/test partitions or run the data preparation pipeline."""
        train_path = os.path.join(self.data_dir, "train.parquet")
        val_path = os.path.join(self.data_dir, "val.parquet")
        test_path = os.path.join(self.data_dir, "test.parquet")
        all_path = os.path.join(self.data_dir, "features_all.parquet")

        if (
            not force_regenerate
            and os.path.exists(train_path)
            and os.path.exists(val_path)
            and os.path.exists(test_path)
            and os.path.exists(all_path)
        ):
            logger.info("Loading existing processed datasets from data/processed/...")
            train_df = pd.read_parquet(train_path)
            val_df = pd.read_parquet(val_path)
            test_df = pd.read_parquet(test_path)
            all_df = pd.read_parquet(all_path)
            return train_df, val_df, test_df, all_df

        logger.info("Processed datasets not found or regeneration requested. Running data preparation pipeline...")
        pipeline = DataPreparationPipeline(seed=self.seed)
        train_df, val_df, test_df = pipeline.run(save_artifacts=True)
        all_df = pd.read_parquet(all_path)
        return train_df, val_df, test_df, all_df

    def train_single_model(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        feature_cols: List[str],
        calibrate: bool = True,
        seed: int = 42,
    ) -> Tuple[Any, Any, float]:
        """Train a single regularized LightGBM model with early stopping and isotonic calibration."""
        X_train = train_df[feature_cols].values
        y_train = train_df["target"].values
        X_val = val_df[feature_cols].values
        y_val = val_df["target"].values

        num_pos = max(1, int(np.sum(y_train == 1)))
        num_neg = max(1, int(np.sum(y_train == 0)))
        scale_pos_weight = float(num_neg / num_pos)

        # Strong regularization to combat patient-level cluster overfitting
        base_model = LGBMClassifier(
            n_estimators=300,
            learning_rate=0.030,
            max_depth=4,
            num_leaves=14,
            min_child_samples=50,
            subsample=0.80,
            colsample_bytree=0.75,
            reg_alpha=0.50,
            reg_lambda=2.00,
            scale_pos_weight=scale_pos_weight,
            random_state=seed,
            n_jobs=-1,
            verbosity=-1,
        )

        base_model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[early_stopping(stopping_rounds=20, verbose=False)],
        )

        calibrator = None
        if calibrate:
            calibrator = CalibratedClassifierCV(estimator=base_model, cv=None, method="isotonic")
            calibrator.fit(X_val, y_val)

        return base_model, calibrator, scale_pos_weight

    def run_full_pipeline(self, force_regenerate: bool = False) -> Dict[str, Any]:
        """Execute end-to-end training, multi-seed ablation, calibration, and artifact generation."""
        train_df, val_df, test_df, all_df = self.load_or_generate_data(force_regenerate=force_regenerate)
        prep_pipe = DataPreparationPipeline(seed=self.seed)

        logger.info("----------------------------------------------------------------------")
        logger.info(f"Executing 4-Tier Multimodal Ablation Study across {len(EVALUATION_SEEDS)} patient split seeds...")
        logger.info("----------------------------------------------------------------------")

        # Multi-seed ablation tracking
        seed_results: Dict[str, List[Dict[str, Any]]] = {
            "ehr_only": [],
            "ehr_plus_bp": [],
            "ehr_bp_sleep_hrv": [],
            "full": [],
        }

        tier_names = ["ehr_only", "ehr_plus_bp", "ehr_bp_sleep_hrv", "full"]

        for s_idx, split_seed in enumerate(EVALUATION_SEEDS):
            logger.info(f"Evaluating Split Seed {split_seed} ({s_idx + 1}/{len(EVALUATION_SEEDS)})...")
            s_train, s_val, s_test = prep_pipe._split_by_patient(all_df, seed=split_seed)
            s_lead_times = s_test["lead_time_hours"].values if "lead_time_hours" in s_test.columns else None

            for tier in tier_names:
                feats = FEATURE_SETS[tier]
                b_mod, c_mod, _ = self.train_single_model(s_train, s_val, feats, calibrate=True, seed=split_seed)
                X_test_s = s_test[feats].values
                y_test_s = s_test["target"].values
                y_prob_s = c_mod.predict_proba(X_test_s)[:, 1]

                tier_metrics = self.evaluator.evaluate_predictions(
                    y_true=y_test_s,
                    y_prob=y_prob_s,
                    test_patient_days=len(s_test),
                    num_patients=s_test["patient_id"].nunique(),
                    test_lead_times=s_lead_times,
                )
                seed_results[tier].append(tier_metrics)

        # Compute mean and standard deviation across seeds
        robust_summary: Dict[str, Dict[str, float]] = {}
        for tier in tier_names:
            roc_vals = [r["roc_auc"] for r in seed_results[tier]]
            pr_vals = [r["pr_auc"] for r in seed_results[tier]]
            brier_vals = [r["brier_score"] for r in seed_results[tier]]
            sens_vals = [r["sensitivity"] for r in seed_results[tier]]
            spec_vals = [r["specificity"] for r in seed_results[tier]]

            robust_summary[tier] = {
                "mean_roc_auc": round(float(np.mean(roc_vals)), 4),
                "std_roc_auc": round(float(np.std(roc_vals)), 4),
                "mean_pr_auc": round(float(np.mean(pr_vals)), 4),
                "std_pr_auc": round(float(np.std(pr_vals)), 4),
                "mean_brier_score": round(float(np.mean(brier_vals)), 4),
                "std_brier_score": round(float(np.std(brier_vals)), 4),
                "mean_sensitivity": round(float(np.mean(sens_vals)), 4),
                "mean_specificity": round(float(np.mean(spec_vals)), 4),
            }
            logger.info(
                f"[{tier.upper():16s}] ROC-AUC: {robust_summary[tier]['mean_roc_auc']:.4f} ± {robust_summary[tier]['std_roc_auc']:.4f} | "
                f"PR-AUC: {robust_summary[tier]['mean_pr_auc']:.4f} ± {robust_summary[tier]['std_pr_auc']:.4f}"
            )

        # Primary Reference Split (Seed 42) for production checkpoint
        logger.info("Fitting Primary Production Checkpoint (Seed 42)...")
        models_dict: Dict[str, Any] = {}
        seed42_ablation: Dict[str, Dict[str, Any]] = {}
        test_lead_times = test_df["lead_time_hours"].values if "lead_time_hours" in test_df.columns else None

        for tier in tier_names:
            feats = FEATURE_SETS[tier]
            b_mod, c_mod, _ = self.train_single_model(train_df, val_df, feats, calibrate=True, seed=self.seed)
            models_dict[tier] = (b_mod, c_mod)
            X_test = test_df[feats].values
            y_test = test_df["target"].values
            y_prob_cal = c_mod.predict_proba(X_test)[:, 1]

            tier_metrics = self.evaluator.evaluate_predictions(
                y_true=y_test,
                y_prob=y_prob_cal,
                test_patient_days=len(test_df),
                num_patients=test_df["patient_id"].nunique(),
                test_lead_times=test_lead_times,
            )
            seed42_ablation[tier] = tier_metrics

        full_base_model, full_calibrator = models_dict["full"]
        full_features = FEATURE_SETS["full"]
        X_test_full = test_df[full_features].values
        y_test_full = test_df["target"].values
        y_prob_uncal = full_base_model.predict_proba(X_test_full)[:, 1]
        y_prob_cal = full_calibrator.predict_proba(X_test_full)[:, 1]

        # Compute Bootstrap 95% Confidence Intervals
        logger.info("Computing Non-Parametric Bootstrap 95% Confidence Intervals (B=1000)...")
        bootstrap_cis = self.evaluator.compute_bootstrap_cis(
            y_true=y_test_full,
            y_prob=y_prob_cal,
            n_bootstraps=1000,
            seed=self.seed,
        )
        logger.info(f"Bootstrap ROC-AUC 95% CI: {bootstrap_cis['roc_auc_ci95']}")
        logger.info(f"Bootstrap PR-AUC  95% CI: {bootstrap_cis['pr_auc_ci95']}")

        # Diagnostic Curves
        logger.info("Generating publication-grade diagnostic curves and plots...")
        self.evaluator.plot_diagnostic_curves(
            y_true=y_test_full,
            y_prob_uncal=y_prob_uncal,
            y_prob_cal=y_prob_cal,
            ablation_results=seed42_ablation,
            robust_summary=robust_summary,
        )

        full_metrics = seed42_ablation["full"]
        full_metrics["bootstrap_confidence_intervals"] = bootstrap_cis

        # Markdown Report Generation
        logger.info("Generating clinical evaluation report markdown...")
        pos_rate = float(all_df["target"].mean())
        self.evaluator.generate_markdown_report(
            full_metrics=full_metrics,
            ablation_results=seed42_ablation,
            robust_summary=robust_summary,
            bootstrap_cis=bootstrap_cis,
            num_train=len(train_df),
            num_val=len(val_df),
            num_test=len(test_df),
            positive_rate=pos_rate,
            model_version=MODEL_VERSION,
        )

        # Persist Production Artifacts
        logger.info("Saving model artifacts to ml/artifacts/...")
        model_save_path = os.path.join(self.artifacts_dir, "lightgbm_model.joblib")
        calibrator_save_path = os.path.join(self.artifacts_dir, "calibrator.joblib")
        features_save_path = os.path.join(self.artifacts_dir, "feature_names.json")
        metrics_save_path = os.path.join(self.artifacts_dir, "metrics.json")
        version_save_path = os.path.join(self.artifacts_dir, "model_version.txt")

        joblib.dump(full_base_model, model_save_path)
        joblib.dump(full_calibrator, calibrator_save_path)

        with open(features_save_path, "w") as f:
            json.dump(full_features, f, indent=2)

        with open(version_save_path, "w") as f:
            f.write(MODEL_VERSION)

        final_metrics_payload = {
            "model_version": MODEL_VERSION,
            "architecture": "Calibrated LightGBM (Isotonic)",
            "primary_metrics": full_metrics,
            "ablation_comparison": seed42_ablation,
            "robust_ablation_summary": robust_summary,
            "bootstrap_confidence_intervals": bootstrap_cis,
            "feature_count": len(full_features),
            "train_samples": len(train_df),
            "val_samples": len(val_df),
            "test_samples": len(test_df),
            "positive_class_rate": round(pos_rate, 4),
        }

        with open(metrics_save_path, "w") as f:
            json.dump(final_metrics_payload, f, indent=2)

        logger.info("======================================================================")
        logger.info(f"NightWatch ML Pipeline Completed! Version: {MODEL_VERSION}")
        logger.info(f"Primary Test ROC-AUC: {full_metrics['roc_auc']:.4f} (95% CI: {bootstrap_cis['roc_auc_ci95']})")
        logger.info(f"Primary Test PR-AUC:  {full_metrics['pr_auc']:.4f} (95% CI: {bootstrap_cis['pr_auc_ci95']})")
        logger.info(f"Multi-Seed Mean Full ROC-AUC: {robust_summary['full']['mean_roc_auc']:.4f} ± {robust_summary['full']['std_roc_auc']:.4f}")
        logger.info(f"Multi-Seed Mean Full PR-AUC:  {robust_summary['full']['mean_pr_auc']:.4f} ± {robust_summary['full']['std_pr_auc']:.4f}")
        logger.info("======================================================================")
        return final_metrics_payload


def main() -> None:
    """CLI Entrypoint for python -m ml.train_lightgbm."""
    parser = argparse.ArgumentParser(
        description="NightWatch: Train, calibrate, and evaluate LightGBM Digital Twin model."
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Force regeneration of synthetic cohort and features.",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=str,
        default="ml/artifacts",
        help="Destination directory for model checkpoints and plots.",
    )
    args = parser.parse_args()

    trainer = LightGBMTrainer(artifacts_dir=args.artifacts_dir)
    trainer.run_full_pipeline(force_regenerate=args.regenerate)


if __name__ == "__main__":
    main()
