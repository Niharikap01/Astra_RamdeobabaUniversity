# NightWatch Handoff — for weaker continuation model
## Architecture
FastAPI (backend/app/main.py lifespan) -> SQLite (backend/app/database.py) -> PredictionService (LightGBM+calibrator joblib) -> TwinService/Fusion/EHR/Fingerprint/Alert/WS. Synthetic data via ml/generate_synthetic.py + backend/app/simulation/*. React/Vite/TS/Tailwind/ECharts dashboard proxying /api + /ws.

## API Contract (prefix /api unless noted)
GET /api/patients -> PatientSummary[]; GET /api/patients/{id}/profile -> PatientProfileDetail
POST/GET /api/patients/{id}/sensor-readings -> SensorReadingResponse[]
GET /api/patients/{id}/twin -> DigitalTwinResponse (static_profile/dynamic_state/prediction/sleep_fingerprint)
GET /api/patients/{id}/risk-horizon -> RiskHorizonResponse (series[].timestamp Asia/Kolkata, risk_pct, uncertainty_*, BP/med markers); GET /api/patients/{id}/why-risk-changed -> WhyRiskChangedResponse; GET /api/patients/{id}/sleep-fingerprint
GET /api/patients/{id}/risk -> PredictionResponse (422 if coverage<50%); GET /api/patients/{id}/risk-history
GET /api/thresholds -> {moderate,high}; GET /api/patients/{id}/alerts; POST /api/alerts/{id}/{acknowledge|snooze|false-positive}
POST /api/patients/{id}/what-if -> WhatIfResponse; POST /api/simulation/{start|stop|status|scenario/{id}}; GET /health; WS /ws/twin/{id}

## File Map
backend/app/{main,config,database,models,schemas}; routers/{patients,predictions,sensors,twin,whatif,simulation}; services/{twin,fusion,ehr,prediction,alert,sensor,whatif,ws_manager}; simulation/{ehr,wearable,scenario}
ml/{train_lightgbm,feature_engineering,explain,robustness,artifacts/*}; dashboard/src/{App,components/*,services/api,styles/tokens,types}

## Component Conventions
Dark navy only (tokens.ts TOKENS.colors.dark); reuse NavigationRail/PatientHeader/RightAlertDrawer/RiskHorizonChart/RiskSummaryCard; one <EChart/> wrapper themed from tokens; <DataTableToggle rows cols/> for CSV; store UTC display Asia/Kolkata; never silent impute NaN; "associated with" not "caused by".

## How to add a panel
1) Add fetch to services/api.ts + type in types/index.ts 2) Create component in dashboard/src/components/ using EChart wrapper + DataTableToggle 3) Wire in App.tsx three-zone layout 4) Handle loading/empty/offline/coverage states.

## Run Commands
.venv_check\Scripts\python -m pytest backend/tests -q | Select-Object -Last 8
.venv_check\Scripts\python -m uvicorn backend.app.main:app --port 8000
cd dashboard; npm ci; npm run build; npm run dev -- --port 5173
