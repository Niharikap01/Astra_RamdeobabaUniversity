# NightWatch Synthetic Cohort & Physiological Feature Data Dictionary

## 1. Overview & Simulation Architecture

NightWatch generates a synthetic longitudinal digital twin cohort ($N=200$ patients, $D=120$ days) to evaluate early-warning hemodynamic prediction models. The simulation couples static electronic health record (EHR) phenotypes, autoregressive wearable sleep architecture, autonomic balance (HRV RMSSD, resting heart rate), daily physical activity, smart medication adherence, and ground-truth home blood pressure cuff readings.

All dynamic risk factors act as physiological triggers that induce acute hemodynamic excursions atop resting baseline arterial pressures.

---

## 2. Patient Cohort Archetypes & Static Baselines (`ehr_simulator.py`)

Each patient is assigned to one of six clinical archetypes reflecting real-world phenotypic heterogeneity:

| Archetype | Prevalence | Baseline SBP (mmHg) | Baseline DBP (mmHg) | Baseline Sleep (h) | Baseline RMSSD (ms) | Resting HR (bpm) | Description & Clinical Phenotype |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `well_controlled` | 25% | $\mathcal{N}(116.0, 3.5^2)$ | $\mathcal{N}(74.0, 3.0^2)$ | $\mathcal{N}(7.6, 0.4^2)$ | $\mathcal{N}(46.0, 6.0^2)$ | $\mathcal{N}(61.0, 4.0^2)$ | Excellent lifestyle & adherence; high autonomic vagal reserve. |
| `controlled_hypertensive` | 25% | $\mathcal{N}(122.0, 4.0^2)$ | $\mathcal{N}(78.0, 3.0^2)$ | $\mathcal{N}(7.1, 0.5^2)$ | $\mathcal{N}(37.0, 5.0^2)$ | $\mathcal{N}(65.0, 4.5^2)$ | Stable pharmacotherapy control; vulnerable to compound triggers. |
| `poor_sleep_risk` | 15% | $\mathcal{N}(126.0, 4.0^2)$ | $\mathcal{N}(81.0, 3.5^2)$ | $\mathcal{N}(5.4, 0.4^2)$ | $\mathcal{N}(24.0, 4.0^2)$ | $\mathcal{N}(73.0, 5.0^2)$ | Chronic short sleep, fragmented architecture; blunted nocturnal dip. |
| `non_adherent` | 15% | $\mathcal{N}(125.0, 4.5^2)$ | $\mathcal{N}(80.5, 3.5^2)$ | $\mathcal{N}(6.8, 0.6^2)$ | $\mathcal{N}(32.0, 5.5^2)$ | $\mathcal{N}(69.0, 5.0^2)$ | Variable medication compliance; intermittent vascular receptor rebound. |
| `sedentary_high_risk` | 10% | $\mathcal{N}(127.0, 4.0^2)$ | $\mathcal{N}(81.5, 3.5^2)$ | $\mathcal{N}(6.3, 0.5^2)$ | $\mathcal{N}(22.0, 3.5^2)$ | $\mathcal{N}(76.0, 5.5^2)$ | Low physical activity (<3500 steps/d); arterial stiffness, metabolic risk. |
| `osa_suspected` | 10% | $\mathcal{N}(127.0, 4.0^2)$ | $\mathcal{N}(81.5, 3.5^2)$ | $\mathcal{N}(5.8, 0.6^2)$ | $\mathcal{N}(25.0, 4.0^2)$ | $\mathcal{N}(74.0, 5.0^2)$ | Obstructive sleep apnea with nocturnal desaturations and sharp morning surge. |

---

## 3. Dynamic Longitudinal Simulation Parameters (`wearable_simulator.py`)

