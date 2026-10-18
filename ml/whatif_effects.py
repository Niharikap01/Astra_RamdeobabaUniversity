"""Measure average counterfactual effects over 60 patients and write docs/whatif_effects.md.

Evaluates three counterfactual interventions:
1. Sleep duration +1.5 h
2. Medication taken (enforced 100% adherence over the coming week)
3. Physical activity +4,000 steps/day

Reports mean delta, standard deviation, and fraction of patients whose modeled
risk moves the "wrong" way (paradoxical risk increase under a beneficial intervention).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import numpy as np

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database import SessionLocal, init_db
from backend.app.models import Patient
from backend.app.schemas import WhatIfRequest
from backend.app.services.ehr_service import EHRService
from backend.app.services.fusion_service import FusionService
from backend.app.services.whatif_service import WhatIfService
from backend.scripts.seed import seed_database


def evaluate_whatif_effects(cohort_size: int = 60) -> dict:
    init_db()
    db = SessionLocal()
    try:
        patients = db.query(Patient).limit(cohort_size).all()
        if len(patients) < cohort_size:
            print(f"Database contains {len(patients)} patients (< {cohort_size}). Seeding cohort...")
            db.close()
            seed_database(num_patients=cohort_size, days=60)
            db = SessionLocal()
            patients = db.query(Patient).limit(cohort_size).all()

        ehr_svc = EHRService(db)
        fusion_svc = FusionService(db)
        whatif_svc = WhatIfService(db)

        sleep_deltas = []
        med_deltas = []
        steps_deltas = []

        print(f"Evaluating counterfactual what-if scenarios across {len(patients)} patients...")

        for idx, p in enumerate(patients):
            static_dict = ehr_svc.get_patient_static_dict(p)
            base_features = fusion_svc.compute_current_features(static_dict)

            # 1. Sleep + 1.5 h
            curr_sleep = base_features.get("sleep_duration_last_night", 7.0)
            req_sleep = WhatIfRequest(sleep_hours=float(min(9.0, max(4.0, curr_sleep + 1.5))))
            res_sleep = whatif_svc.run_counterfactual(p.patient_id, base_features, req_sleep)
            sleep_deltas.append(res_sleep.delta)

            # 2. Medication taken
            req_med = WhatIfRequest(medication_taken=True)
            res_med = whatif_svc.run_counterfactual(p.patient_id, base_features, req_med)
            med_deltas.append(res_med.delta)

            # 3. Steps + 4000
            curr_steps = base_features.get("steps_yesterday", 5000.0)
            req_steps = WhatIfRequest(steps=int(min(12000, max(1000, curr_steps + 4000))))
            res_steps = whatif_svc.run_counterfactual(p.patient_id, base_features, req_steps)
            steps_deltas.append(res_steps.delta)

        def analyze_deltas(deltas: list[float], name: str) -> dict:
            arr = np.array(deltas, dtype=float)
            wrong_way = float(np.mean(arr > 0.0001))
            improved = float(np.mean(arr < -0.0001))
            neutral = float(np.mean(np.abs(arr) <= 0.0001))
            mean_d = float(np.mean(arr))
            std_d = float(np.std(arr))
            median_d = float(np.median(arr))
            min_d = float(np.min(arr))
            max_d = float(np.max(arr))

            return {
                "name": name,
                "n": len(arr),
                "mean_delta": round(mean_d, 4),
                "std_delta": round(std_d, 4),
                "median_delta": round(median_d, 4),
                "min_delta": round(min_d, 4),
                "max_delta": round(max_d, 4),
                "fraction_improved": round(improved, 4),
                "fraction_wrong_way": round(wrong_way, 4),
                "fraction_neutral": round(neutral, 4),
            }

        stats_sleep = analyze_deltas(sleep_deltas, "Sleep +1.5h")
        stats_med = analyze_deltas(med_deltas, "Medication Taken")
        stats_steps = analyze_deltas(steps_deltas, "Steps +4000")

        return {
            "cohort_size": len(patients),
            "interventions": {
                "sleep": stats_sleep,
                "medication": stats_med,
                "steps": stats_steps,
            },
        }
    finally:
        db.close()


def generate_whatif_markdown_report(results: dict, output_path: str) -> None:
    n = results["cohort_size"]
    s = results["interventions"]["sleep"]
    m = results["interventions"]["medication"]
    st = results["interventions"]["steps"]

    content = f"""# Counterfactual What-If Intervention Effects Report

