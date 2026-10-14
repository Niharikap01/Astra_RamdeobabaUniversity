# NightWatch Agent Execution Evidence

This document records the exact commands run, pasted raw terminal outputs, elapsed times, git diff stats, and unverified/not run items for each phase of work.

---

## Initial Verification: Contradictory M1 Reports Check

### 1. `npx tsc --noEmit`
**Command:**
```powershell
npx tsc --noEmit
```
**Raw Output:**
```
(exit code 0, no errors)
```

### 2. Clean `.venv_check` pytest
**Commands:**
```powershell
python -m venv .venv_check
.\.venv_check\Scripts\pip.exe install -r backend/requirements.txt
.\.venv_check\Scripts\pytest.exe
```
**Raw Output:**
```
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\HP\Downloads\nightwatch (1)
plugins: anyio-4.15.1, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 18 items

backend\tests\test_api.py .............                                  [ 72%]
backend\tests\test_fusion.py ..                                          [ 83%]
backend\tests\test_prediction.py .                                       [ 88%]
backend\tests\test_twin.py .                                             [ 94%]
backend\tests\test_whatif.py .                                           [100%]

============================== warnings summary ===============================
...
====================== 18 passed, 16 warnings in 21.37s =======================
```

---

## PHASE 0: Finish M1

### Part (a): Cold Start Verification
Deleted generated data files (`data/raw/*.parquet`, `data/processed/*.parquet`) and ML artifacts (`ml/artifacts/*.joblib`, `ml/artifacts/*.png`).

#### 1. Cold Start from Repo Root
**Command:**
```powershell
$sw = [System.Diagnostics.Stopwatch]::StartNew(); .\.venv_check\Scripts\pytest.exe; $sw.Stop(); Write-Host "ELAPSED: $($sw.Elapsed.TotalSeconds) seconds"
```
**Raw Output:**
```
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\HP\Downloads\nightwatch (1)
plugins: anyio-4.15.1, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 18 items

backend\tests\test_api.py .............                                  [ 72%]
backend\tests\test_fusion.py ..                                          [ 83%]
backend\tests\test_prediction.py .                                       [ 88%]
backend\tests\test_twin.py .                                             [ 94%]
backend\tests\test_whatif.py .                                           [100%]

============================== warnings summary ===============================
...
================= 18 passed, 40 warnings in 103.72s (0:01:43) =================
ELAPSED: 105.1370053 seconds
```

#### 2. Directory Hygiene Check after Root Run
**Command:**
```powershell
Test-Path backend/data, backend/ml, backend/docs
```
**Raw Output:**
```
False
False
False
```

#### 3. Cold Start from `backend/`
Deleted generated parquet and joblib files again to force retraining from `backend/`.
**Command:**
```powershell
cd backend
$sw = [System.Diagnostics.Stopwatch]::StartNew(); ..\.venv_check\Scripts\pytest.exe; $sw.Stop(); Write-Host "ELAPSED: $($sw.Elapsed.TotalSeconds) seconds"
```
**Raw Output:**
```
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\HP\Downloads\nightwatch (1)\backend
plugins: anyio-4.15.1, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 18 items

tests\test_api.py .............                                          [ 72%]
tests\test_fusion.py ..                                                  [ 83%]
tests\test_prediction.py .                                               [ 88%]
tests\test_twin.py .                                                     [ 94%]
tests\test_whatif.py .                                                   [100%]

============================== warnings summary ===============================
...
================= 18 passed, 40 warnings in 92.50s (0:01:32) ==================
ELAPSED: 97.946837 seconds
```

#### 4. Directory Hygiene Check after Backend Run
**Command:**
```powershell
Test-Path backend/data, backend/ml, backend/docs
```
**Raw Output:**
```
False
False
False
```

---

