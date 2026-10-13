# NightWatch Model Evaluation Report

**Model Version:** 1.1.0  
**Target:** 24-Hour Hypertensive Episode Prediction (Next-day SBP $\ge 140$ mmHg or DBP $\ge 90$ mmHg)  
**Positive Episode Rate:** 27.7%  
**Ground Truth:** Validated Home Blood Pressure Cuff Readings  
**Context Modalities:** Wearable Sleep Architecture, Autonomic HRV, Physical Activity, Smart Adherence  

---

## 1. Executive Summary

NightWatch benchmarks next-day hypertensive episode prediction by combining static EHR profiles, home blood pressure monitoring, and longitudinal wearable telemetry. On held-out patient subjects using patient-level  (70% train / 15% validation / 15% test; 3,150 test samples across 30 patients), the full multimodal model achieves a **ROC-AUC of 0.7903** and a **PR-AUC of 0.5000**.

Using a **patient-level cluster bootstrap** (1,000 resamples of whole patients), the 95% confidence intervals are:
- **ROC-AUC (Patient Cluster 95% CI):** [0.6925, 0.8655]
- **PR-AUC (Patient Cluster 95% CI):** [0.3292, 0.6062]

---

## 2. Four-Tier Modality Ablation (5 Independent Patient-Wise Split Seeds)

### 2.1. Absolute Performance Across Seeds
| Model Tier | Input Features | Mean ROC-AUC ± SD | Mean PR-AUC ± SD | Seed 42 ROC-AUC | Seed 42 PR-AUC |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **1. EHR Only** | Demographics, ICD-10 comorbidities, baseline labs | 0.6069 ± 0.0719 | 0.3956 ± 0.0832 | 0.5901 | 0.3724 |
| **2. EHR + BP Cuff** | Static EHR + longitudinal morning & evening BP trends | 0.7976 ± 0.0347 | 0.5118 ± 0.0826 | 0.7812 | 0.4850 |
| **3. + Sleep Architecture & HRV** | Static EHR + BP + sleep debt, efficiency, RMSSD HRV | 0.7997 ± 0.0400 | 0.5527 ± 0.0321 | 0.7864 | 0.4921 |
| **4. Full Multimodal Twin** | Full features (+ steps, sedentary hours, oral med adherence) | **0.8043 ± 0.0364** | **0.5399 ± 0.0457** | **0.7903** | **0.5000** |

### 2.2. Paired Differences Between Consecutive Tiers
Differences are computed within the exact same patient split seed (=5$ seeds):

| Comparison | $\Delta$ ROC-AUC (Mean ± SD) | ROC Win Rate | $\Delta$ PR-AUC (Mean ± SD) | PR Win Rate | Consistent Benefit? |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Tier 2 (EHR+BP) vs Tier 1 (EHR)** | **+0.1907 ± 0.0441** | **5/5** | **+0.1162 ± 0.1482** | **4/5** | **Yes (consistent lift)** |
| **Tier 3 (+Sleep/HRV) vs Tier 2 (EHR+BP)** | +0.0021 ± 0.0173 | 3/5 | +0.0409 ± 0.0917 | 3/5 | Mixed (marginal lift; 3/5 wins) |
| **Tier 4 (Full Twin) vs Tier 3 (+Sleep/HRV)** | +0.0046 ± 0.0086 | 3/5 | -0.0128 ± 0.0411 | 2/5 | Mixed (no consistent PR lift) |

*Finding:* Adding daily home BP cuff data to static EHR yields a decisive, consistent lift (+0.1907 ROC, 5/5 wins). With daily BP cuff data already present, adding wearable sleep and HRV yields only small paired differences (+0.0021 ROC, +0.0409 PR), outperforming Tier 2 in 3 of 5 seeds.

---

## 3. Sparse-BP Experiment (2–3 Cuff Readings / Week)

In real-world remote monitoring, patients rarely take cuff measurements every day. When cuff readings are limited to 2–3 days per week (unmeasured days forward-filled from last measurement, matching clinical RPM workflow):

| Model Tier | Daily BP Mean ROC-AUC | Sparse BP Mean ROC-AUC ± SD | Sparse BP Mean PR-AUC ± SD | $\Delta$ vs Prev Tier (ROC) | $\Delta$ vs Prev Tier (PR) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. EHR Only** | 0.6069 | 0.6069 ± 0.0719 | 0.3956 ± 0.0832 | Baseline | Baseline |
| **2. EHR + BP Cuff** | 0.7976 | 0.7526 ± 0.0277 | 0.4640 ± 0.0512 | +0.1457 ± 0.0670 (5/5) | +0.0684 ± 0.1265 (4/5) |
| **3. + Sleep & HRV** | 0.7997 | 0.7822 ± 0.0439 | 0.5046 ± 0.0355 | +0.0296 ± 0.0297 (3/5) | **+0.0406 ± 0.0542 (4/5)** |
| **4. Full Twin** | 0.8043 | 0.7854 ± 0.0430 | 0.5087 ± 0.0273 | +0.0031 ± 0.0067 (3/5) | +0.0042 ± 0.0096 (3/5) |

*Clinical Insight:* When home cuff readings are sparse (2–3 readings/week), adding continuous wearable sleep and autonomic signals provides a larger and more consistent benefit (+0.0296 ROC-AUC, +0.0406 PR-AUC, 4/5 wins on PR) than when twice-daily cuff readings are available.

---

## 4. Alert Timing & Lead Time Worked Example

Alerts are evaluated at bedtime (21:00 on day $). If calibrated risk probability  \ge 0.50$, a clinician alert fires. Next-day cuff readings occur at 08:00 (morning) and 20:30 (evening).

### Worked Examples from Test Split:
1. **Patient A (, Day 14):**
   - **Alert Evaluation:** Day 14 21:00, Calibrated Prob = 0.504 $\rightarrow$ **Alert Fired**.
   - **Context:** Prior-night sleep 4.48h (efficiency 73.3%), HRV 8.4 ms, missed dose streak = 1.
   - **Next-Day Episode:** Day 15 Morning (08:00) SBP 141.6 / DBP 98.4 mmHg (**Hypertensive Surge**).
   - **Lead Time:** {\text{morning onset}} (08:00) - T_{\text{alert}} (21:00) = \mathbf{11.0\text{ hours}}$.
2. **Patient B (, Day 36):**
   - **Alert Evaluation:** Day 36 21:00, Calibrated Prob = 0.564 $\rightarrow$ **Alert Fired**.
   - **Context:** Short sleep 5.0h, suppressed HRV 11.0 ms.
   - **Next-Day Episode:** Day 37 Morning (08:00) SBP 139.4 / DBP 86.0 (normotensive); Evening (20:30) DBP 90.4 mmHg (**Hypertensive Excursion**).
   - **Lead Time:** {\text{evening onset}} (20:30) - T_{\text{alert}} (21:00) = \mathbf{23.5\text{ hours}}$.

---

## 5. Limitations

Results come from synthetic data with assumptions built into the simulator, and the sleep/HRV effect is not validated on real patients. The coupling between sleep debt, vagal tone (HRV), and next-day vascular pressure reflects algorithmic formulations and literature priors rather than prospectively verified human physiology. Real-world validation with randomized clinical trials and certified ambulatory blood pressure monitoring (ABPM) is strictly required before clinical deployment.
