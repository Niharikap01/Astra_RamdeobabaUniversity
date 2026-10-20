"""Robust Evaluation Suite for NightWatch.

Executes:
1. 5-Fold GroupKFold cross-validation across all patients with pooled out-of-fold predictions.
2. Patient-level (cluster) bootstrap 95% confidence intervals on pooled predictions.
3. Paired differences between consecutive ablation tiers (mean, SD, win counts).
4. Paired wearable-value comparisons at daily, 2-3, and 1 BP readings per week.
5. Validation-derived operating thresholds (Moderate and High) with test set operating metrics.
6. Programmatic generation of metrics.json, publication plots, and evaluation reports.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Tuple

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import (
    auc,
    brier_score_loss,
    confusion_matrix,
    precision_recall_curve,
    precision_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

from ml.data_preparation import DataPreparationPipeline
from ml.feature_engineering import FEATURE_SETS, FeatureEngineeringPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nightwatch.robustness")

MODEL_VERSION = "1.1.0"
EVALUATION_SEEDS = [42, 101, 202, 303, 404]
TIER_NAMES = ["ehr_only", "ehr_plus_bp", "ehr_bp_sleep_hrv", "full"]


def train_single_tier(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: List[str],
    seed: int = 42,
) -> Tuple[Any, Any]:
    """Train regularized LightGBM with early stopping and isotonic calibration."""
    X_train = train_df[feature_cols].values
    y_train = train_df["target"].values
    X_val = val_df[feature_cols].values
    y_val = val_df["target"].values

    num_pos = max(1, int(np.sum(y_train == 1)))
    num_neg = max(1, int(np.sum(y_train == 0)))
    scale_pos_weight = float(num_neg / num_pos)

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

    calibrator = CalibratedClassifierCV(estimator=base_model, cv=None, method="isotonic")
    calibrator.fit(X_val, y_val)
    return base_model, calibrator


def compute_cluster_bootstrap_ci(
    df: pd.DataFrame,
    y_prob: np.ndarray,
    n_bootstraps: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compute non-parametric patient-level (cluster) bootstrap 95% confidence intervals."""
    unique_pids = np.unique(df["patient_id"].values)
    n_patients = len(unique_pids)
    rng = np.random.default_rng(seed)

    df_subset = pd.DataFrame({
        "patient_id": df["patient_id"].values,
        "target": df["target"].values,
        "prob": y_prob,
    })
    patient_groups = {pid: grp[["target", "prob"]].to_numpy() for pid, grp in df_subset.groupby("patient_id")}

    roc_scores: List[float] = []
    pr_scores: List[float] = []

    for _ in range(n_bootstraps):
        sampled_pids = rng.choice(unique_pids, size=n_patients, replace=True)
        sampled_data = np.vstack([patient_groups[pid] for pid in sampled_pids])
        y_b_true = sampled_data[:, 0].astype(int)
        y_b_prob = sampled_data[:, 1]

        if len(np.unique(y_b_true)) < 2:
            continue

        roc_scores.append(float(roc_auc_score(y_b_true, y_b_prob)))
        pr, rc, _ = precision_recall_curve(y_b_true, y_b_prob)
        pr_scores.append(float(auc(rc, pr)))

    return {
        "roc_auc_ci95": [round(float(np.percentile(roc_scores, 2.5)), 4), round(float(np.percentile(roc_scores, 97.5)), 4)],
        "pr_auc_ci95": [round(float(np.percentile(pr_scores, 2.5)), 4), round(float(np.percentile(pr_scores, 97.5)), 4)],
        "bootstraps": n_bootstraps,
        "clusters": n_patients,
    }