### Part (b): Explanation of `test_whatif` Behavior
Why did test count change from 15 (14 passed, 1 failed) to 18 passed?
1. **Test Count (15 to 18):** 3 new unit tests were added to `backend/tests/test_api.py` during M1: `test_health_check_db_failure`, `test_health_check_model_not_loaded`, and `test_config_app_port_env`.
2. **`test_whatif` Passing Due to Calibration Luck:**
In baseline, the model predictions for `test_whatif` had:
- LightGBM Raw baseline score: `0.465877`
- LightGBM Raw counterfactual score: `0.437782`
- Raw score delta: `-0.028095`
Because the model's feature gains are dominated by 7-day BP means (`sbp_mean_7d`: 59,140, `dbp_mean_7d`: 46,066, `hrv_rmssd_mean_7d`: 37,591) while single-night sleep/steps/medication have tiny gains (262, 132, 83), the raw score change is small (-0.028).
Under the pre-M1 calibrator, both raw scores fell into the exact same bin/step of `IsotonicRegression`, giving calibrated delta = `0.000000`, which caused `assert response.delta < 0.0` to fail.
When the model was retrained under seed 42 in M1:
- Calibrated baseline: `0.336814`
- Calibrated counterfactual: `0.334361`
- Calibrated delta: `-0.002453`
**Finding:** The test passed solely due to calibration luck (the two scores happened to straddle an empirical step threshold in the retrained isotonic calibrator). The single-night counterfactual does not produce a sustained physiological shift in the model's primary drivers.

---

### Part (c): Moving React App to `dashboard/`
The React application was moved into `dashboard/` via `git mv`:
- `src/` -> `dashboard/src/`
- `index.html` -> `dashboard/index.html`
- `package.json` -> `dashboard/package.json`
- `package-lock.json` -> `dashboard/package-lock.json`
- `vite.config.ts` -> `dashboard/vite.config.ts`
- `tsconfig.json` -> `dashboard/tsconfig.json`
- `tailwind.config.js` -> `dashboard/tailwind.config.js`

Updated `Makefile`, `scripts/dev.ps1`, `scripts/dashboard.ps1`, `.gitignore`, and `.env.example`.

#### esbuild Dependency Analysis
**Command:**
```powershell
npm ls esbuild
```
**Raw Output:**
```
react-example@0.0.0 C:\Users\HP\Downloads\nightwatch (1)
+-- esbuild@0.28.2
+-- tsx@4.23.15
| `-- esbuild@0.28.2 deduped
`-- vite@8.3.4
  `-- esbuild@0.28.2 deduped
```
**Conclusion:** `esbuild` is a direct dependency of both `vite` and `tsx`. The explicit top-level `esbuild` pin in `package.json` was redundant and has been removed.

#### Verification in `dashboard/`
1. `npm ci`:
```
added 69 packages, and audited 70 packages in 22s
16 packages are looking for funding
  run `npm fund` for details
found 0 vulnerabilities
```
2. `npm run build`:
```
> react-example@0.0.0 build
> vite build

vite v8.3.4 building client environment for production...
transforming...
✓ 16 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   1.25 kB │ gzip:  0.58 kB
dist/assets/index-CaHEg_y7.css   40.66 kB │ gzip:  7.82 kB
dist/assets/index-BPfduECR.js   219.49 kB │ gzip: 68.57 kB
✓ built in 293ms
```
3. `npx tsc --noEmit`:
```
(exit code 0, no errors)
```

---

### Part (d): Git Status & Gate Summary

#### `git diff --stat`
```
 .env.example                |  1 +
 .gitignore                  |  3 +++
 Makefile                    |  4 +--
 dashboard/package-lock.json | 61 ++++++++++++++++++++++++++++++++++++++++++++-
 dashboard/package.json      |  1 -
 dashboard/vite.config.ts    |  5 +++-
 6 files changed, 70 insertions(+), 5 deletions(-)