### 3.1. Sleep Architecture & Autoregressive Sleep Debt
- **Sleep Duration ($h$):** Sampled around archetype baseline $\mu_{\text{sleep}}$ with Gaussian noise $\sigma \in [0.35, 0.70]$ h and weekend boost $+0.4$ h.
- **Sleep Stages:** Deep sleep ratio $\mathcal{N}(0.10\text{--}0.19, 0.02^2)$; REM sleep ratio $\mathcal{N}(0.15\text{--}0.22, 0.02^2)$; awakenings Poisson-distributed ($\lambda = 1.3\text{--}5.5$).
- **Sleep Efficiency ($\eta$):** Bounded ratio $[0.50, 0.98]$ reflecting fragmented vs consolidated rest.
- **Daily Sleep Debt ($\Delta D_t$):** $\Delta D_t = \text{clip}(\text{baseline\_sleep} - \text{sleep}_t, -1.0, 3.0)$ hours.
- **Autoregressive Debt Accumulation:** $D_t = 0.70 \times D_{t-1} + 0.30 \times \max(0, \Delta D_t)$.
- **Sleep Risk Index:** $\text{Risk}_{\text{sleep}} = \text{clip}(D_t \times 0.16 + \max(0, 0.85 - \eta_t) \times 0.70, 0.0, 0.50)$.

### 3.2. Autonomic Tone & Heart Rate Variability
- **RMSSD HRV ($ms$):** Governed by parasympathetic balance:
  $$\text{HRV}_t = \text{base\_hrv} + (\text{sleep}_t - \text{base\_sleep}) \times 3.0 + (\eta_t - 0.85) \times 15.0 - \text{stress}_t \times 8.0 + \mathcal{N}(0, 2.5^2)$$
- **Relative HRV Drop:** $\Delta\text{HRV}_{\text{rel}} = \text{clip}\left(\frac{\text{base\_hrv} - \text{HRV}_t}{\max(10, \text{base\_hrv})}, 0.0, 1.0\right)$.
- **HRV Risk Index:** $\text{Risk}_{\text{hrv}} = \Delta\text{HRV}_{\text{rel}} \times 0.32$.
- **Resting Heart Rate ($bpm$):** Coupled inversely with vagal withdrawal:
  $$\text{RHR}_t = \text{base\_rhr} - (\text{sleep}_t - \text{base\_sleep}) \times 1.5 - (\eta_t - 0.85) \times 8.0 + \text{stress}_t \times 6.5 + \mathcal{N}(0, 1.8^2)$$

### 3.3. Medication Adherence
- **Daily Compliance Probability:** $P(\text{med}_t = 1)$ is $0.98$ for well-controlled, $0.94$ for controlled, $0.88\text{--}0.90$ for poor sleep/OSA/sedentary, and $0.60$ for non-adherent.
- **Streak Tracking:** Missed dose streak $k$ increments sequentially when missed, resetting to $0$ upon ingestion.
- **Adherence Risk Index:** $\text{Risk}_{\text{med}} = 0.0$ if taken; $0.26 + \min(0.24, k \times 0.10)$ if missed.

### 3.4. Physical Activity & Sedentary Burden
- **Daily Step Count:** Archetype base (sedentary: 2800; normal: 6400; active: 8800) $\pm$ fatigue penalty and Gaussian noise $\sigma=1200$.
- **Sedentary Risk Index:** $+0.08$ if steps $< 3500$; $-0.04$ if steps $> 8500$; $0.0$ otherwise.

### 3.5. Sodium & Psychosocial Stress Proxy
- **Compound Stress Proxy:** $\text{SodiumProxy}_t = \text{clip}(\text{stress}_t \times 0.70 + \text{Beta}(2, 4) \times 0.40, 0.0, 1.0)$.
- **Stress Risk Index:** $\text{Risk}_{\text{stress}} = (\text{SodiumProxy}_t - 0.32) \times 0.16$.

### 3.6. Acute Hemodynamic Response & Blood Pressure Generation
- **Static EHR Risk:**
  $$\text{Risk}_{\text{ehr}} = (\text{base\_sbp} - 124.0) \times 0.015 + \text{DM} \times 0.05 + \text{CKD} \times 0.06 + \text{OSA} \times 0.06 + (\text{BMI} - 27.0) \times 0.008 + (\text{Age} - 55.0) \times 0.003$$
- **Latent Logit ($z$):**
  $$z = -2.20 + \text{Risk}_{\text{ehr}} + \text{Risk}_{\text{sleep}} + \text{Risk}_{\text{hrv}} + \text{Risk}_{\text{med}} + \text{Risk}_{\text{sedentary}} + \text{Risk}_{\text{stress}}$$
