# NightWatch Model Evaluation Report

**Model Version:** 1.1.0  
**Target:** 24-Hour Hypertensive Episode Prediction (Next-day SBP $\ge 140$ mmHg or DBP $\ge 90$ mmHg)  
**Positive Episode Rate:** 27.6%  
**Ground Truth:** Validated Home Blood Pressure Cuff Readings  
**Cross-Validation Protocol:** 5-Fold GroupKFold over 200 patients (zero patient overlap across folds; 21,000 daily records)  

---

## 1. Executive Summary & Out-of-Fold Performance

NightWatch evaluates multimodal clinical telemetry for next-day hypertensive episode warning. On the complete 200-patient cohort evaluated via 5-Fold GroupKFold cross-validation, the full multimodal digital twin reaches:
- **5-Fold Cross-Validation Mean ROC-AUC:** 0.8143 ± 0.0283
- **Pooled Out-of-Fold ROC-AUC:** 0.7751 (Patient Cluster 95% CI: [0.7338, 0.8155])
- **Pooled Out-of-Fold PR-AUC:** 0.5194 (Patient Cluster 95% CI: [0.4443, 0.6039])

---

## 2. Five-Fold GroupKFold Modality Ablation

### 2.1. Absolute Performance Across 5 Folds
| Model Tier | Input Features | Mean ROC-AUC ± SD | Mean PR-AUC ± SD |
| :--- | :--- | :---: | :---: |
| **1. EHR Only** | Demographics, ICD-10 comorbidities, baseline labs | 0.6453 ± 0.0379 | 0.4171 ± 0.0531 |
| **2. EHR + BP Cuff** | Static EHR + longitudinal morning & evening BP trends | 0.8124 ± 0.0210 | 0.5757 ± 0.0236 |
| **3. + Sleep Architecture & HRV** | Static EHR + BP + sleep debt, efficiency, RMSSD HRV | 0.8159 ± 0.0253 | 0.5937 ± 0.0514 |
| **4. Full Multimodal Twin** | Full features (+ steps, sedentary hours, oral med adherence) | **0.8143 ± 0.0283** | **0.6045 ± 0.0455** |

### 2.2. Paired Consecutive Differences (Within Same Patient Folds)
| Comparison | $\Delta$ ROC-AUC (Mean ± SD) | ROC Wins | $\Delta$ PR-AUC (Mean ± SD) | PR Wins | Empirical Conclusion |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Tier 2 (EHR+BP) vs Tier 1 (EHR)** | **+0.1671 ± 0.0405** | **5/5** | **+0.1586 ± 0.0725** | **5/5** | **Consistent gain**: BP history provides large, statistically decisive lift |
| **Tier 3 (+Sleep/HRV) vs Tier 2 (EHR+BP)** | +0.0035 ± 0.0093 | 3/5 | +0.0181 ± 0.0292 | 3/5 | **Inconsistent gain**: marginal mean lift with high fold-to-fold variance |
| **Tier 4 (Full Twin) vs Tier 3 (+Sleep/HRV)** | -0.0016 ± 0.0039 | 2/5 | +0.0108 ± 0.0302 | 2/5 | **Inconsistent gain**: adherence/activity features yield mixed fold wins |

*Core Finding:* Blood pressure history is the only consistent gain across all patient folds. Wearable sleep, autonomic HRV, and medication adherence metrics show marginal and inconsistent incremental lift when daily twice-cuff readings are already captured.

---

## 3. Sparse-BP Sensitivity Experiment (2–3 Readings / Week)

When home blood pressure cuff readings are sparse (2–3 measurements per week, forward-filled on non-measured days):

| Model Tier | Daily BP Mean ROC-AUC | Sparse BP Mean ROC-AUC ± SD | Sparse BP Mean PR-AUC ± SD | $\Delta$ vs Prev Tier (ROC) | $\Delta$ vs Prev Tier (PR) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. EHR Only** | 0.6453 | 0.6297 ± 0.0850 | 0.4214 ± 0.0844 | Baseline | Baseline |
| **2. EHR + BP Cuff** | 0.8124 | 0.7493 ± 0.0286 | 0.4630 ± 0.0721 | +0.1196 ± 0.0590 (5/5) | +0.0416 ± 0.1487 (4/5) |
| **3. + Sleep & HRV** | 0.8159 | 0.7810 ± 0.0439 | 0.5247 ± 0.0589 | +0.0317 ± 0.0235 (4/5) | +0.0617 ± 0.1227 (3/5) |
| **4. Full Twin** | 0.8143 | 0.7844 ± 0.0406 | 0.5026 ± 0.0273 | +0.0035 ± 0.0063 (2/5) | -0.0220 ± 0.0676 (2/5) |

*Observation on Sparse-BP:* The incremental gain from sleep/HRV under sparse BP is **suggestive only** (4/5 seeds, with standard deviation 0.0235 roughly equal to the mean difference +0.0317). While continuous telemetry helps bridge unmeasured cuff intervals, the effect is modest and should not be overstated.

---

## 4. Operating Points & Validation-Derived Clinical Thresholds

Thresholds are derived strictly on the validation sets to respect clinical alert fatigue budgets:
- **Moderate Risk Threshold ($\\tau = 0.34$):** Target $\\le 0.80$ false alerts / patient-week on validation.
- **High Risk Threshold ($\\tau = 0.47$):** Lowest threshold achieving $\\le 0.30$ false alerts / patient-week on validation.

### Out-of-Fold Test Performance at Derived Operating Points
| Risk Tier | Decision Threshold | Sensitivity (Recall) | Specificity | Precision (PPV) | False Alerts / Patient-Week | Clinical Action Profile |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Moderate Risk** | **$\\tau \\ge 0.34$** | 98.5% | 33.8% | 31.8% | 3.529 | Lifestyle review, sleep hygiene check, medication adherence verification |
| **High Risk** | **$\\tau \\ge 0.47$** | 86.3% | 57.0% | 38.6% | 2.291 | Direct clinician notification, morning BP confirmation, medication review |

---

## 5. Protocol Timing & Action Window Note

Alerts run at 21:00 (bedtime assessment) when daily wearable metrics sync. If an episode occurs the next day, it is detected either at the morning cuff measurement (08:00; 11.0 hours later) or evening measurement (20:30; 23.5 hours later). These lead times are **design-determined by the measurement protocol schedule**, not an intrinsic property or discovery of the predictive model.

---

## 6. Limitations

Results come from synthetic data with assumptions built into the simulator, and the sleep/HRV effect is not validated on real patients. The coupling between sleep debt, vagal tone (HRV), and next-day vascular pressure reflects algorithmic formulations and literature priors rather than prospectively verified human biology. Prospective clinical validation with randomized clinical trials and certified ambulatory blood pressure monitoring (ABPM) is strictly required before any real-world deployment.
