# NightWatch Handoff — Architecture & Engineering Guide

## Architecture
- **Backend**: FastAPI (`backend/app/main.py`) + SQLite/SQLAlchemy 2.0 (`backend/app/database.py`).
- **ML Engine**: LightGBM + isotonic calibration + TreeSHAP (`ml/artifacts/`, `ml/train_lightgbm.py`, `ml/explain.py`).
- **Services**: `TwinService`, `FusionService`, `EHRService`, `PredictionService`, `AlertService`, `SensorService`, `WhatIfService`, `FingerprintService`, `ws_manager`.
- **Simulation**: `EHRSimulator`, `WearableSimulator`, `ScenarioSimulator` in `backend/app/simulation/`.
- **Dashboard**: React 19 + Vite + TypeScript + Tailwind 4 + ECharts (`dashboard/`).

## API Contract (prefix `/api` unless noted)
- `GET /api/patients` -> `PatientSummary[]` (id, demographic, risk_level, probability, coverage_pct, alerts_count)
- `GET /api/patients/{id}/profile` -> `PatientProfileDetail` (diagnoses, medications, baselines, coverage)
- `POST/GET /api/patients/{id}/sensor-readings` -> `SensorReadingResponse[]`
- `GET /api/patients/{id}/twin` -> `DigitalTwinResponse` (static_profile, dynamic_state, prediction, sleep_fingerprint, top_factors, recommended_actions)
- `GET /api/patients/{id}/risk-horizon` -> `RiskHorizonResponse` (24h series with Asia/Kolkata timestamps, risk_pct, confidence bounds, sleep stage, BP/med markers)
- `GET /api/patients/{id}/why-risk-changed` -> `WhyRiskChangedResponse` (current/previous risk, waterfall factors, trust statement)
- `GET /api/patients/{id}/sleep-fingerprint` -> `SleepFingerprintData` (deviation vs personal baseline across 6 radar axes)
- `GET /api/patients/{id}/risk` -> `PredictionResponse` (422 if coverage < 50%)
- `GET /api/patients/{id}/risk-history` -> `PredictionResponse[]`
- `GET /api/thresholds` -> `{moderate: float, high: float}`
- `GET /api/patients/{id}/alerts` -> `AlertResponse[]`
- `POST /api/alerts/{id}/acknowledge` | `snooze` | `false-positive`
- `POST /api/patients/{id}/what-if` -> `WhatIfResponse` (counterfactual delta, sustained change over coming week)
- `POST /api/simulation/start` | `stop` | `status` | `scenario/{id}`
- `GET /health` -> `{status: healthy, database: connected, model_loaded: true}`
- `WS /ws/twin/{id}` -> Live twin state updates

## File Map
- `backend/app/`: `main.py`, `config.py`, `database.py`, `models.py`, `schemas.py`
- `backend/app/routers/`: `patients.py`, `predictions.py`, `sensors.py`, `twin.py`, `whatif.py`, `simulation.py`
- `backend/app/services/`: `twin_service.py`, `fusion_service.py`, `ehr_service.py`, `prediction_service.py`, `alert_service.py`, `sensor_service.py`, `whatif_service.py`, `fingerprint_service.py`, `ws_manager.py`
- `backend/app/simulation/`: `ehr_simulator.py`, `wearable_simulator.py`, `scenario_simulator.py`
- `ml/`: `train_lightgbm.py`, `feature_engineering.py`, `explain.py`, `robustness.py`, `artifacts/`
- `dashboard/src/`: `App.tsx`, `components/`, `services/api.ts`, `styles/tokens.ts`, `types/index.ts`

## Component & Clinical Conventions
- **Theme**: Dark navy only (`tokens.ts` `TOKENS.colors.dark`).
- **Core components**: `NavigationRail`, `PatientHeader`, `RightAlertDrawer`, `RiskHorizonChart`, `RiskSummaryCard`.
- **ECharts**: Themed `<EChart option/>` wrapper via tokens; `<DataTableToggle rows cols/>` for CSV export.
- **Time**: Store UTC in database, format and display as `Asia/Kolkata`.
- **Honesty**: Cuff is ground truth; wearable is context; never silent-impute missing telemetry; "associated with", never "caused by".

## How to Add a Panel
1. Define types in `dashboard/src/types/index.ts` and fetch call in `dashboard/src/services/api.ts`.
2. Build component in `dashboard/src/components/` using themed `<EChart>` and `<DataTableToggle>`.
3. Wire component into `dashboard/src/App.tsx` handling loading skeleton, empty state, and low coverage refusal.

## Run Commands
- Tests: `.\.venv_check\Scripts\python.exe -m pytest backend/tests -q`
- Backend: `.\.venv_check\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000`
- Dashboard: `cd dashboard; npm ci; npm run build; npm run dev`