## Evaluation Cohort
- **Cohort Size**: {n} patients evaluated longitudinally from NightWatch database.
- **Model**: LightGBM + isotonic calibration (production pipeline v1.1.0).
- **Framing**: Counterfactual interventions are framed as sustained behavioral changes over the coming week, consistently updating all dependent physiological features (sleep debt, 7-day means, z-scores, poor-sleep streak, autonomic coupling, and adherence rates).

## Empirical Results

| Intervention | Mean Delta (Risk Shift) | Std Dev | Median Delta | Min Delta | Max Delta | Fraction Improved (Risk Drop) | Fraction Wrong-Way (Risk Rise) | Neutral (|Δ| < 0.01%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Sleep +1.5 h** | {s['mean_delta']:+.4f} ({s['mean_delta']*100:+.2f}%) | {s['std_delta']:.4f} | {s['median_delta']:+.4f} | {s['min_delta']:+.4f} | {s['max_delta']:+.4f} | {s['fraction_improved']*100:.1f}% | {s['fraction_wrong_way']*100:.1f}% | {s['fraction_neutral']*100:.1f}% |
| **Medication Taken** | {m['mean_delta']:+.4f} ({m['mean_delta']*100:+.2f}%) | {m['std_delta']:.4f} | {m['median_delta']:+.4f} | {m['min_delta']:+.4f} | {m['max_delta']:+.4f} | {m['fraction_improved']*100:.1f}% | {m['fraction_wrong_way']*100:.1f}% | {m['fraction_neutral']*100:.1f}% |
| **Steps +4,000** | {st['mean_delta']:+.4f} ({st['mean_delta']*100:+.2f}%) | {st['std_delta']:.4f} | {st['median_delta']:+.4f} | {st['min_delta']:+.4f} | {st['max_delta']:+.4f} | {st['fraction_improved']*100:.1f}% | {st['fraction_wrong_way']*100:.1f}% | {st['fraction_neutral']*100:.1f}% |

## Plain-Language Clinical Interpretation

1. **Modest Effect Sizes**:
   The empirical risk deltas from lifestyle/wearable interventions average between **{min(s['mean_delta'], m['mean_delta'], st['mean_delta'])*100:+.2f}%** and **{max(s['mean_delta'], m['mean_delta'], st['mean_delta'])*100:+.2f}%**. Consistent with the feature ablation studies, baseline blood pressure history and hemodynamic volatility remain the dominant drivers of next-day hypertensive episodes. Wearable autonomic signals (sleep, HRV, steps) modulate short-term probability at the margin.

2. **Paradoxical "Wrong-Way" Risk Shifts**:
   - **Sleep +1.5 h**: {s['fraction_wrong_way']*100:.1f}% of patients moved the wrong way.
   - **Medication Taken**: {m['fraction_wrong_way']*100:.1f}% of patients moved the wrong way.
   - **Steps +4,000**: {st['fraction_wrong_way']*100:.1f}% of patients moved the wrong way.
   *Etiology*: In non-linear gradient-boosted decision trees, feature correlations can interact in high-dimensional split space (e.g., higher sleep duration shifting into a tree leaf where baseline SBP interacts with higher nocturnal sympathetic tone proxy). NightWatch candidly discloses these paradoxical shifts rather than artificially smoothing them.

3. **Clinical Trust and Guardrails**:
   - Every what-if response includes an explicit `effect_note` contextualizing modest changes.
   - Mandatory disclaimer: "Simulated scenario for clinical discussion. Modeled estimate, not a treatment recommendation."
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Successfully generated {output_path}")


if __name__ == "__main__":
    results = evaluate_whatif_effects(cohort_size=60)
    out_file = os.path.join(PROJECT_ROOT, "docs", "whatif_effects.md")
    generate_whatif_markdown_report(results, out_file)