- **Latent Risk Probability:** $P_{\text{latent}} = \frac{1}{1 + e^{-z}}$.
- **Acute SBP Surge (mmHg):**
  $$\Delta\text{SBP} = \text{Risk}_{\text{sleep}} \times 16.0 + \text{Risk}_{\text{hrv}} \times 14.0 + \text{Risk}_{\text{med}} \times 20.0 + (5.5 \text{ if sedentary else } 0) + \max(0, \text{Risk}_{\text{stress}}) \times 9.0$$
- **Acute DBP Surge (mmHg):**
  $$\Delta\text{DBP} = \text{Risk}_{\text{sleep}} \times 9.0 + \text{Risk}_{\text{hrv}} \times 8.0 + \text{Risk}_{\text{med}} \times 12.0 + (3.0 \text{ if sedentary else } 0) + \max(0, \text{Risk}_{\text{stress}}) \times 5.0$$
- **Morning Surge:** $+2.0$ mmHg base, $+3.5$ mmHg if OSA or short sleep ($< 5.5$ h).
- **Home BP Cuff Measurements:**
  - $\text{Morning SBP} = \max(90, \mathcal{N}(\text{base\_sbp} + \Delta\text{SBP} + \text{MorningSurge}, 3.5^2))$
  - $\text{Morning DBP} = \max(55, \mathcal{N}(\text{base\_dbp} + \Delta\text{DBP} + \text{MorningSurge} \times 0.6, 2.5^2))$
  - $\text{Evening SBP} = \max(90, \mathcal{N}(\text{base\_sbp} + \Delta\text{SBP} \times 0.82, 3.5^2))$
  - $\text{Evening DBP} = \max(55, \mathcal{N}(\text{base\_dbp} + \Delta\text{DBP} \times 0.82, 2.5^2))$

---

## 4. Ground Truth Target & Temporal Causality Guarantee

- **Target Label ($Y_t$):** Binary indicator of a next-day hypertensive episode:
  $$Y_t = \mathbb{I}\left(\text{MorningSBP}_{t+1} \ge 140 \lor \text{MorningDBP}_{t+1} \ge 90 \lor \text{EveningSBP}_{t+1} \ge 140 \lor \text{EveningDBP}_{t+1} \ge 90\right)$$
- **Positive-Class Prevalence:** Calibrated to $21.2\%$ across all patient records, matching real-world clinical excursion incidence ($20\text{--}35\%$).
- **Strict Causality Guarantee:** All 65 features evaluated at day $t$ utilize observations timestamped on or before day $t$. No next-day readings ($t+1$) or future targets are accessible to feature extraction.
- **Alert Lead Time ($T_{\text{lead}}$):** Evaluated at 21:00 on day $t$:
  - $11.0$ hours if the morning reading on day $t+1$ (08:00) exhibits excursion ($\ge 140/90$).
  - $23.5$ hours if the morning reading is controlled but the evening reading on day $t+1$ (20:30) exhibits excursion.

---

## 5. Feature Dictionary & 4-Tier Ablation Mapping

