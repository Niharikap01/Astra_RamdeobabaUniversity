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

| BP availability | Fold-mean paired ΔAUC ± SD (n=5) | Fold-mean wins / 5 | Pooled OOF paired ΔAUC | Pooled bootstrap mean ΔAUC | Pooled patient-cluster bootstrap 95% CI | Fold one-sample t-test p-value | Conclusion |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Daily** | +0.0035 ± 0.0093 | 3/5 | +0.0040 | +0.0042 | [-0.0093, +0.0166] | 0.4891 | not supported |
| **2–3 readings/week** | +0.0186 ± 0.0222 | 4/5 | +0.0360 | +0.0364 | [+0.0165, +0.0579] | 0.1689 | suggestive (CI excludes 0 but fold evidence weak) |
| **1 reading/week** | +0.0474 ± 0.0386 | 4/5 | +0.0620 | +0.0619 | [+0.0292, +0.0960] | 0.0702 | supported |

Gain is supported only when the pooled patient-cluster bootstrap 95% CI excludes zero, there are at least 4 wins in 5 folds, and the one-sample t-test on the five fold differences has p < 0.10. If the pooled CI excludes zero but either fold criterion fails, the result is “suggestive (CI excludes 0 but fold evidence weak)”; otherwise it is “not supported”.

## Limitations

Labels are derived from simulated next-day cuff readings, which in turn are generated from a hidden latent risk score that includes sleep debt, HRV drop, activity and stress terms, so model results measure recovery of the simulator's assumptions and are not evidence on real patients.
