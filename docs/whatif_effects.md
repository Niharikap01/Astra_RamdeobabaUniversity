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

1. **Modest Effect Sizes**:
   The empirical risk deltas from lifestyle/wearable interventions average between **-8.38%** and **-0.18%**. Consistent with the feature ablation studies, baseline blood pressure history and hemodynamic volatility remain the dominant drivers of next-day hypertensive episodes. Wearable autonomic signals (sleep, HRV, steps) modulate short-term probability at the margin.

2. **Paradoxical "Wrong-Way" Risk Shifts**:
   - **Sleep +1.5 h**: 1.7% of patients moved the wrong way.
   - **Medication Taken**: 21.7% of patients moved the wrong way.
   - **Steps +4,000**: 6.7% of patients moved the wrong way.
   *Etiology*: In non-linear gradient-boosted decision trees, feature correlations can interact in high-dimensional split space (e.g., higher sleep duration shifting into a tree leaf where baseline SBP interacts with higher nocturnal sympathetic tone proxy). NightWatch candidly discloses these paradoxical shifts rather than artificially smoothing them.

3. **Clinical Trust and Guardrails**:
   - Every what-if response includes an explicit `effect_note` contextualizing modest changes.
   - Mandatory disclaimer: "Simulated scenario for clinical discussion. Modeled estimate, not a treatment recommendation."
