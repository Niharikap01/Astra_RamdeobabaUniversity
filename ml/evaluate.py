"""Clinical Evaluation and Model Diagnostic Module for NightWatch.

Computes discriminatory power (ROC-AUC, PR-AUC), clinical safety metrics
(Brier score, Expected Calibration Error, false alerts per patient-week, alert lead time),
multi-seed ablation benchmarks, bootstrap 95% confidence intervals,
and renders publication-grade diagnostic visualizations.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    auc,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    roc_auc_score,
    roc_curve,
)

logger = logging.getLogger("nightwatch.evaluate")


class ModelEvaluator:
    """Comprehensive clinical diagnostic evaluation and reporting suite."""

    def __init__(
        self,
        artifacts_dir: Optional[str] = None,
        docs_dir: Optional[str] = None,
    ) -> None:
        from backend.app.config import PROJECT_ROOT
        self.artifacts_dir = str(Path(artifacts_dir) if artifacts_dir and Path(artifacts_dir).is_absolute() else (PROJECT_ROOT / (artifacts_dir or "ml/artifacts")))
        self.docs_dir = str(Path(docs_dir) if docs_dir and Path(docs_dir).is_absolute() else (PROJECT_ROOT / (docs_dir or "docs")))
        os.makedirs(self.artifacts_dir, exist_ok=True)
        os.makedirs(self.docs_dir, exist_ok=True)

    def evaluate_predictions(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        threshold_high: float = 0.65,
        test_patient_days: Optional[int] = None,
        num_patients: Optional[int] = None,
        test_lead_times: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Compute standard ML metrics and clinical alert burden metrics."""
        roc_auc = float(roc_auc_score(y_true, y_prob))
        precision_arr, recall_arr, _ = precision_recall_curve(y_true, y_prob)
        pr_auc = float(auc(recall_arr, precision_arr))

        # Confusion matrix at High Risk threshold (>= 0.65)
        y_pred_high = (y_prob >= threshold_high).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred_high, labels=[0, 1]).ravel()

        sensitivity = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        precision = float(precision_score(y_true, y_pred_high, zero_division=0))
        f1 = float(f1_score(y_true, y_pred_high, zero_division=0))
        brier = float(brier_score_loss(y_true, y_prob))

        # Clinical monitoring metrics
        # False alerts per patient-week: (FP / total_patient_weeks)
        total_days = test_patient_days or len(y_true)
        patient_count = num_patients or max(1, total_days // 100)
        patient_weeks = max(0.1, total_days / 7.0 / patient_count)
        false_alerts_per_patient_week = float(fp / (patient_count * patient_weeks))

        # Expected Calibration Error (ECE)
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy="uniform")
        ece = float(np.mean(np.abs(prob_true - prob_pred)))

        # Dynamic Alert Lead Time: median lead time in hours for True Positive alerts
        tp_mask = (y_true == 1) & (y_pred_high == 1)
        if test_lead_times is not None and np.sum(tp_mask) > 0:
            median_lead_time = float(np.median(test_lead_times[tp_mask]))
        else:
            median_lead_time = 0.0

        return {
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "sensitivity": round(sensitivity, 4),
            "specificity": round(specificity, 4),
            "precision": round(precision, 4),
            "f1_score": round(f1, 4),
            "brier_score": round(brier, 4),
            "expected_calibration_error": round(ece, 4),
            "false_alerts_per_patient_week": round(false_alerts_per_patient_week, 3),
            "median_alert_lead_time_hours": round(median_lead_time, 1),
            "true_positives": int(tp),
            "false_positives": int(fp),
            "true_negatives": int(tn),
            "false_negatives": int(fn),
        }

    @staticmethod
    def compute_bootstrap_cis(
        y_true: Any,
        y_prob: Any,
        n_bootstraps: int = 1000,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """Compute non-parametric bootstrap 95% confidence intervals for ROC-AUC and PR-AUC."""
        y_t = np.asarray(y_true)
        y_p = np.asarray(y_prob)
        rng = np.random.default_rng(seed)
        roc_scores = []
        pr_scores = []
        n_samples = len(y_t)
        for _ in range(n_bootstraps):
            indices = rng.integers(0, n_samples, n_samples)
            if len(np.unique(y_t[indices])) < 2:
                continue
            y_b_true = y_t[indices]
            y_b_prob = y_p[indices]
            roc_scores.append(roc_auc_score(y_b_true, y_b_prob))
            pr, rc, _ = precision_recall_curve(y_b_true, y_b_prob)
            pr_scores.append(auc(rc, pr))

        return {
            "roc_auc_ci95": [round(float(np.percentile(roc_scores, 2.5)), 4), round(float(np.percentile(roc_scores, 97.5)), 4)],
            "pr_auc_ci95": [round(float(np.percentile(pr_scores, 2.5)), 4), round(float(np.percentile(pr_scores, 97.5)), 4)],
        }

    def plot_diagnostic_curves(
        self,
        y_true: np.ndarray,
        y_prob_uncal: np.ndarray,
        y_prob_cal: np.ndarray,
        ablation_results: Dict[str, Dict[str, Any]],
        robust_summary: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> None:
        """Render publication-quality ROC, PR, Calibration, and Ablation comparison figures."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Figure 1: ROC and PR Curves
        fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

        # ROC Curve
        fpr, tpr, _ = roc_curve(y_true, y_prob_cal)
        roc_val = roc_auc_score(y_true, y_prob_cal)
        axes[0].plot(fpr, tpr, color="#1e3a8a", lw=2.2, label=f"Calibrated LightGBM (AUC = {roc_val:.3f})")
        axes[0].plot([0, 1], [0, 1], color="#9ca3af", linestyle="--", lw=1.2, label="Chance")
        axes[0].set_title("Receiver Operating Characteristic (ROC)", fontsize=12, fontweight="bold", pad=10)
        axes[0].set_xlabel("False Positive Rate (1 - Specificity)", fontsize=10)
        axes[0].set_ylabel("True Positive Rate (Sensitivity)", fontsize=10)
        axes[0].legend(loc="lower right", frameon=True)
        axes[0].grid(True, linestyle=":", alpha=0.6)

        # Precision-Recall Curve
        precision_arr, recall_arr, _ = precision_recall_curve(y_true, y_prob_cal)
        pr_val = auc(recall_arr, precision_arr)
        prevalence = float(np.mean(y_true))
        axes[1].plot(recall_arr, precision_arr, color="#047857", lw=2.2, label=f"Precision-Recall (AUC = {pr_val:.3f})")
        axes[1].axhline(y=prevalence, color="#dc2626", linestyle="--", lw=1.2, label=f"Prevalence ({prevalence:.1%})")
        axes[1].set_title("Precision-Recall Curve (PRC)", fontsize=12, fontweight="bold", pad=10)
        axes[1].set_xlabel("Recall (Sensitivity)", fontsize=10)
        axes[1].set_ylabel("Positive Predictive Value (Precision)", fontsize=10)
        axes[1].legend(loc="upper right", frameon=True)
        axes[1].grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        roc_pr_path = os.path.join(self.artifacts_dir, "roc_prc_curves.png")
        plt.savefig(roc_pr_path, dpi=200)
        plt.close(fig)
        logger.info(f"Saved ROC/PR curves to {roc_pr_path}")

        # Figure 2: Calibration Reliability Curve
        fig, ax = plt.subplots(figsize=(7, 6))
        prob_true_uncal, prob_pred_uncal = calibration_curve(y_true, y_prob_uncal, n_bins=10, strategy="uniform")
        prob_true_cal, prob_pred_cal = calibration_curve(y_true, y_prob_cal, n_bins=10, strategy="uniform")

        ax.plot([0, 1], [0, 1], "k--", label="Perfect Calibration", lw=1.2)
        ax.plot(prob_pred_uncal, prob_true_uncal, "s-", color="#ef4444", label="Uncalibrated LightGBM", lw=1.8, markersize=5)
        ax.plot(prob_pred_cal, prob_true_cal, "o-", color="#2563eb", label="Isotonic Calibrated LightGBM", lw=2.2, markersize=6)
        ax.set_title("Reliability Diagram (Probability Calibration)", fontsize=12, fontweight="bold", pad=10)
        ax.set_xlabel("Predicted Probability", fontsize=10)
        ax.set_ylabel("Empirical Event Rate", fontsize=10)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.legend(loc="upper left", frameon=True)
        ax.grid(True, linestyle=":", alpha=0.6)

        plt.tight_layout()
        cal_path = os.path.join(self.artifacts_dir, "calibration_curve.png")
        plt.savefig(cal_path, dpi=200)
        plt.close(fig)
        logger.info(f"Saved Calibration curve to {cal_path}")

        # Figure 3: Ablation Study Comparison Bar Chart
        fig, ax = plt.subplots(figsize=(8.5, 5.0))
        models = ["ehr_only", "ehr_plus_bp", "ehr_bp_sleep_hrv", "full"]

        if robust_summary is not None:
            roc_scores = [robust_summary[m]["mean_roc_auc"] for m in models]
            roc_errors = [robust_summary[m]["std_roc_auc"] for m in models]
            pr_scores = [robust_summary[m]["mean_pr_auc"] for m in models]
            pr_errors = [robust_summary[m]["std_pr_auc"] for m in models]
        else:
            roc_scores = [ablation_results[m]["roc_auc"] for m in models]
            roc_errors = [0.0] * len(models)
            pr_scores = [ablation_results[m]["pr_auc"] for m in models]
            pr_errors = [0.0] * len(models)

        x = np.arange(len(models))
        width = 0.35
        labels_display = [
            "1. EHR Static",
            "2. EHR + BP Cuff",
            "3. + Sleep & HRV",
            "4. Full (+ Adherence)",
        ]

        ax.bar(x - width / 2, roc_scores, width, yerr=roc_errors, capsize=4, label="ROC-AUC (mean ± std)", color="#3b82f6")
        ax.bar(x + width / 2, pr_scores, width, yerr=pr_errors, capsize=4, label="PR-AUC (mean ± std)", color="#10b981")

        ax.set_xticks(x)
        ax.set_xticklabels(labels_display, fontsize=9.5, fontweight="semibold")
        ax.set_ylabel("Metric Value", fontsize=10)
        ax.set_ylim(0.0, 1.0)
        ax.set_title("Ablation Study: Incremental Modality Lift (5-Fold Cross-Seed)", fontsize=12, fontweight="bold", pad=10)
        ax.grid(axis="y", linestyle=":", alpha=0.6)
        ax.legend(loc="upper left")

        for i in range(len(models)):
            ax.annotate(f"{roc_scores[i]:.3f}", (x[i] - width / 2, roc_scores[i] + 0.03), ha="center", fontsize=8.5)
            ax.annotate(f"{pr_scores[i]:.3f}", (x[i] + width / 2, pr_scores[i] + 0.03), ha="center", fontsize=8.5)

        plt.tight_layout()
        ablation_path = os.path.join(self.artifacts_dir, "ablation_comparison.png")
        plt.savefig(ablation_path, dpi=200)
        plt.close(fig)
        logger.info(f"Saved Ablation figure to {ablation_path}")

    def generate_markdown_report(
        self,
        full_metrics: Dict[str, Any],
        ablation_results: Dict[str, Dict[str, Any]],
        robust_summary: Dict[str, Dict[str, float]],
        bootstrap_cis: Dict[str, Any],
        num_train: int,
        num_val: int,
        num_test: int,
        positive_rate: float,
        model_version: str = "1.1.0",
    ) -> str:
        """Produce the comprehensive clinical evaluation report markdown file."""
        report = f"""# NightWatch Model Evaluation Report

**Model Version:** {model_version}  
**Target:** 24-Hour Hypertensive Episode Prediction (Next-day SBP $\\ge 140$ mmHg or DBP $\\ge 90$ mmHg)  
**Positive Episode Rate:** {positive_rate:.1%}  
**Ground Truth:** Validated Home Blood Pressure Cuff Readings  
**Context Modalities:** Wearable Sleep Architecture, Autonomic HRV, Physical Activity, Smart Adherence  

---

## 1. Executive Summary

NightWatch achieves predictive discrimination for next-day hypertensive episodes by fusing static electronic health record (EHR) profiles with wearable sleep and autonomic dynamics. The full multimodal digital twin reaches a **ROC-AUC of {full_metrics['roc_auc']:.3f}** (95% CI: [{bootstrap_cis['roc_auc_ci95'][0]:.3f}, {bootstrap_cis['roc_auc_ci95'][1]:.3f}]) and a **PR-AUC of {full_metrics['pr_auc']:.3f}** (95% CI: [{bootstrap_cis['pr_auc_ci95'][0]:.3f}, {bootstrap_cis['pr_auc_ci95'][1]:.3f}]).

```
                      +-------------------+
                      |   EHR Baseline    | ROC-AUC: {robust_summary['ehr_only']['mean_roc_auc']:.3f} ± {robust_summary['ehr_only']['std_roc_auc']:.3f}
                      +---------+---------+
                                | + Home BP Cuff Readings
                                v
                      +-------------------+
                      |   EHR + BP Cuff   | ROC-AUC: {robust_summary['ehr_plus_bp']['mean_roc_auc']:.3f} ± {robust_summary['ehr_plus_bp']['std_roc_auc']:.3f}
                      +---------+---------+
                                | + Wearable Sleep Architecture & HRV
                                v
                      +-------------------+
                      | EHR+BP+Sleep+HRV  | ROC-AUC: {robust_summary['ehr_bp_sleep_hrv']['mean_roc_auc']:.3f} ± {robust_summary['ehr_bp_sleep_hrv']['std_roc_auc']:.3f}
                      +---------+---------+
                                | + Medication Adherence & Activity
                                v
                      +-------------------+
                      | Full Digital Twin | ROC-AUC: {robust_summary['full']['mean_roc_auc']:.3f} ± {robust_summary['full']['std_roc_auc']:.3f} | PR-AUC: {robust_summary['full']['mean_pr_auc']:.3f} ± {robust_summary['full']['std_pr_auc']:.3f}
                      +-------------------+
```

---

## 2. Test Cohort Performance Metrics

Evaluated on held-out patient subjects using patient-level `GroupShuffleSplit` (70% train / 15% validation / 15% test; {num_test} independent daily samples).

| Metric | Full Model Value | 95% Bootstrap CI | Clinical Relevance |
| :--- | :---: | :---: | :--- |
| **ROC-AUC** | **{full_metrics['roc_auc']:.4f}** | [{bootstrap_cis['roc_auc_ci95'][0]:.4f}, {bootstrap_cis['roc_auc_ci95'][1]:.4f}] | Area under receiver operating characteristic curve |
| **PR-AUC** | **{full_metrics['pr_auc']:.4f}** | [{bootstrap_cis['pr_auc_ci95'][0]:.4f}, {bootstrap_cis['pr_auc_ci95'][1]:.4f}] | Precision-recall area (accommodates clinical imbalance) |
| **Sensitivity (Recall)** | **{full_metrics['sensitivity']:.1%}** | — | True episode detection rate at High risk tier ($\\ge 0.65$) |
| **Specificity** | **{full_metrics['specificity']:.1%}** | — | Correct identification of normotensive intervals |
| **Positive Predictive Value (PPV)** | **{full_metrics['precision']:.1%}** | — | True positive rate when clinician alert fires |
| **F1 Score** | **{full_metrics['f1_score']:.4f}** | — | Harmonic mean of precision and recall |
| **Brier Score** | **{full_metrics['brier_score']:.4f}** | — | Mean squared error of calibrated probability |
| **Expected Calibration Error (ECE)** | **{full_metrics['expected_calibration_error']:.4f}** | — | Reliability index across probabilistic risk deciles |
| **False Alerts / Patient-Week** | **{full_metrics['false_alerts_per_patient_week']:.2f}** | — | Alert burden metric (target $< 1.0$) |
| **Median Alert Lead Time** | **{full_metrics['median_alert_lead_time_hours']} hours** | — | Warning window prior to next-day hypertensive excursion |

---

## 3. Four-Tier Modality Ablation Study (5 Patient-Wise Split Seeds)

Benchmarked across 5 independent patient-wise split seeds (70/15/15) to evaluate the incremental diagnostic contribution of wearable modalities beyond static EHR and home BP:

| Model Tier | Input Features | Mean ROC-AUC ± SD | Mean PR-AUC ± SD | Seed 42 ROC-AUC | Seed 42 PR-AUC |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **1. EHR Only** | Demographics, ICD-10 comorbidities, baseline labs | {robust_summary['ehr_only']['mean_roc_auc']:.4f} ± {robust_summary['ehr_only']['std_roc_auc']:.4f} | {robust_summary['ehr_only']['mean_pr_auc']:.4f} ± {robust_summary['ehr_only']['std_pr_auc']:.4f} | {ablation_results['ehr_only']['roc_auc']:.4f} | {ablation_results['ehr_only']['pr_auc']:.4f} |
| **2. EHR + BP Cuff** | Static EHR + longitudinal morning & evening BP trends | {robust_summary['ehr_plus_bp']['mean_roc_auc']:.4f} ± {robust_summary['ehr_plus_bp']['std_roc_auc']:.4f} | {robust_summary['ehr_plus_bp']['mean_pr_auc']:.4f} ± {robust_summary['ehr_plus_bp']['std_pr_auc']:.4f} | {ablation_results['ehr_plus_bp']['roc_auc']:.4f} | {ablation_results['ehr_plus_bp']['pr_auc']:.4f} |
| **3. + Sleep Architecture & HRV** | Static EHR + BP + sleep debt, efficiency, RMSSD HRV | {robust_summary['ehr_bp_sleep_hrv']['mean_roc_auc']:.4f} ± {robust_summary['ehr_bp_sleep_hrv']['std_roc_auc']:.4f} | {robust_summary['ehr_bp_sleep_hrv']['mean_pr_auc']:.4f} ± {robust_summary['ehr_bp_sleep_hrv']['std_pr_auc']:.4f} | {ablation_results['ehr_bp_sleep_hrv']['roc_auc']:.4f} | {ablation_results['ehr_bp_sleep_hrv']['pr_auc']:.4f} |
| **4. Full Multimodal Twin** | Full features (+ steps, sedentary hours, oral med adherence) | **{robust_summary['full']['mean_roc_auc']:.4f} ± {robust_summary['full']['std_roc_auc']:.4f}** | **{robust_summary['full']['mean_pr_auc']:.4f} ± {robust_summary['full']['std_pr_auc']:.4f}** | **{full_metrics['roc_auc']:.4f}** | **{full_metrics['pr_auc']:.4f}** |

---

## 4. Probability Calibration & Clinical Safety

NightWatch applies isotonic probability calibration fitted strictly on the independent validation split:
- **Calibrated Brier Score:** {full_metrics['brier_score']:.4f}
- **Expected Calibration Error (ECE):** {full_metrics['expected_calibration_error']:.4f}

### Risk Tier Configuration
- **Low Risk ($< 0.35$):** Routine monitoring; green status in clinician dashboard.
- **Moderate Risk ($0.35 - 0.65$):** Amber status; automated review of sleep debt and adherence trends recommended.
- **High Risk ($\\ge 0.65$):** Red alert with clinical action suggestion; clinician notification triggered with 24-hour deduplication cooldown.

---

## 5. Limitations

The sleep/HRV effects and autonomic surrogate signals reflect the simulator's physiological assumptions and literature-derived parameters, not prospectively validated real-world clinical trial effects. In synthetic cohorts, the coupling between prior-night sleep architecture, autonomic balance, and vascular tone is modeled via physiological differential equations and archetype response functions. Prospective clinical validation with certified ambulatory blood pressure monitoring (ABPM) and randomized control protocols is necessary before any clinical decision support deployment.

---

## 6. Regulatory & Clinical Disclaimer

NightWatch is a research prototype for clinical decision support. It does not diagnose hypertension, replace validated BP measurement, prescribe medication, or provide autonomous treatment recommendations. All data is synthetic or simulated.
"""
        report_path = os.path.join(self.docs_dir, "evaluation_report.md")
        with open(report_path, "w") as f:
            f.write(report)
        logger.info(f"Saved evaluation report markdown to {report_path}")
        return report