def compute_cluster_bootstrap_auc_difference_ci(
    df: pd.DataFrame,
    prob_without_wearables: np.ndarray,
    prob_with_wearables: np.ndarray,
    n_bootstraps: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compute a paired ROC-AUC difference CI by resampling whole patients."""
    unique_pids = np.unique(df["patient_id"].values)
    groups = {
        pid: np.column_stack((grp["target"].values, prob_without_wearables[grp.index], prob_with_wearables[grp.index]))
        for pid, grp in df.reset_index(drop=True).groupby("patient_id")
    }
    rng = np.random.default_rng(seed)
    differences: List[float] = []

    for _ in range(n_bootstraps):
        sampled_pids = rng.choice(unique_pids, size=len(unique_pids), replace=True)
        sample = np.vstack([groups[pid] for pid in sampled_pids])
        y_true = sample[:, 0].astype(int)
        if len(np.unique(y_true)) < 2:
            continue
        without_auc = roc_auc_score(y_true, sample[:, 1])
        with_auc = roc_auc_score(y_true, sample[:, 2])
        differences.append(float(with_auc - without_auc))

    return {
        "ci95": [round(float(np.percentile(differences, 2.5)), 4), round(float(np.percentile(differences, 97.5)), 4)],
        "bootstraps": n_bootstraps,
        "clusters": len(unique_pids),
    }


def derive_operating_thresholds(
    val_df: pd.DataFrame,
    val_prob: np.ndarray,
    target_fa_high: float = 0.30,
    target_fa_mod: float = 0.80,
) -> Tuple[float, float, Dict[str, Any]]:
    """Derive Moderate and High thresholds strictly on the validation set."""
    y_val = val_df["target"].values
    total_val_weeks = len(val_df) / 7.0

    high_threshold = 0.50
    mod_threshold = 0.35

    high_candidates = []
    mod_candidates = []

    for tau in np.arange(0.20, 0.65, 0.01):
        tau_r = round(float(tau), 2)
        y_pred = (val_prob >= tau_r).astype(int)
        fp = int(np.sum((y_val == 0) & (y_pred == 1)))
        tp = int(np.sum((y_val == 1) & (y_pred == 1)))
        fn = int(np.sum((y_val == 1) & (y_pred == 0)))
        fa_pw = float(fp / total_val_weeks)
        sens = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0

        if fa_pw <= target_fa_high:
            high_candidates.append((tau_r, fa_pw, sens, prec))
        if fa_pw <= target_fa_mod:
            mod_candidates.append((tau_r, fa_pw, sens, prec))

    if high_candidates:
        high_threshold = high_candidates[0][0]
    if mod_candidates:
        mod_threshold = mod_candidates[0][0]

    return high_threshold, mod_threshold, {
        "val_high_tau": high_threshold,
        "val_high_fa_pw": round(high_candidates[0][1], 3) if high_candidates else 0.30,
        "val_mod_tau": mod_threshold,
        "val_mod_fa_pw": round(mod_candidates[0][1], 3) if mod_candidates else 0.80,
    }


def evaluate_operating_point(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float,
    total_weeks: float,
) -> Dict[str, Any]:
    """Compute operating performance at a fixed decision threshold."""
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    sens = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    fa_pw = float(fp / total_weeks) if total_weeks > 0 else 0.0

    return {
        "threshold": round(threshold, 2),
        "sensitivity": round(sens, 4),
        "specificity": round(spec, 4),
        "precision": round(prec, 4),
        "false_alerts_per_patient_week": round(fa_pw, 3),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }


def run_group_kfold_pipeline(
    dataset_df: pd.DataFrame,
    n_splits: int = 5,
    seed: int = 42,
) -> Dict[str, Any]:
    """Execute 5-fold GroupKFold cross-validation across all patients."""
    logger.info(f"Starting {n_splits}-Fold GroupKFold ablation over all {dataset_df['patient_id'].nunique()} patients...")
    gkf = GroupKFold(n_splits=n_splits)

    oof_predictions = {t: np.zeros(len(dataset_df)) for t in TIER_NAMES}
    fold_metrics = {t: {"roc": [], "pr": []} for t in TIER_NAMES}

    best_full_model = None
    best_full_calibrator = None

    for fold_idx, (train_full_idx, test_idx) in enumerate(gkf.split(dataset_df, groups=dataset_df["patient_id"])):
        train_full_df = dataset_df.iloc[train_full_idx]
        test_df = dataset_df.iloc[test_idx]

        # Split train_full into 80% inner-train and 20% inner-val for early stopping & isotonic calibration
        gss_inner = GroupShuffleSplit(n_splits=1, train_size=0.80, random_state=seed + fold_idx)
        inner_tr_idx, inner_val_idx = next(gss_inner.split(train_full_df, groups=train_full_df["patient_id"]))
        inner_train = train_full_df.iloc[inner_tr_idx]
        inner_val = train_full_df.iloc[inner_val_idx]

        y_test = test_df["target"].values

        for tier in TIER_NAMES:
            feats = FEATURE_SETS[tier]
            b_mod, c_mod = train_single_tier(inner_train, inner_val, feats, seed=seed + fold_idx)
            probs = c_mod.predict_proba(test_df[feats].values)[:, 1]
            oof_predictions[tier][test_idx] = probs

            roc = float(roc_auc_score(y_test, probs))
            pr_val, rc_val, _ = precision_recall_curve(y_test, probs)
            prauc = float(auc(rc_val, pr_val))

            fold_metrics[tier]["roc"].append(roc)
            fold_metrics[tier]["pr"].append(prauc)

            if tier == "full" and fold_idx == 0:
                best_full_model = b_mod
                best_full_calibrator = c_mod

        logger.info(f"Fold {fold_idx + 1}/{n_splits} complete. Full Tier Fold ROC: {fold_metrics['full']['roc'][-1]:.4f}")

    # Summary across folds
    kfold_summary = {}
    for tier in TIER_NAMES:
        kfold_summary[tier] = {
            "mean_roc_auc": round(float(np.mean(fold_metrics[tier]["roc"])), 4),
            "std_roc_auc": round(float(np.std(fold_metrics[tier]["roc"])), 4),
            "mean_pr_auc": round(float(np.mean(fold_metrics[tier]["pr"])), 4),
            "std_pr_auc": round(float(np.std(fold_metrics[tier]["pr"])), 4),
        }

    # Paired differences across folds
    comparisons = [
        ("tier2_vs_tier1", "Tier 2 (EHR+BP) vs Tier 1 (EHR)", "ehr_plus_bp", "ehr_only"),
        ("tier3_vs_tier2", "Tier 3 (+Sleep/HRV) vs Tier 2 (EHR+BP)", "ehr_bp_sleep_hrv", "ehr_plus_bp"),
        ("tier4_vs_tier3", "Tier 4 (Full Twin) vs Tier 3 (+Sleep/HRV)", "full", "ehr_bp_sleep_hrv"),
    ]
    paired_diffs = {}
    for key, label, t_curr, t_prev in comparisons:
        d_roc = [fold_metrics[t_curr]["roc"][i] - fold_metrics[t_prev]["roc"][i] for i in range(n_splits)]
        d_pr = [fold_metrics[t_curr]["pr"][i] - fold_metrics[t_prev]["pr"][i] for i in range(n_splits)]
        w_roc = sum(d > 0 for d in d_roc)
        w_pr = sum(d > 0 for d in d_pr)
        paired_diffs[key] = {
            "label": label,
            "roc_mean": round(float(np.mean(d_roc)), 4),
            "roc_sd": round(float(np.std(d_roc)), 4),
            "roc_wins": f"{w_roc}/{n_splits}",
            "pr_mean": round(float(np.mean(d_pr)), 4),
            "pr_sd": round(float(np.std(d_pr)), 4),
            "pr_wins": f"{w_pr}/{n_splits}",
            "consistent": "Yes" if (w_roc >= 4 and np.mean(d_roc) > 0.05) else ("Mixed" if w_roc >= 3 else "No"),
        }

    # Pooled Out-of-Fold performance & Cluster Bootstrap
    y_all = dataset_df["target"].values
    pooled_metrics = {}
    for tier in TIER_NAMES:
        probs = oof_predictions[tier]
        roc = float(roc_auc_score(y_all, probs))
        pr_val, rc_val, _ = precision_recall_curve(y_all, probs)
        prauc = float(auc(rc_val, pr_val))
        brier = float(brier_score_loss(y_all, probs))
        pooled_metrics[tier] = {
            "roc_auc": round(roc, 4),
            "pr_auc": round(prauc, 4),
            "brier_score": round(brier, 4),
        }

    logger.info("Computing Patient-Level Cluster Bootstrap (1,000 resamples) on pooled predictions...")
    full_oof_probs = oof_predictions["full"]
    bootstrap_cis = compute_cluster_bootstrap_ci(dataset_df, full_oof_probs, n_bootstraps=1000, seed=seed)

    return {
        "kfold_summary": kfold_summary,
        "paired_diffs": paired_diffs,
        "pooled_metrics": pooled_metrics,
        "bootstrap_cis": bootstrap_cis,
        "best_model": best_full_model,
        "best_calibrator": best_full_calibrator,
        "oof_predictions": oof_predictions,
    }


def run_sparse_bp_experiment(
    records_df: pd.DataFrame,
    patients_df: pd.DataFrame,
    base_df: pd.DataFrame,
    figures_dir: str,
    n_bootstraps: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compare BP plus wearable models at three BP availabilities in shared grouped CV."""
    patient_lookup = {p["patient_id"]: p for p in patients_df.to_dict(orient="records")}
    records_grouped = {
        pid: grp.sort_values("day_index").reset_index(drop=True)
        for pid, grp in records_df.groupby("patient_id")
    }
    base_keys = pd.MultiIndex.from_frame(base_df[["patient_id", "day_index"]])
    non_bp_features = FEATURE_SETS["ehr_bp_sleep_hrv"]
    bp_columns = [
        "morning_sbp", "morning_dbp", "evening_sbp", "evening_dbp",
    ]

    def build_availability_frame(setting: str, setting_seed: int) -> pd.DataFrame:
        if setting == "daily":
            return base_df.copy()

        rng = np.random.default_rng(setting_seed)
        feature_pipe = FeatureEngineeringPipeline(feature_subset="full")
        rows: List[Dict[str, Any]] = []
        readings_per_week = [2, 3] if setting == "2-3 readings/week" else [1]

        for pid, group_sorted in records_grouped.items():
            static_info = patient_lookup[pid]
            masked_history = group_sorted.copy()
            observed_sessions = set()

            for week_start in range(0, len(group_sorted), 7):
                week_days = list(range(week_start, min(len(group_sorted), week_start + 7)))
                sessions = [(day, period) for day in week_days for period in ("morning", "evening")]
                count = min(int(rng.choice(readings_per_week)), len(sessions))
                chosen_indices = rng.choice(len(sessions), size=count, replace=False)
                observed_sessions.update(sessions[int(i)] for i in chosen_indices)

            for day_pos, day_row in masked_history.iterrows():
                day_idx = int(day_row["day_index"])
                for period in ("morning", "evening"):
                    if (day_pos, period) not in observed_sessions:
                        for col in (f"{period}_sbp", f"{period}_dbp"):
                            masked_history.at[day_pos, col] = np.nan

            # The final day has no next-day cuff outcome and is excluded from model features.
            for d_idx in range(14, len(group_sorted) - 1):
                source_label = group_sorted.iloc[d_idx]["hypertensive_episode_next_day"]
                if pd.isna(source_label) or str(source_label).lower() == "unlabelled":
                    continue
                history = masked_history[masked_history["day_index"] <= d_idx]
                feature_row = feature_pipe.compute_features_from_history(
                    static_info=static_info,
                    history_df=history,
                    current_day_index=d_idx + 1,
                )
                feature_row["patient_id"] = pid
                feature_row["day_index"] = d_idx
                feature_row["target"] = int(source_label)
                rows.append(feature_row)

        masked_features = pd.DataFrame(rows).set_index(["patient_id", "day_index"])
        masked_features = masked_features.reindex(base_keys)
        if masked_features["target"].isna().any():
            raise ValueError(f"BP availability masking changed the evaluation row set for {setting}.")

        available = base_df.copy()
        for feature in non_bp_features:
            available[feature] = masked_features[feature].to_numpy()
        return available

    settings = [
        ("daily", "Daily"),
        ("2-3 readings/week", "2–3 readings/week"),
        ("1 reading/week", "1 reading/week"),
    ]
    results: Dict[str, Any] = {
        "comparison": "ehr_bp_sleep_hrv minus ehr_plus_bp",
        "cv_protocol": "5-Fold GroupKFold with patient groups; identical folds for all settings",
        "masking_protocol": "Unavailable cuff sessions are masked independently within each week; daily means all sessions.",
        "availability_settings": {},
    }
    fold_differences_by_setting: Dict[str, List[float]] = {}

    for setting_idx, (setting, label) in enumerate(settings):
        logger.info(f"Running wearable comparison with BP availability: {label}...")
        availability_df = build_availability_frame(setting, seed)
        gkf = GroupKFold(n_splits=5)
        fold_roc = {"ehr_plus_bp": [], "ehr_bp_sleep_hrv": []}
        oof_probs = {
            "ehr_plus_bp": np.zeros(len(availability_df), dtype=float),
            "ehr_bp_sleep_hrv": np.zeros(len(availability_df), dtype=float),
        }

        for fold_idx, (train_full_idx, test_idx) in enumerate(
            gkf.split(availability_df, groups=availability_df["patient_id"])
        ):
            train_full_df = availability_df.iloc[train_full_idx]
            test_df = availability_df.iloc[test_idx]
            inner_split = GroupShuffleSplit(n_splits=1, train_size=0.80, random_state=seed + fold_idx)
            train_idx, val_idx = next(
                inner_split.split(train_full_df, groups=train_full_df["patient_id"])
            )
            train_df = train_full_df.iloc[train_idx]
            val_df = train_full_df.iloc[val_idx]

            for tier in ("ehr_plus_bp", "ehr_bp_sleep_hrv"):
                features = FEATURE_SETS[tier]
                _, calibrator = train_single_tier(
                    train_df, val_df, features, seed=seed + fold_idx
                )
                probabilities = calibrator.predict_proba(test_df[features].values)[:, 1]
                oof_probs[tier][test_idx] = probabilities
                fold_roc[tier].append(
                    float(roc_auc_score(test_df["target"].values, probabilities))
                )

        fold_differences = [
            fold_roc["ehr_bp_sleep_hrv"][fold] - fold_roc["ehr_plus_bp"][fold]
            for fold in range(5)
        ]
        wins = int(sum(difference > 0 for difference in fold_differences))
        ci = compute_cluster_bootstrap_auc_difference_ci(
            base_df.reset_index(drop=True),
            oof_probs["ehr_plus_bp"],
            oof_probs["ehr_bp_sleep_hrv"],
            n_bootstraps=n_bootstraps,
            seed=seed + setting_idx,
        )
        pooled_difference = float(
            roc_auc_score(availability_df["target"], oof_probs["ehr_bp_sleep_hrv"])
            - roc_auc_score(availability_df["target"], oof_probs["ehr_plus_bp"])
        )
        ci_excludes_zero = ci["ci95"][0] > 0 or ci["ci95"][1] < 0
        supported = bool(ci_excludes_zero and wins >= 4)
        fold_differences_by_setting[setting] = fold_differences

        results["availability_settings"][setting] = {
            "label": label,
            "models": {
                tier: {
                    "fold_roc_auc": [round(score, 4) for score in fold_roc[tier]],
                    "mean_roc_auc": round(float(np.mean(fold_roc[tier])), 4),
                    "std_roc_auc": round(float(np.std(fold_roc[tier])), 4),
                }
                for tier in ("ehr_plus_bp", "ehr_bp_sleep_hrv")
            },
            "wearable_gain": {
                "comparison": results["comparison"],
                "fold_differences": [round(value, 4) for value in fold_differences],
                "roc_auc_difference_mean": round(float(np.mean(fold_differences)), 4),
                "roc_auc_difference_sd": round(float(np.std(fold_differences)), 4),
                "win_count": wins,
                "wins": f"{wins}/5",
                "pooled_oof_roc_auc_difference": round(pooled_difference, 4),
                "patient_cluster_bootstrap_ci95": ci["ci95"],
                "patient_cluster_bootstrap": {
                    "bootstraps": ci["bootstraps"],
                    "clusters": ci["clusters"],
                },
                "ci_excludes_zero": ci_excludes_zero,
                "supported": supported,
                "conclusion": "supported" if supported else "not supported",
            },
        }

    # Plot paired fold estimates and the patient-cluster bootstrap intervals.
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    y_positions = np.arange(len(settings))[::-1]
    all_bounds = [0.0]
    for y_pos, (setting, label) in zip(y_positions, settings):
        result = results["availability_settings"][setting]
        gain = result["wearable_gain"]
        mean = gain["roc_auc_difference_mean"]
        sd = gain["roc_auc_difference_sd"]
        ci_low, ci_high = gain["patient_cluster_bootstrap_ci95"]
        ax.errorbar(mean, y_pos + 0.12, xerr=sd, fmt="o", color="#2563eb", capsize=4,
                    label="5-fold mean ± SD" if y_pos == y_positions[0] else None)
        ax.errorbar(gain["pooled_oof_roc_auc_difference"], y_pos - 0.12,
                    xerr=[[max(0.0, gain["pooled_oof_roc_auc_difference"] - ci_low)],
                          [max(0.0, ci_high - gain["pooled_oof_roc_auc_difference"])]],
                    fmt="D", color="#d97706", capsize=4,
                    label="Pooled OOF difference, patient-cluster 95% CI" if y_pos == y_positions[0] else None)
        ax.text(1.01, y_pos, f"{gain['wins']} wins; {gain['conclusion']}",
                transform=ax.get_yaxis_transform(), va="center", fontsize=9)
        all_bounds.extend([mean - sd, mean + sd, ci_low, ci_high])

    ax.axvline(0, color="#6b7280", linestyle="--", linewidth=1.1)
    ax.set_yticks(y_positions)
    ax.set_yticklabels([label for _, label in settings])
    ax.set_xlabel("Δ ROC-AUC (EHR + BP + sleep/HRV minus EHR + BP)")
    ax.set_title("Wearable contribution by BP availability")
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    ax.legend(loc="lower right", fontsize=8)
    right = max(all_bounds) + 0.06
    left = min(all_bounds) - 0.06
    ax.set_xlim(left, right)
    fig.subplots_adjust(right=0.75)
    os.makedirs(figures_dir, exist_ok=True)
    fig.savefig(os.path.join(figures_dir, "sparse_bp_wearable_gain.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)
    return results

def render_publication_plots(
    dataset_df: pd.DataFrame,
    oof_predictions: Dict[str, np.ndarray],
    kfold_summary: Dict[str, Dict[str, float]],
    artifacts_dir: str = "ml/artifacts",
    figures_dir: Optional[str] = None,
) -> None:
    """Generate publication diagnostic figures from empirical pooled OOF predictions."""
    if figures_dir:
        os.makedirs(figures_dir, exist_ok=True)
    y_true = dataset_df["target"].values
    full_probs = oof_predictions["full"]

    # 1. ROC and PR Curves
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fpr, tpr, _ = roc_curve(y_true, full_probs)
    roc_val = roc_auc_score(y_true, full_probs)
    axes[0].plot(fpr, tpr, color="#1e3a8a", lw=2.2, label=f"Pooled OOF LightGBM (AUC = {roc_val:.3f})")
    axes[0].plot([0, 1], [0, 1], color="#9ca3af", linestyle="--", lw=1.2, label="Chance")
    axes[0].set_title("Receiver Operating Characteristic (ROC)", fontsize=12, fontweight="bold", pad=10)
    axes[0].set_xlabel("False Positive Rate (1 - Specificity)", fontsize=10)
    axes[0].set_ylabel("True Positive Rate (Sensitivity)", fontsize=10)
    axes[0].legend(loc="lower right")
    axes[0].grid(True, linestyle=":", alpha=0.6)

    precision_arr, recall_arr, _ = precision_recall_curve(y_true, full_probs)
    pr_val = auc(recall_arr, precision_arr)
    prevalence = float(np.mean(y_true))
    axes[1].plot(recall_arr, precision_arr, color="#047857", lw=2.2, label=f"Precision-Recall (AUC = {pr_val:.3f})")
    axes[1].axhline(y=prevalence, color="#dc2626", linestyle="--", lw=1.2, label=f"Prevalence ({prevalence:.1%})")
    axes[1].set_title("Precision-Recall Curve (PRC)", fontsize=12, fontweight="bold", pad=10)
    axes[1].set_xlabel("Recall (Sensitivity)", fontsize=10)
    axes[1].set_ylabel("Positive Predictive Value (Precision)", fontsize=10)
    axes[1].legend(loc="upper right")
    axes[1].grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(artifacts_dir, "roc_prc_curves.png"), dpi=200)
    if figures_dir:
        plt.savefig(os.path.join(figures_dir, "roc_prc_curves.png"), dpi=200)
    plt.close(fig)

    # 2. Calibration Reliability Curve
    fig, ax = plt.subplots(figsize=(7, 6))
    prob_true, prob_pred = calibration_curve(y_true, full_probs, n_bins=10, strategy="uniform")
    ax.plot([0, 1], [0, 1], "k--", label="Perfect Calibration", lw=1.2)
    ax.plot(prob_pred, prob_true, "o-", color="#2563eb", label="Pooled Isotonic LightGBM", lw=2.2, markersize=6)
    ax.set_title("Reliability Diagram (Probability Calibration)", fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel("Predicted Probability", fontsize=10)
    ax.set_ylabel("Empirical Event Rate", fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left")
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(artifacts_dir, "calibration_curve.png"), dpi=200)
    if figures_dir:
        plt.savefig(os.path.join(figures_dir, "calibration_curve.png"), dpi=200)
    plt.close(fig)

    # 3. Ablation Comparison Bar Chart
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    models = TIER_NAMES
    roc_scores = [kfold_summary[m]["mean_roc_auc"] for m in models]
    roc_errors = [kfold_summary[m]["std_roc_auc"] for m in models]
    pr_scores = [kfold_summary[m]["mean_pr_auc"] for m in models]
    pr_errors = [kfold_summary[m]["std_pr_auc"] for m in models]

    x = np.arange(len(models))
    width = 0.35
    labels_display = ["1. EHR Static", "2. EHR + BP Cuff", "3. + Sleep & HRV", "4. Full (+ Adherence)"]
    ax.bar(x - width / 2, roc_scores, width, yerr=roc_errors, capsize=4, label="ROC-AUC (mean ± SD)", color="#3b82f6")
    ax.bar(x + width / 2, pr_scores, width, yerr=pr_errors, capsize=4, label="PR-AUC (mean ± SD)", color="#10b981")
    ax.set_xticks(x)
    ax.set_xticklabels(labels_display, fontsize=9.5, fontweight="semibold")
    ax.set_ylabel("Metric Value", fontsize=10)
    ax.set_ylim(0.0, 1.0)
    ax.set_title("5-Fold GroupKFold Multimodal Ablation (Mean ± SD)", fontsize=12, fontweight="bold", pad=10)
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    ax.legend(loc="upper left")

    for i in range(len(models)):
        ax.annotate(f"{roc_scores[i]:.3f}", (x[i] - width / 2, roc_scores[i] + 0.03), ha="center", fontsize=8.5)
        ax.annotate(f"{pr_scores[i]:.3f}", (x[i] + width / 2, pr_scores[i] + 0.03), ha="center", fontsize=8.5)

    plt.tight_layout()
    plt.savefig(os.path.join(artifacts_dir, "ablation_comparison.png"), dpi=200)
    if figures_dir:
        plt.savefig(os.path.join(figures_dir, "ablation_comparison.png"), dpi=200)
    plt.close(fig)


def write_documentation_files(
    kfold_summary: Dict[str, Any],
    pooled_metrics: Dict[str, Any],
    paired_diffs: Dict[str, Any],
    sparse_results: Dict[str, Any],
    operating_points: Dict[str, Any],
    bootstrap_cis: Dict[str, Any],
    positive_rate: float,
    docs_dir: str = "docs",
) -> None:
    """Render the evaluation report and model card from computed metrics."""
    os.makedirs(docs_dir, exist_ok=True)
    eval_report_path = os.path.join(docs_dir, "evaluation_report.md")
    model_card_path = os.path.join(docs_dir, "model_card.md")
    settings = sparse_results["availability_settings"]

    sparse_table_rows = []
    for result in settings.values():
        gain = result["wearable_gain"]
        ci_low, ci_high = gain["patient_cluster_bootstrap_ci95"]
        conclusion = (
            "Wearable gain is supported"
            if gain["supported"]
            else "Wearable gain is not supported"
        )
        sparse_table_rows.append(
            f"| **{result['label']}** | {gain['roc_auc_difference_mean']:+.4f} ± "
            f"{gain['roc_auc_difference_sd']:.4f} | {gain['wins']} | "
            f"[{ci_low:+.4f}, {ci_high:+.4f}] | {conclusion} |"
        )
    sparse_table = "\n".join(sparse_table_rows)

    report_text = f"""# NightWatch Model Evaluation Report

**Model Version:** {MODEL_VERSION}  
**Target:** 24-hour hypertensive episode prediction (next-day SBP ≥ 140 mmHg or DBP ≥ 90 mmHg)  
**Positive Episode Rate:** {positive_rate:.1%}  
**Ground Truth:** Simulated next-day home blood pressure cuff readings  
**Cross-Validation Protocol:** 5-Fold GroupKFold over 200 patients (zero patient overlap across folds)  

---

## 1. Headline Performance

- **Pooled Out-of-Fold ROC-AUC:** {pooled_metrics['full']['roc_auc']:.4f} (patient-cluster 95% CI: [{bootstrap_cis['roc_auc_ci95'][0]:.4f}, {bootstrap_cis['roc_auc_ci95'][1]:.4f}])
- **5-Fold Cross-Validation Mean ROC-AUC:** {kfold_summary['full']['mean_roc_auc']:.4f} ± {kfold_summary['full']['std_roc_auc']:.4f}
- **Pooled Out-of-Fold PR-AUC:** {pooled_metrics['full']['pr_auc']:.4f} (patient-cluster 95% CI: [{bootstrap_cis['pr_auc_ci95'][0]:.4f}, {bootstrap_cis['pr_auc_ci95'][1]:.4f}])

The pooled out-of-fold AUC and its patient-cluster confidence interval are the headline discrimination result. The 5-fold mean and SD describe variation across folds separately.

## 2. Five-Fold GroupKFold Modality Ablation

| Model Tier | Mean ROC-AUC ± SD | Mean PR-AUC ± SD |
| :--- | :---: | :---: |
| **EHR Only** | {kfold_summary['ehr_only']['mean_roc_auc']:.4f} ± {kfold_summary['ehr_only']['std_roc_auc']:.4f} | {kfold_summary['ehr_only']['mean_pr_auc']:.4f} ± {kfold_summary['ehr_only']['std_pr_auc']:.4f} |
| **EHR + BP Cuff** | {kfold_summary['ehr_plus_bp']['mean_roc_auc']:.4f} ± {kfold_summary['ehr_plus_bp']['std_roc_auc']:.4f} | {kfold_summary['ehr_plus_bp']['mean_pr_auc']:.4f} ± {kfold_summary['ehr_plus_bp']['std_pr_auc']:.4f} |
| **EHR + BP + Sleep/HRV** | {kfold_summary['ehr_bp_sleep_hrv']['mean_roc_auc']:.4f} ± {kfold_summary['ehr_bp_sleep_hrv']['std_roc_auc']:.4f} | {kfold_summary['ehr_bp_sleep_hrv']['mean_pr_auc']:.4f} ± {kfold_summary['ehr_bp_sleep_hrv']['std_pr_auc']:.4f} |
| **Full Multimodal Twin** | {kfold_summary['full']['mean_roc_auc']:.4f} ± {kfold_summary['full']['std_roc_auc']:.4f} | {kfold_summary['full']['mean_pr_auc']:.4f} ± {kfold_summary['full']['std_pr_auc']:.4f} |

### Paired Fold Differences

| Comparison | Δ ROC-AUC (Mean ± SD) | Wins | Δ PR-AUC (Mean ± SD) | Wins |
| :--- | :---: | :---: | :---: | :---: |
| **EHR + BP vs EHR** | {paired_diffs['tier2_vs_tier1']['roc_mean']:+.4f} ± {paired_diffs['tier2_vs_tier1']['roc_sd']:.4f} | {paired_diffs['tier2_vs_tier1']['roc_wins']} | {paired_diffs['tier2_vs_tier1']['pr_mean']:+.4f} ± {paired_diffs['tier2_vs_tier1']['pr_sd']:.4f} | {paired_diffs['tier2_vs_tier1']['pr_wins']} |
| **EHR + BP + Sleep/HRV vs EHR + BP** | {paired_diffs['tier3_vs_tier2']['roc_mean']:+.4f} ± {paired_diffs['tier3_vs_tier2']['roc_sd']:.4f} | {paired_diffs['tier3_vs_tier2']['roc_wins']} | {paired_diffs['tier3_vs_tier2']['pr_mean']:+.4f} ± {paired_diffs['tier3_vs_tier2']['pr_sd']:.4f} | {paired_diffs['tier3_vs_tier2']['pr_wins']} |
| **Full Twin vs EHR + BP + Sleep/HRV** | {paired_diffs['tier4_vs_tier3']['roc_mean']:+.4f} ± {paired_diffs['tier4_vs_tier3']['roc_sd']:.4f} | {paired_diffs['tier4_vs_tier3']['roc_wins']} | {paired_diffs['tier4_vs_tier3']['pr_mean']:+.4f} ± {paired_diffs['tier4_vs_tier3']['pr_sd']:.4f} | {paired_diffs['tier4_vs_tier3']['pr_wins']} |

## 3. Wearable Value Under Sparse BP Availability

The paired comparison is EHR + BP + sleep/HRV versus EHR + BP. Each availability setting uses the same patient-grouped 5-fold CV; the reported difference is the wearable model's ROC-AUC minus the BP-only model's ROC-AUC. The CI resamples whole patients from pooled out-of-fold predictions.

| BP availability | Paired Δ ROC-AUC (Mean ± SD) | Wins out of 5 | Patient-cluster bootstrap 95% CI for Δ | Conclusion |
| :--- | :---: | :---: | :---: | :--- |
{sparse_table}

A wearable gain is supported for a setting only when its patient-cluster bootstrap CI excludes zero and the wearable model wins at least 4 of 5 folds. The figure is `figures/sparse_bp_wearable_gain.png`.

## 4. Operating Points From `ml/artifacts/thresholds.json`

| Risk tier | Threshold | Sensitivity | Specificity | Precision | False alerts / patient-week | TP | FP | TN | FN |
| :--- | :---: | :---: | :---: | :---: | :---: | ---: | ---: | ---: | ---: |
| **Moderate** | {operating_points['moderate']['threshold']:.2f} | {operating_points['moderate']['sensitivity']:.1%} | {operating_points['moderate']['specificity']:.1%} | {operating_points['moderate']['precision']:.1%} | {operating_points['moderate']['false_alerts_per_patient_week']:.3f} | {operating_points['moderate']['tp']} | {operating_points['moderate']['fp']} | {operating_points['moderate']['tn']} | {operating_points['moderate']['fn']} |
| **High** | {operating_points['high']['threshold']:.2f} | {operating_points['high']['sensitivity']:.1%} | {operating_points['high']['specificity']:.1%} | {operating_points['high']['precision']:.1%} | {operating_points['high']['false_alerts_per_patient_week']:.3f} | {operating_points['high']['tp']} | {operating_points['high']['fp']} | {operating_points['high']['tn']} | {operating_points['high']['fn']} |

## 5. Protocol Timing

Alerts run at 21:00 when daily wearable metrics sync. A next-day episode is detected at the morning cuff measurement (08:00; 11 hours later) or evening measurement (20:30; 23.5 hours later). These lead times are determined by the measurement schedule, not by the model.

## 6. Limitations

Labels are derived from simulated next-day cuff readings, which in turn are generated from a hidden latent risk score that includes sleep debt, HRV drop, activity and stress terms, so model results measure recovery of the simulator's assumptions and are not evidence on real patients. Prospective clinical validation is required before any real-world use.
"""
    with open(eval_report_path, "w", encoding="utf-8") as report_file:
        report_file.write(report_text)

    model_card_text = f"""# Model Card: NightWatch Multimodal Hypertensive Episode Predictor

## Model Details

- **Developer:** NightWatch Clinical Intelligence Team
- **Model Version:** {MODEL_VERSION}
- **Architecture:** Regularized LightGBM with isotonic probability calibration
- **Evaluation Protocol:** Patient-grouped 5-Fold GroupKFold with pooled out-of-fold predictions
- **Primary Inputs:** EHR, home BP cuff trends, sleep architecture, HRV, activity, and medication adherence

## Headline Performance

- **Pooled Out-of-Fold ROC-AUC:** {pooled_metrics['full']['roc_auc']:.4f} (patient-cluster 95% CI: [{bootstrap_cis['roc_auc_ci95'][0]:.4f}, {bootstrap_cis['roc_auc_ci95'][1]:.4f}])
- **5-Fold Cross-Validation Mean ROC-AUC:** {kfold_summary['full']['mean_roc_auc']:.4f} ± {kfold_summary['full']['std_roc_auc']:.4f}
- **Pooled Out-of-Fold PR-AUC:** {pooled_metrics['full']['pr_auc']:.4f} (patient-cluster 95% CI: [{bootstrap_cis['pr_auc_ci95'][0]:.4f}, {bootstrap_cis['pr_auc_ci95'][1]:.4f}])

The pooled out-of-fold AUC is the headline AUC; the fold mean and SD are reported separately as cross-validation variability.

## Clinical Operating Points From `ml/artifacts/thresholds.json`

| Risk tier | Threshold | Sensitivity | Specificity | Precision | False alerts / patient-week | TP | FP | TN | FN |
| :--- | :---: | :---: | :---: | :---: | :---: | ---: | ---: | ---: | ---: |
| **Moderate** | {operating_points['moderate']['threshold']:.2f} | {operating_points['moderate']['sensitivity']:.1%} | {operating_points['moderate']['specificity']:.1%} | {operating_points['moderate']['precision']:.1%} | {operating_points['moderate']['false_alerts_per_patient_week']:.3f} | {operating_points['moderate']['tp']} | {operating_points['moderate']['fp']} | {operating_points['moderate']['tn']} | {operating_points['moderate']['fn']} |
| **High** | {operating_points['high']['threshold']:.2f} | {operating_points['high']['sensitivity']:.1%} | {operating_points['high']['specificity']:.1%} | {operating_points['high']['precision']:.1%} | {operating_points['high']['false_alerts_per_patient_week']:.3f} | {operating_points['high']['tp']} | {operating_points['high']['fp']} | {operating_points['high']['tn']} | {operating_points['high']['fn']} |

## Wearable Value Under Sparse BP Availability

| BP availability | Paired Δ ROC-AUC (Mean ± SD) | Wins out of 5 | Patient-cluster bootstrap 95% CI for Δ | Conclusion |
| :--- | :---: | :---: | :---: | :--- |
{sparse_table}

Gain is supported only when the patient-cluster CI excludes zero and there are at least 4 wins in 5 folds.

## Limitations

Labels are derived from simulated next-day cuff readings, which in turn are generated from a hidden latent risk score that includes sleep debt, HRV drop, activity and stress terms, so model results measure recovery of the simulator's assumptions and are not evidence on real patients.
"""
    with open(model_card_path, "w", encoding="utf-8") as card_file:
        card_file.write(model_card_text)
    logger.info(f"Saved generated evaluation report to {eval_report_path}")
    logger.info(f"Saved generated model card to {model_card_path}")

def main() -> None:
    """Execute end-to-end robust evaluation pipeline and write all artifacts."""
    from backend.app.config import PROJECT_ROOT
    from pathlib import Path

    artifacts_dir = str(PROJECT_ROOT / "ml" / "artifacts")
    docs_dir = str(PROJECT_ROOT / "docs")
    figures_dir = str(PROJECT_ROOT / "docs" / "figures")
    data_dir = PROJECT_ROOT / "data"
    os.makedirs(artifacts_dir, exist_ok=True)
    os.makedirs(docs_dir, exist_ok=True)
    os.makedirs(figures_dir, exist_ok=True)

    # 1. Load data
    logger.info("Loading processed dataset and raw cohort...")
    dataset_df = pd.read_parquet(data_dir / "processed" / "features_all.parquet")
    records_df = pd.read_parquet(data_dir / "raw" / "records_daily.parquet")
    patients_df = pd.read_parquet(data_dir / "raw" / "patients.parquet")
    val_df = pd.read_parquet(data_dir / "processed" / "val.parquet")

    # 2. 5-Fold GroupKFold Ablation
    kfold_res = run_group_kfold_pipeline(dataset_df, n_splits=5, seed=42)

    # 3. Operating thresholds from ml/artifacts/thresholds.json (fallback: derive on validation)
    test_df = pd.read_parquet(data_dir / "processed" / "test.parquet")
    thresh_path = os.path.join(artifacts_dir, "thresholds.json")
    threshold_data = None
    if os.path.exists(thresh_path):
        logger.info(f"Loading operating thresholds from {thresh_path}...")
        with open(thresh_path, encoding="utf-8") as f:
            threshold_data = json.load(f)
            tau_high = float(threshold_data.get("high", 0.47))
            tau_mod = float(threshold_data.get("moderate", 0.34))
    else:
        val_feats = val_df[FEATURE_SETS["full"]].values
        val_probs = kfold_res["best_calibrator"].predict_proba(val_feats)[:, 1]
        tau_high, tau_mod, val_thresh_info = derive_operating_thresholds(val_df, val_probs)

    # Evaluate on test set
    test_feats = test_df[FEATURE_SETS["full"]].values
    test_probs = kfold_res["best_calibrator"].predict_proba(test_feats)[:, 1]
    total_test_weeks = len(test_df) / 7.0

    saved_test_points = (threshold_data or {}).get("test_evaluation", {})
    if all(tier in saved_test_points for tier in ("moderate", "high")):
        op_mod = {**saved_test_points["moderate"], "threshold": tau_mod}
        op_high = {**saved_test_points["high"], "threshold": tau_high}
    else:
        op_high = evaluate_operating_point(test_df["target"].values, test_probs, tau_high, total_test_weeks)
        op_mod = evaluate_operating_point(test_df["target"].values, test_probs, tau_mod, total_test_weeks)
    operating_points = {"high": op_high, "moderate": op_mod}

    # 4. Sparse-BP wearable comparison
    sparse_res = run_sparse_bp_experiment(
        records_df, patients_df, base_df=dataset_df, figures_dir=figures_dir, seed=42
    )

    # 5. Render plots (both ml/artifacts/ and docs/figures/)
    logger.info("Rendering publication diagnostic plots...")
    render_publication_plots(
        dataset_df,
        kfold_res["oof_predictions"],
        kfold_res["kfold_summary"],
        artifacts_dir,
        figures_dir,
    )

    # 6. Save Model Artifacts
    logger.info("Writing production model checkpoints and metadata...")
    joblib.dump(kfold_res["best_model"], os.path.join(artifacts_dir, "lightgbm_model.joblib"))
    joblib.dump(kfold_res["best_calibrator"], os.path.join(artifacts_dir, "calibrator.joblib"))
    with open(os.path.join(artifacts_dir, "model_version.txt"), "w") as f:
        f.write(MODEL_VERSION)
    with open(os.path.join(artifacts_dir, "feature_names.json"), "w") as f:
        json.dump(FEATURE_SETS["full"], f, indent=2)

    pos_rate = float(dataset_df["target"].mean())

    metrics_payload = {
        "model_version": MODEL_VERSION,
        "evaluation_protocol": "5-Fold GroupKFold (200 patients pooled)",
        "positive_class_rate": round(pos_rate, 4),
        "headline_metrics": {
            "pooled_out_of_fold_roc_auc": kfold_res["pooled_metrics"]["full"]["roc_auc"],
            "pooled_out_of_fold_roc_auc_patient_cluster_ci95": kfold_res["bootstrap_cis"]["roc_auc_ci95"],
            "five_fold_mean_roc_auc": kfold_res["kfold_summary"]["full"]["mean_roc_auc"],
            "five_fold_roc_auc_sd": kfold_res["kfold_summary"]["full"]["std_roc_auc"],
            "operating_points": {"moderate": op_mod, "high": op_high},
        },
        "operating_thresholds": {
            "high": op_high,
            "moderate": op_mod,
            "derivation": "validation set false alert budgets (High <= 0.30, Mod <= 0.80)",
        },
        "kfold_summary": kfold_res["kfold_summary"],
        "paired_differences": kfold_res["paired_diffs"],
        "pooled_out_of_fold": kfold_res["pooled_metrics"],
        "patient_cluster_bootstrap": kfold_res["bootstrap_cis"],
        "sparse_bp_experiment": sparse_res,
        "protocol_note": "Alert lead time is design-determined by the measurement protocol schedule (21:00 bedtime alert -> 08:00 morning or 20:30 evening cuff), not a model result.",
        "limitations": "Labels are derived from simulated next-day cuff readings, which in turn are generated from a hidden latent risk score that includes sleep debt, HRV drop, activity and stress terms, so model results measure recovery of the simulator's assumptions and are not evidence on real patients.",
    }

    def _clean_json(obj):
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return str(obj)

    with open(os.path.join(artifacts_dir, "metrics.json"), "w") as f:
        json.dump(metrics_payload, f, indent=2, default=_clean_json)

    # 7. Write Documentation
    logger.info("Writing clean docs/evaluation_report.md and docs/model_card.md...")
    write_documentation_files(
        kfold_summary=kfold_res["kfold_summary"],
        pooled_metrics=kfold_res["pooled_metrics"],
        paired_diffs=kfold_res["paired_diffs"],
        sparse_results=sparse_res,
        operating_points=operating_points,
        bootstrap_cis=kfold_res["bootstrap_cis"],
        positive_rate=pos_rate,
        docs_dir=docs_dir,
    )

    logger.info("Sparse-BP wearable comparison (Δ ROC-AUC, mean ± SD | wins | patient-cluster 95% CI):")
    for result in sparse_res["availability_settings"].values():
        gain = result["wearable_gain"]
        logger.info(
            f"{result['label']}: {gain['roc_auc_difference_mean']:+.4f} ± "
            f"{gain['roc_auc_difference_sd']:.4f} | {gain['wins']} | "
            f"[{gain['patient_cluster_bootstrap_ci95'][0]:+.4f}, "
            f"{gain['patient_cluster_bootstrap_ci95'][1]:+.4f}] | {gain['conclusion']}"
        )
    logger.info("======================================================================")
    logger.info("Robustness and Evaluation Integrity Pipeline Finished Successfully!")
    logger.info(f"High Threshold: {tau_high:.2f} | Mod Threshold: {tau_mod:.2f}")
    logger.info(f"5-fold mean ROC-AUC: {kfold_res['kfold_summary']['full']['mean_roc_auc']:.4f} ± {kfold_res['kfold_summary']['full']['std_roc_auc']:.4f}")
    logger.info(f"5-fold mean PR-AUC:  {kfold_res['kfold_summary']['full']['mean_pr_auc']:.4f} ± {kfold_res['kfold_summary']['full']['std_pr_auc']:.4f}")
    logger.info(f"Pooled OOF ROC-AUC:  {kfold_res['pooled_metrics']['full']['roc_auc']:.4f} (Patient Cluster 95% CI: {kfold_res['bootstrap_cis']['roc_auc_ci95']})")
    logger.info(f"Pooled OOF PR-AUC:   {kfold_res['pooled_metrics']['full']['pr_auc']:.4f} (Patient Cluster 95% CI: {kfold_res['bootstrap_cis']['pr_auc_ci95']})")
    logger.info("======================================================================")


if __name__ == "__main__":
    main()
