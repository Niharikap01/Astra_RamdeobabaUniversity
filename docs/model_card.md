# Model Card: NightWatch Multimodal Hypertensive Episode Predictor

## Model Details

- **Developer:** NightWatch Clinical Intelligence Team
- **Model Version:** 1.1.0
- **Architecture:** Regularized LightGBM with isotonic probability calibration
- **Evaluation Protocol:** Patient-grouped 5-Fold GroupKFold with pooled out-of-fold predictions
- **Primary Inputs:** EHR, home BP cuff trends, sleep architecture, HRV, activity, and medication adherence

## Headline Performance

- **Pooled Out-of-Fold ROC-AUC:** 0.7751 (patient-cluster 95% CI: [0.7338, 0.8155])
- **5-Fold Cross-Validation Mean ROC-AUC:** 0.8143 ± 0.0283
- **Pooled Out-of-Fold PR-AUC:** 0.5194 (patient-cluster 95% CI: [0.4443, 0.6039])

The pooled out-of-fold AUC is the headline AUC; the fold mean and SD are reported separately as cross-validation variability.

## Clinical Operating Points From `ml/artifacts/thresholds.json`

| Risk tier | Threshold | Sensitivity | Specificity | Precision | False alerts / patient-week | TP | FP | TN | FN |
| :--- | :---: | :---: | :---: | :---: | :---: | ---: | ---: | ---: | ---: |
| **Moderate** | 0.34 | 69.9% | 70.4% | 42.5% | 1.580 | 525 | 711 | 1688 | 226 |
| **High** | 0.47 | 36.8% | 91.7% | 58.0% | 0.444 | 276 | 200 | 2199 | 475 |

## Wearable Value Under Sparse BP Availability

| BP availability | Paired Δ ROC-AUC (Mean ± SD) | Wins out of 5 | Patient-cluster bootstrap 95% CI for Δ | Conclusion |
| :--- | :---: | :---: | :---: | :--- |
| **Daily** | +0.0035 ± 0.0093 | 3/5 | [-0.0093, +0.0166] | Wearable gain is not supported |
| **2–3 readings/week** | +0.0186 ± 0.0222 | 4/5 | [+0.0165, +0.0579] | Wearable gain is supported |
| **1 reading/week** | +0.0474 ± 0.0386 | 4/5 | [+0.0292, +0.0960] | Wearable gain is supported |

Gain is supported only when the patient-cluster CI excludes zero and there are at least 4 wins in 5 folds.

## Limitations

Labels are derived from simulated next-day cuff readings, which in turn are generated from a hidden latent risk score that includes sleep debt, HRV drop, activity and stress terms, so model results measure recovery of the simulator's assumptions and are not evidence on real patients.