```

#### Untracked / Ignored
Unrelated generated files are kept ignored:
- `nightwatch.db` (ignored)
- `dashboard/dist/` (ignored)
- `data/raw/*.parquet`, `data/processed/*.parquet` (ignored)
- `ml/artifacts/*.joblib`, `ml/artifacts/*.png` (ignored)
- `ml/artifacts/metrics.json` and `docs/evaluation_report.md` checked out to committed baseline versions per Phase 4 requirement.

#### NOT RUN / NOT VERIFIED (Phase 0)
- End-to-end WebSocket telemetry streaming to dashboard (deferred to Phase 7).
- Docker deployment (deferred to Phase 8).

---

## PHASE 1: Thresholds and Alerts That Fire (M2)

### 1. Operating Thresholds Derivation (Validation Set Only)
Operating thresholds derived strictly from `data/processed/val.parquet` via `ml/robustness.py derive_operating_thresholds`:
- **Moderate Risk Threshold ($\tau_{\text{mod}}$):** `0.34` (validation false alert rate: 0.631 FA/patient-week, sensitivity: 96.5%)
- **High Risk Threshold ($\tau_{\text{high}}$):** `0.47` (validation false alert rate: 0.298 FA/patient-week $\le$ 0.30 target)

Persisted in committed file `ml/artifacts/thresholds.json`.

#### Honest Test Split Evaluation (`data/processed/test.parquet`, 30 patients, 450 patient-weeks)
- **High Threshold ($\tau = 0.47$):**
  - Sensitivity: `36.75%` (276 TP / 751 total positives)
  - Specificity: `91.66%` (2,199 TN / 2,399 total negatives)
  - Precision: `57.98%` (276 TP / 476 total alerts)
  - False Alerts Per Patient-Week: `0.444` (200 FP / 450 patient-weeks)
- **Moderate Threshold ($\tau = 0.34$):**
  - Sensitivity: `69.91%` (525 TP / 751 total positives)
  - Specificity: `70.36%` (1,688 TN / 2,399 total negatives)
  - Precision: `42.48%` (525 TP / 1,236 total alerts)
  - False Alerts Per Patient-Week: `1.580` (711 FP / 450 patient-weeks)

### 2. Alert Lifecycle & Cooldown Implementation
- **Cooldown:** In `backend/app/services/alert_service.py`, cooldown now explicitly evaluates `Alert.status.in_(["open", "acknowledged", "snoozed"])`, ensuring acknowledged and snoozed alerts within the 24-hour window properly suppress duplicate firing.
- **Snooze Expiry:** `Alert` model augmented with `snoozed_until`, `snooze_duration_minutes`, and `snooze_reason`. `check_and_expire_snoozes` reverts expired snoozes to `open`.
- **No Prefilled Snooze Reason:** Fallback placeholder text removed in `backend/app/schemas.py`, `dashboard/src/services/api.ts`, and `dashboard/src/components/RightAlertDrawer.tsx`.
- **Dynamic Threshold Integration:** `GET /api/thresholds` endpoint added; loaded into `backend/app/config.py` via `model_post_init` and consumed by dashboard components (`RiskSummaryCard`, `RiskHorizonChart`, `RightAlertDrawer`).

### 3. Test Execution & Coverage
**Command:**
```powershell
.\.venv_check\Scripts\pytest.exe backend/tests -v --cov=backend/app --cov-report=term-missing
```
**Raw Pytest Summary Output:**
```
backend/tests/test_alerts.py::test_alert_generation_at_threshold PASSED  [  4%]
backend/tests/test_alerts.py::test_alert_cooldown_open_acknowledged_snoozed PASSED [  8%]
backend/tests/test_alerts.py::test_snooze_duration_stored_and_expires PASSED [ 13%]
backend/tests/test_alerts.py::test_alerts_fire_in_simulation_run PASSED  [ 17%]
backend/tests/test_alerts.py::test_thresholds_endpoint PASSED            [ 21%]
backend/tests/test_api.py::test_health_check PASSED                      [ 26%]
backend/tests/test_api.py::test_health_check_db_failure PASSED           [ 30%]
backend/tests/test_api.py::test_health_check_model_not_loaded PASSED     [ 34%]
backend/tests/test_api.py::test_config_app_port_env PASSED               [ 39%]
backend/tests/test_api.py::test_patients_endpoints PASSED                [ 43%]
backend/tests/test_api.py::test_digital_twin_endpoints PASSED            [ 47%]
backend/tests/test_api.py::test_risk_and_history_endpoints PASSED        [ 52%]
backend/tests/test_api.py::test_whatif_endpoint PASSED                   [ 56%]
backend/tests/test_api.py::test_sensor_ingestion_and_pipeline_trigger PASSED [ 60%]
backend/tests/test_api.py::test_risk_horizon_and_why_risk_changed PASSED [ 65%]
backend/tests/test_api.py::test_alert_lifecycle_and_notes PASSED         [ 69%]
backend/tests/test_api.py::test_simulation_endpoints PASSED              [ 73%]
backend/tests/test_api.py::test_websocket_stream PASSED                  [ 78%]
backend/tests/test_fusion.py::test_zero_future_leakage_proof PASSED      [ 82%]
backend/tests/test_fusion.py::test_fusion_service_integration PASSED     [ 86%]
backend/tests/test_prediction.py::test_prediction_scoring PASSED         [ 91%]
backend/tests/test_twin.py::test_twin_construction PASSED                [ 95%]
backend/tests/test_whatif.py::test_whatif_counterfactual_simulation PASSED [100%]

======================= 23 passed, 17 warnings in 3.21s =======================
TOTAL Coverage: 84% (backend/app/services/alert_service.py: 97%)
```
**Elapsed Time:** 3.21 seconds (test execution)

### 4. Frontend Verification
**Command:**
```powershell
cd dashboard; npm run build; npx tsc --noEmit
```
**Raw Output:**
```
> react-example@0.0.0 build
> vite build

vite v8.3.4 building client environment for production...
transforming...
✓ 16 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   1.25 kB │ gzip:  0.58 kB
dist/assets/index-CaHEg_y7.css   40.66 kB │ gzip:  7.82 kB
dist/assets/index-BPfduECR.js   219.49 kB │ gzip: 68.57 kB
✓ built in 192ms
(exit code 0, no errors)
```

### 5. Git Diff Stat
**Command:**
```powershell
git diff --stat
```
**Raw Output:**
```
 backend/app/config.py                         | 18 ++++++++-
 backend/app/models.py                         |  5 ++-
 backend/app/routers/predictions.py            | 13 +++++++
 backend/app/schemas.py                        | 18 +++++++--
 backend/app/services/alert_service.py         | 53 +++++++++++++++++++++++----
 dashboard/src/components/RightAlertDrawer.tsx |  8 ++--
 dashboard/src/components/RiskHorizonChart.tsx |  8 ++--
 dashboard/src/components/RiskSummaryCard.tsx  |  6 ++-
 dashboard/src/services/api.ts                 | 13 +++++--
 dashboard/src/types/index.ts                  | 10 +++++
 ml/train_lightgbm.py                          | 35 ++++++++++++++++++
 11 files changed, 161 insertions(+), 26 deletions(-)
```

### 6. NOT RUN / NOT VERIFIED (Phase 1)
- Long-duration multi-day background simulation process running indefinitely (verified discrete multi-tick ingestion pipeline triggering alerts).
- Headless browser verification of snooze modal UI (deferred to Phase 7).


---

## Phase 2: Honest Data Layer (M3)

### 1. Summary of Changes
- **No Silent Imputations**: Removed hardcoded magic values (`125.0`, `80.0`, `7.0`, `35.0`, `68.0`, evening = morning - 2) across `backend/app/services/fusion_service.py` and `ml/feature_engineering.py`. Missing sensor readings now strictly preserve `np.nan`.
- **Honest Data Coverage & Refusal**: Implemented `compute_data_coverage` in `fusion_service.py`. When data coverage falls below `MIN_COVERAGE_THRESHOLD` (configurable in `config.py`, default `0.50`), `generate_and_save_prediction` and `/api/patients/{patient_id}/risk` refuse prediction with clear clinical reasons (HTTP 422 / ValueError).
- **Coverage-Aware Confidence & CI Scaling**: In `prediction_service.py`, implemented `compute_confidence(prob, coverage_pct)` returning a confidence score (0-1) and confidence interval bounds `[lower, upper]`. Confidence intervals widen proportionally as coverage decreases.
- **30-Day Personal Baseline Estimation**: Implemented `compute_patient_30d_baseline` in `ehr_service.py`, estimating individual physiological reference baselines from stored `SensorReading` events during the patient's first 30 days. Removed any reference to archetype simulator ground-truth parameters.
- **Sleep Fingerprint 6 Clinical Axes**: Rewrote `fingerprint_service.py` to evaluate the six clinical axes: Nocturnal BP Stability, Autonomic Resilience, Sleep Continuity, Morning Surge Control, Medication Coverage, and Recovery Capacity against each patient's personal 30-day baseline deviations.
- **Real Risk Horizon**: Updated `build_risk_horizon` in `twin_service.py` to return timestamps localized in `Asia/Kolkata` (+05:30), markers strictly from real stored BP cuff readings and medication logs, and setting `nocturnal_dipping_pct = None` to honestly reflect that home BP cuffs cannot measure nocturnal dipping without ABPM.
- **Why Risk Changed**: Feature snapshot diffing between consecutive predictions. When only 1 prediction exists, cleanly returns "No previous prediction exists." with `previous_risk_pct = None` and `risk_delta_pct = None`.
- **Frontend Safe Rendering**: In `dashboard/src/components/RiskHorizonChart.tsx`, rendered `nocturnal_dipping_pct` safely, displaying `"N/A (Requires ABPM)"` when `null`.

### 2. Pytest Execution & Coverage
**Command:**
```powershell
.\.venv_check\Scripts\pytest.exe -v --cov=backend/app --cov-report=term-missing
```
**Raw Output:**
```
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\HP\Downloads\nightwatch (1)
plugins: anyio-4.15.1, asyncio-1.4.0, cov-7.1.0
collected 30 items

backend/tests/test_alerts.py::test_alert_generation_at_threshold PASSED  [  3%]
backend/tests/test_alerts.py::test_alert_cooldown_open_acknowledged_snoozed PASSED [  6%]
backend/tests/test_alerts.py::test_snooze_duration_stored_and_expires PASSED [ 10%]
backend/tests/test_alerts.py::test_alerts_fire_in_simulation_run PASSED  [ 13%]
backend/tests/test_alerts.py::test_thresholds_endpoint PASSED            [ 16%]
backend/tests/test_api.py::test_health_check PASSED                      [ 20%]
backend/tests/test_api.py::test_health_check_db_failure PASSED           [ 23%]
backend/tests/test_api.py::test_health_check_model_not_loaded PASSED     [ 26%]
backend/tests/test_api.py::test_config_app_port_env PASSED               [ 30%]
backend/tests/test_api.py::test_patients_endpoints PASSED                [ 33%]
backend/tests/test_api.py::test_digital_twin_endpoints PASSED            [ 36%]
backend/tests/test_api.py::test_risk_and_history_endpoints PASSED        [ 40%]
backend/tests/test_api.py::test_whatif_endpoint PASSED                   [ 43%]
backend/tests/test_api.py::test_sensor_ingestion_and_pipeline_trigger PASSED [ 46%]
backend/tests/test_api.py::test_risk_horizon_and_why_risk_changed PASSED [ 50%]
backend/tests/test_api.py::test_alert_lifecycle_and_notes PASSED         [ 53%]
backend/tests/test_api.py::test_simulation_endpoints PASSED              [ 56%]
backend/tests/test_api.py::test_websocket_stream PASSED                  [ 60%]
backend/tests/test_fusion.py::test_zero_future_leakage_proof PASSED      [ 63%]
backend/tests/test_fusion.py::test_fusion_service_integration PASSED     [ 66%]
backend/tests/test_honest_data_layer.py::test_fusion_no_silent_imputation PASSED [ 70%]
backend/tests/test_honest_data_layer.py::test_coverage_computation_and_prediction_refusal PASSED [ 73%]
backend/tests/test_honest_data_layer.py::test_confidence_and_ci_widening PASSED [ 76%]
backend/tests/test_honest_data_layer.py::test_patient_30d_baseline_estimation PASSED [ 80%]
backend/tests/test_honest_data_layer.py::test_risk_horizon_honest_markers_and_timezone PASSED [ 83%]
backend/tests/test_honest_data_layer.py::test_sleep_fingerprint_six_clinical_axes PASSED [ 86%]
backend/tests/test_honest_data_layer.py::test_why_risk_changed_single_and_multiple_predictions PASSED [ 90%]
backend/tests/test_prediction.py::test_prediction_scoring PASSED         [ 93%]
backend/tests/test_twin.py::test_twin_construction PASSED                [ 96%]
backend/tests/test_whatif.py::test_whatif_counterfactual_simulation PASSED [100%]

=============================== tests coverage ================================
Name                                           Stmts   Miss  Cover   Missing
----------------------------------------------------------------------------
backend\app\__init__.py                            1      0   100%
backend\app\config.py                             68      3    96%   89, 113-114
backend\app\database.py                           22      4    82%   32-36
backend\app\main.py                               70      5    93%   118, 127-130
backend\app\models.py                             88      0   100%
backend\app\routers\patients.py                   50      3    94%   68, 107, 124
backend\app\routers\predictions.py                73      5    93%   44, 67, 167, 186, 204
backend\app\routers\sensors.py                    30      8    73%   26-31, 51, 63-64
backend\app\routers\simulation.py                 54     26    52%   32-47, 56-67, 106-118
backend\app\routers\twin.py                       41      4    90%   29, 39, 54, 64
backend\app\routers\whatif.py                     20      1    95%   29
backend\app\schemas.py                           230      0   100%
backend\app\services\alert_service.py             98      3    97%   119, 148, 183
backend\app\services\ehr_service.py               84      2    98%   131-132
backend\app\services\fingerprint_service.py       52      2    96%   137, 196
backend\app\services\fusion_service.py            83      2    98%   45, 131
backend\app\services\prediction_service.py       104      8    92%   51-59, 74-76
backend\app\services\sensor_service.py            41     11    73%   29, 42-47, 63-72
backend\app\services\twin_service.py             207     18    91%   52, 154, 184, 321, 324, 330, 359, 410, 431-434, 458, 460, 464-468
backend\app\services\whatif_service.py            61      4    93%   94-95, 102-103
backend\app\services\ws_manager.py                34      9    74%   40-49
backend\app\simulation\__init__.py                 4      0   100%
backend\app\simulation\ehr_simulator.py          178     49    72%   79, 128-134, 147, 149, 155, 161, 163, 203-207, 209-213, 220-237, 296, 298, 302, 304, 306, 308, 321, 327, 329
backend\app\simulation\scenario_runner.py        125     89    29%   61-81, 89-95, 105-158, 188-202, 208-217, 225-252
backend\app\simulation\wearable_simulator.py     186     28    85%   105, 204-224, 257, 259, 263, 277, 279, 281, 285
----------------------------------------------------------------------------
TOTAL                                           2004    284    86%
====================== 30 passed, 19 warnings in 10.00s =======================
```

### 3. Frontend Build & Typecheck
**Command:**
```powershell
cd dashboard; npm run build; npx tsc --noEmit
```
**Raw Output:**
```
> react-example@0.0.0 build
> vite build

vite v8.3.4 building client environment for production...
transforming...
✓ 16 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   1.25 kB │ gzip:  0.58 kB
dist/assets/index-CaHEg_y7.css   40.66 kB │ gzip:  7.82 kB
dist/assets/index-BPfduECR.js   219.49 kB │ gzip: 68.57 kB
✓ built in 282ms
```
TypeScript typecheck (`npx tsc --noEmit`) completed with exit code 0 and 0 errors.

### 4. Git Diff Stat
**Command:**
```powershell
git diff --stat
```
**Raw Output:**
```
 .env.example                                  |   1 +
 backend/app/config.py                         |   3 +
 backend/app/routers/predictions.py            |  34 ++++
 backend/app/schemas.py                        |  51 +++--
 backend/app/services/ehr_service.py           |  93 +++++++--
 backend/app/services/fingerprint_service.py   | 206 +++++++++++--------
 backend/app/services/fusion_service.py        |  98 ++++++---
 backend/app/services/prediction_service.py    |  52 ++++-
 backend/app/services/twin_service.py          | 280 +++++++++++++++++---------
 dashboard/src/components/RiskHorizonChart.tsx |   2 +-
 dashboard/src/types/index.ts                  |  46 +++--
 ml/explain.py                                 |   8 +-
 ml/feature_engineering.py                     | 188 +++++++++++------
 13 files changed, 743 insertions(+), 319 deletions(-)
```

### 5. NOT RUN / NOT VERIFIED (Phase 2)
- Ambulatory 24h blood pressure monitoring (ABPM) hardware integration — nightwatch deliberately marks nocturnal dipping as N/A (Requires ABPM) per clinical guidelines.
- Live streaming WebSocket verification with low-coverage patient simulated ticks (deferred to Phase 7).


