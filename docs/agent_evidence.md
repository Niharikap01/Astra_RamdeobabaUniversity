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