| Feature Name | Modality Tier | Window | Clinical Definition & Units |
| :--- | :--- | :---: | :--- |
| `age` | EHR Static | Static | Patient age in years |
| `sex_male` | EHR Static | Static | Binary (1=Male, 0=Female) |
| `bmi` | EHR Static | Static | Body mass index ($\text{kg/m}^2$) |
| `hypertension_duration_years` | EHR Static | Static | Years since formal hypertension diagnosis |
| `diabetes`, `ckd`, `dyslipidemia`, `prior_stroke`, `ihd`, `osa` | EHR Static | Static | Binary ICD-10 clinical comorbidity flags |
| `family_history_cvd` | EHR Static | Static | Binary family history of premature CVD |
| `hba1c`, `ldl_cholesterol`, `hdl_cholesterol`, `triglycerides` | EHR Static | Static | Baseline laboratory metabolic parameters |
| `serum_creatinine`, `egfr`, `serum_potassium` | EHR Static | Static | Baseline renal function and electrolyte markers |
| `med_acei`, `med_arb`, `med_ccb`, `med_beta_blocker`, `med_diuretic`, `med_statin` | EHR Static | Static | Baseline prescribed cardioprotective medications |
| `sbp_latest`, `dbp_latest` | BP Cuff | 1-day | Most recent evening or morning home BP cuff reading (mmHg) |
| `sbp_mean_3d`, `sbp_mean_7d`, `dbp_mean_7d` | BP Cuff | 3d / 7d | Rolling mean arterial pressure values (mmHg) |
| `sbp_std_7d` | BP Cuff | 7d | 7-day systolic blood pressure standard deviation (mmHg) |
| `sbp_slope_7d` | BP Cuff | 7d | 7-day linear trajectory slope of mean daily SBP (mmHg/day) |
| `morning_sbp_mean_7d`, `evening_sbp_mean_7d` | BP Cuff | 7d | Diurnal separation of 7-day home BP readings (mmHg) |
| `morning_minus_evening_sbp` | BP Cuff | 7d | Difference between morning surge and evening resting BP (mmHg) |
| `days_since_last_bp_reading` | BP Cuff | Dynamic | Monitoring gap indicator (0 for daily compliant users) |
| `bp_reading_count_7d` | BP Cuff | 7d | Number of validated cuff measurements taken in past week |
| `sleep_duration_last_night` | Sleep & HRV | 1-day | Prior-night total sleep duration (hours) |
| `deep_sleep_last_night`, `rem_sleep_last_night` | Sleep & HRV | 1-day | Prior-night restorative sleep stages (hours) |
| `awakenings_last_night` | Sleep & HRV | 1-day | Nocturnal awakenings count from smart ring / watch |
| `sleep_efficiency_last_night` | Sleep & HRV | 1-day | Ratio of time asleep to total time in bed |
| `sleep_duration_mean_7d`, `sleep_efficiency_mean_7d` | Sleep & HRV | 7d | 7-day rolling sleep duration and efficiency averages |
| `sleep_debt_7d` | Sleep & HRV | 7d | Cumulative deficit relative to patient baseline sleep (hours) |
| `poor_sleep_streak` | Sleep & HRV | Consecutive | Consecutive nights with $<6.0$ hours or $<75\%$ efficiency |
| `sleep_duration_zscore_30d`, `sleep_efficiency_zscore_30d` | Sleep & HRV | 30d | Normalized personal z-scores relative to 30-day baseline |
| `hrv_rmssd_last_night` | Sleep & HRV | 1-day | Nocturnal root mean square of successive differences (ms) |
| `hrv_rmssd_mean_7d` | Sleep & HRV | 7d | 7-day moving average of nocturnal RMSSD HRV (ms) |
| `hrv_zscore_30d` | Sleep & HRV | 30d | Normalized RMSSD z-score relative to patient 30-day mean |
| `hrv_drop_from_personal_baseline` | Sleep & HRV | Contrast | Absolute drop in last-night HRV relative to personal baseline (ms) |
| `resting_hr_last_night`, `resting_hr_mean_7d`, `resting_hr_zscore_30d` | Sleep & HRV | 1d / 7d / 30d | Resting heart rate nocturnal measurements (bpm) |
| `sbp_deviation_vs_30d_baseline`, `dbp_deviation_vs_30d_baseline` | Deviation | 30d | Hemodynamic deviation from patient personal 30-day median (mmHg) |
| `bp_variability_ratio_7d_vs_30d` | Deviation | Contrast | Ratio of acute 7-day BP standard deviation to chronic 30-day baseline |
| `steps_yesterday`, `steps_mean_7d` | Full Twin | 1d / 7d | Daytime pedometer step volume |
| `active_minutes_yesterday`, `sedentary_hours_yesterday` | Full Twin | 1-day | Daily physical activity duration and sedentary behavior hours |
| `medication_taken_last_night` | Full Twin | 1-day | Smart pillbox binary confirmation of prescribed evening dose |
| `missed_doses_7d`, `adherence_rate_30d` | Full Twin | 7d / 30d | Longitudinal medication adherence tracking (%) |
| `hours_since_last_medication` | Full Twin | Dynamic | Time elapsed since last recorded pillbox ingestion event (hours) |
