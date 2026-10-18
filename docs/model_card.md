# Model Card: NightWatch Multimodal Hypertensive Episode Predictor

## Model Details
- **Developer:** NightWatch Clinical Intelligence Team
- **Model Version:** 1.1.0
- **Architecture:** Regularized LightGBM with Isotonic Probability Calibration (`CalibratedClassifierCV`)
- **Evaluation Protocol:** 5-Fold GroupKFold over 200 patients (pooled out-of-fold predictions)
- **Primary Inputs:** Multimodal physiological features ($d=65$):
  1. Static EHR demographics, ICD-10 comorbidities, baseline labs ($d=24$)
  2. Ground-truth home BP cuff longitudinal rolling statistics ($d=11$)
  3. Wearable sleep architecture and autonomic tone (RMSSD HRV, resting HR) ($d=18$)
  4. Physical activity and smart pillbox adherence tracking ($d=8$)
  5. 30-day personal baseline deviation contrasts ($d=4$)

---

## Clinical Operating Thresholds (Validation-Derived)
- **Moderate Risk Threshold:** $\tau = 0.34$ (Sensitivity: 98.5%, Precision: 31.8%, FA: 3.53/pt-wk)
- **High Risk Threshold:** $\tau = 0.47$ (Sensitivity: 86.3%, Precision: 38.6%, FA: 2.29/pt-wk)

---

## Performance Summary (5-Fold GroupKFold)
- **Pooled Out-of-Fold ROC-AUC:** 0.8143 ± 0.0283 (Patient Cluster 95% CI: [0.7338, 0.8155])
- **Pooled Out-of-Fold PR-AUC:** 0.6045 ± 0.0455 (Patient Cluster 95% CI: [0.4443, 0.6039])
- **Ablation Findings:** Blood pressure history is the only consistent gain across all patient folds (+0.1671 ROC, 5/5 wins). Sleep/HRV and adherence gains are inconsistent under daily cuff monitoring. Under sparse cuff monitoring (2-3 readings/week), sleep/HRV gains are suggestive only (4/5 wins).

---

## Limitations

Results come from synthetic data with assumptions built into the simulator, and the sleep/HRV effect is not validated on real patients. The coupling between prior-night sleep architecture, autonomic balance, and vascular tone is modeled via algorithmic differential equations and literature priors rather than prospectively verified human biology. Prospective clinical validation with randomized clinical trials and certified ambulatory blood pressure monitoring (ABPM) is strictly required before any real-world deployment.
