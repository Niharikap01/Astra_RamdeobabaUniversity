# Model Card: NightWatch Multimodal Hypertensive Episode Predictor

## Model Details
- **Developer:** NightWatch Clinical Intelligence Team
- **Model Date:** October 2026
- **Model Version:** 1.1.0
- **Model Architecture:** Regularized LightGBM Gradient Boosted Decision Trees with Post-Hoc Isotonic Probability Calibration (`CalibratedClassifierCV`)
- **License:** Research Prototype / Decision Support
- **Primary Inputs:** Multimodal longitudinal telemetry:
  1. Static EHR demographics, comorbidities, and baseline medications ($d=24$)
  2. Ground-truth home BP cuff rolling metrics and trajectory slopes ($d=11$)
  3. Continuous wearable sleep architecture and autonomic tone (RMSSD HRV, resting HR) ($d=18$)
  4. Pedometer physical activity and smart pillbox adherence records ($d=8$)
  5. 30-day personal baseline deviation contrasts ($d=4$)
- **Total Feature Dimension:** 65 continuous and normalized numeric features

---

## Intended Use & Clinical Deployment
- **Intended Purpose:** 24-hour lookahead decision support for remote patient monitoring (RPM) clinician dashboards. Identifies ambulatory patients at impending risk of acute hypertensive excursions (next-day SBP $\ge 140$ mmHg or DBP $\ge 90$ mmHg).
- **Clinical Decision Window:** 11 to 24 hours of actionable clinician lead time prior to daytime hemodynamic surges.
- **Out of Scope Uses:**
  - Autonomous titration or prescription of antihypertensive drugs without clinician oversight.
  - Diagnosis of primary or secondary hypertension.
  - Replacement for certified ambulatory blood pressure monitoring (ABPM) or in-clinic sphygmomanometry.

---

## Performance Summary & Robust Evaluation
Benchmarked across 5 independent patient-wise `GroupShuffleSplit` seeds (70% train, 15% validation, 15% test; zero subject overlap between splits):

| Model Modality Tier | Mean ROC-AUC ± SD | Mean PR-AUC ± SD | Incremental Lift vs EHR Baseline |
| :--- | :---: | :---: | :---: |
| **Tier 1: EHR Static Only** | Evaluated via 5-fold cross-seed | Evaluated via 5-fold cross-seed | Baseline |
| **Tier 2: EHR + Home BP Cuff** | Evaluated via 5-fold cross-seed | Evaluated via 5-fold cross-seed | + Home cuff hemodynamics |
| **Tier 3: + Wearable Sleep & HRV** | Evaluated via 5-fold cross-seed | Evaluated via 5-fold cross-seed | + Autonomic & sleep debt early warnings |
| **Tier 4: Full Digital Twin (+ Adherence)** | Evaluated via 5-fold cross-seed | Evaluated via 5-fold cross-seed | Multimodal synthesis |

- **Probability Calibration:** Isotonic regression fitted strictly on the independent validation split, reducing Expected Calibration Error (ECE) and Brier score.
- **Alert Fatigue Control:** High-risk alert threshold ($\ge 0.65$) tuned to maintain false alerts per patient-week below 1.0, with an automated 24-hour alert deduplication cooldown.

---

## Limitations

Results come from synthetic data with assumptions built into the simulator, and the sleep/HRV effect is not validated on real patients. The coupling between prior-night sleep architecture, autonomic balance, and vascular tone is modeled via algorithmic differential equations and literature priors rather than prospectively verified human biology. Prospective clinical validation with randomized clinical trials and certified ambulatory blood pressure monitoring (ABPM) is strictly required before any real-world deployment.
