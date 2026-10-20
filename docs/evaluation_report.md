# NightWatch Model Evaluation Report

**Model Version:** 1.1.0  
**Target:** 24-hour hypertensive episode prediction (next-day SBP ≥ 140 mmHg or DBP ≥ 90 mmHg)  
**Positive Episode Rate:** 27.6%  
**Ground Truth:** Simulated next-day home blood pressure cuff readings  
**Cross-Validation Protocol:** 5-Fold GroupKFold over 200 patients (zero patient overlap across folds)  

---

## 1. Headline Performance

- **Pooled Out-of-Fold ROC-AUC:** 0.7751 (patient-cluster 95% CI: [0.7338, 0.8155])
- **5-Fold Cross-Validation Mean ROC-AUC:** 0.8143 ± 0.0283
- **Pooled Out-of-Fold PR-AUC:** 0.5194 (patient-cluster 95% CI: [0.4443, 0.6039])

The pooled out-of-fold AUC and its patient-cluster confidence interval are the headline discrimination result. The 5-fold mean and SD describe variation across folds separately.

## 2. Five-Fold GroupKFold Modality Ablation

| Model Tier | Mean ROC-AUC ± SD | Mean PR-AUC ± SD |
| :--- | :---: | :---: |
| **EHR Only** | 0.6453 ± 0.0379 | 0.4171 ± 0.0531 |
| **EHR + BP Cuff** | 0.8124 ± 0.0210 | 0.5757 ± 0.0236 |
| **EHR + BP + Sleep/HRV** | 0.8159 ± 0.0253 | 0.5937 ± 0.0514 |
| **Full Multimodal Twin** | 0.8143 ± 0.0283 | 0.6045 ± 0.0455 |

### Paired Fold Differences

| Comparison | Δ ROC-AUC (Mean ± SD) | Wins | Δ PR-AUC (Mean ± SD) | Wins |
| :--- | :---: | :---: | :---: | :---: |
| **EHR + BP vs EHR** | +0.1671 ± 0.0405 | 5/5 | +0.1586 ± 0.0725 | 5/5 |
| **EHR + BP + Sleep/HRV vs EHR + BP** | +0.0035 ± 0.0093 | 3/5 | +0.0181 ± 0.0292 | 3/5 |
| **Full Twin vs EHR + BP + Sleep/HRV** | -0.0016 ± 0.0039 | 2/5 | +0.0108 ± 0.0302 | 2/5 |

## 3. Wearable Value Under Sparse BP Availability

The paired comparison is EHR + BP + sleep/HRV versus EHR + BP. Each availability setting uses the same patient-grouped 5-fold CV; the reported difference is the wearable model's ROC-AUC minus the BP-only model's ROC-AUC. The CI resamples whole patients from pooled out-of-fold predictions.

| BP availability | Paired Δ ROC-AUC (Mean ± SD) | Wins out of 5 | Patient-cluster bootstrap 95% CI for Δ | Conclusion |
| :--- | :---: | :---: | :---: | :--- |
| **Daily** | +0.0035 ± 0.0093 | 3/5 | [-0.0093, +0.0166] | Wearable gain is not supported |
| **2–3 readings/week** | +0.0186 ± 0.0222 | 4/5 | [+0.0165, +0.0579] | Wearable gain is supported |
| **1 reading/week** | +0.0474 ± 0.0386 | 4/5 | [+0.0292, +0.0960] | Wearable gain is supported |

A wearable gain is supported for a setting only when its patient-cluster bootstrap CI excludes zero and the wearable model wins at least 4 of 5 folds. The figure is `figures/sparse_bp_wearable_gain.png`.

## 4. Operating Points From `ml/artifacts/thresholds.json`

| Risk tier | Threshold | Sensitivity | Specificity | Precision | False alerts / patient-week | TP | FP | TN | FN |
| :--- | :---: | :---: | :---: | :---: | :---: | ---: | ---: | ---: | ---: |
| **Moderate** | 0.34 | 69.9% | 70.4% | 42.5% | 1.580 | 525 | 711 | 1688 | 226 |
| **High** | 0.47 | 36.8% | 91.7% | 58.0% | 0.444 | 276 | 200 | 2199 | 475 |

## 5. Protocol Timing

Alerts run at 21:00 when daily wearable metrics sync. A next-day episode is detected at the morning cuff measurement (08:00; 11 hours later) or evening measurement (20:30; 23.5 hours later). These lead times are determined by the measurement schedule, not by the model.

## 6. Limitations

Labels are derived from simulated next-day cuff readings, which in turn are generated from a hidden latent risk score that includes sleep debt, HRV drop, activity and stress terms, so model results measure recovery of the simulator's assumptions and are not evidence on real patients. Prospective clinical validation is required before any real-world use.
