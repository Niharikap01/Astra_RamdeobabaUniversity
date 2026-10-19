# Counterfactual What-If Intervention Effects Report

## Evaluation Cohort
- **Cohort Size**: 60 patients evaluated longitudinally from NightWatch database.
- **Model**: LightGBM + isotonic calibration (production pipeline v1.1.0).
- **Framing**: Counterfactual interventions are framed as sustained behavioral changes over the coming week, consistently updating all dependent physiological features (sleep debt, 7-day means, z-scores, poor-sleep streak, autonomic coupling, and adherence rates).

## Empirical Results

| Intervention | Mean Delta (Risk Shift) | Std Dev | Median Delta | Min Delta | Max Delta | Fraction Improved (Risk Drop) | Fraction Wrong-Way (Risk Rise) | Neutral (|Δ| < 0.01%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Sleep +1.5 h** | -0.0838 (-8.38%) | 0.0680 | -0.0777 | -0.3004 | +0.0597 | 78.3% | 1.7% | 20.0% |
| **Medication Taken** | -0.0018 (-0.18%) | 0.0123 | +0.0000 | -0.0808 | +0.0089 | 13.3% | 21.7% | 65.0% |
| **Steps +4,000** | -0.0170 (-1.70%) | 0.0295 | -0.0066 | -0.1197 | +0.0478 | 55.0% | 6.7% | 38.3% |

## Plain-Language Clinical Interpretation

1. **Ablation vs Counterfactual Sensitivity**:
   Sleep features add little predictive accuracy in the ablation (+0.002 ROC-AUC) yet the model is sensitive to the joint sleep counterfactual (mean -8.4 pts for +1.5 h); treat as modeled associations in synthetic data, not validated treatment effects.

2. **Observed Directional Shifts**:
   - **Sleep +1.5 h**: 78.3% improved (mean delta -8.38%), 1.7% wrong-way, 20.0% neutral.
   - **Medication Taken**: 13.3% improved (mean delta -0.18%), 21.7% wrong-way, 65.0% neutral.
   - **Steps +4,000**: 55.0% improved (mean delta -1.70%), 6.7% wrong-way, 38.3% neutral.

3. **Clinical Trust and Guardrails**:
   - Every what-if response includes an explicit `effect_note` contextualizing changes.
   - Mandatory disclaimer: "Simulated scenario for clinical discussion. Modeled estimate, not a treatment recommendation."
